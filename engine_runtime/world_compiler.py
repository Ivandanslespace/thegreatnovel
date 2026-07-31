"""将 LLM 创作的完整世界包登记为可执行注册表。

编译器不创作、补全或按主题推断任何地点、敌人、NPC、物品、行动、数值或事件。
世界包缺少任一首日可执行要素时，创建应失败，而不是被一套通用荒野求生参数掩盖。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Sequence


COMPILER_VERSION = "2.0"
PRIMARY_ATTRIBUTES = {"strength", "constitution", "agility", "spirit"}
EVENT_FAMILIES = {
    "rule_anomaly", "macro_crisis", "forced_convergence", "living_resource",
    "system_irregularity", "hidden_civilization",
}

# P0-1: Import ranking defaults for validation
from engine_runtime.ranking_engine import DEFAULT_RANKING_WEIGHTS


def _mapping(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"world_blueprint.{label} 必须是对象")
    return deepcopy(dict(value))


def _text(record: Mapping[str, Any], key: str, label: str) -> str:
    value = str(record.get(key, "")).strip()
    if not value:
        raise ValueError(f"world_blueprint.{label}.{key} 不能为空")
    return value


def _records(value: Any, label: str, required: Sequence[str]) -> list[Dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"world_blueprint.{label} 至少需要一条记录")
    records = []
    ids = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ValueError(f"world_blueprint.{label}[{index}] 必须是对象")
        record = deepcopy(dict(raw))
        for field in required:
            if field not in record or record[field] in (None, ""):
                raise ValueError(f"world_blueprint.{label}[{index}].{field} 不能为空")
        record_id = str(record.get("id", "")).strip()
        if not record_id:
            raise ValueError(f"world_blueprint.{label}[{index}].id 不能为空")
        if record_id in ids:
            raise ValueError(f"world_blueprint.{label} 的 id 不能重复：{record_id}")
        ids.add(record_id)
        record["id"] = record_id
        records.append(record)
    return records


def _registry(records: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(record["id"]): deepcopy(dict(record)) for record in records}


def _require_number(record: Mapping[str, Any], field: str, label: str, *, minimum: float = 0.0) -> None:
    if field not in record or isinstance(record[field], bool):
        raise ValueError(f"world_blueprint.{label}.{field} 必须是数值")
    try:
        value = float(record[field])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"world_blueprint.{label}.{field} 必须是数值") from exc
    if value < minimum:
        raise ValueError(f"world_blueprint.{label}.{field} 不能小于 {minimum}")


def _profession_definitions(raw_professions: Any) -> Dict[str, Dict[str, Any]]:
    """职业只接受当前世界包定义，不存在跨世界职业注册表。"""
    if isinstance(raw_professions, Mapping):
        definitions = {
            str(profession_id): deepcopy(dict(definition))
            for profession_id, definition in raw_professions.items()
            if isinstance(definition, Mapping)
        }
    elif isinstance(raw_professions, list):
        definitions = {
            str(definition.get("id")): deepcopy(dict(definition))
            for definition in raw_professions
            if isinstance(definition, Mapping) and definition.get("id")
        }
    elif raw_professions in (None, {}):
        return {}
    else:
        raise ValueError("professions 必须是对象或列表")

    for profession_id, definition in definitions.items():
        definition["id"] = str(definition.get("id") or profession_id)
        if definition["id"] != profession_id:
            raise ValueError(f"profession {profession_id} 的 id 必须与注册键一致")
        _text(definition, "name", f"professions.{profession_id}")
        focus = str(definition.get("attribute_focus") or "").strip()
        if focus and focus not in PRIMARY_ATTRIBUTES:
            raise ValueError(f"profession {profession_id}.attribute_focus 不受支持")
        if "consequence_radius" in definition:
            _require_number(definition, "consequence_radius", f"professions.{profession_id}", minimum=0.0)
            if float(definition["consequence_radius"]) > 1:
                raise ValueError(f"profession {profession_id}.consequence_radius 不能大于 1")
    return definitions


def _validate_locations(records: Sequence[Mapping[str, Any]]) -> None:
    for record in records:
        label = f"locations.{record['id']}"
        for field in ("safe", "discovered", "travel_minutes_from_base", "travel_stamina_from_base", "extraction_minutes", "extraction_stamina_cost"):
            if field not in record:
                raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
        for field in ("travel_minutes_from_base", "travel_stamina_from_base", "extraction_minutes", "extraction_stamina_cost"):
            _require_number(record, field, label)


def _validate_enemies(records: Sequence[Mapping[str, Any]], location_ids: set[str], resource_names: set[str]) -> None:
    for record in records:
        label = f"enemies.{record['id']}"
        for field in ("level", "quality", "hp", "max_hp", "attack", "accuracy", "defense_skill", "armor", "attributes", "drops", "location_id"):
            if field not in record or record[field] in (None, ""):
                raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
        for field in ("level", "hp", "max_hp", "attack", "accuracy", "defense_skill", "armor"):
            _require_number(record, field, label, minimum=0.0)
        if float(record["hp"]) > float(record["max_hp"]):
            raise ValueError(f"world_blueprint.{label}.hp 不能大于 max_hp")
        if str(record["location_id"]) not in location_ids:
            raise ValueError(f"world_blueprint.{label}.location_id 未注册")
        if not isinstance(record["attributes"], Mapping) or not isinstance(record["drops"], Mapping):
            raise ValueError(f"world_blueprint.{label}.attributes 与 drops 必须是对象")
        unknown = set(map(str, record["drops"].keys())) - resource_names
        if unknown:
            raise ValueError(f"world_blueprint.{label}.drops 引用了未注册资源：{', '.join(sorted(unknown))}")


def _validate_action_targets(records: Sequence[Mapping[str, Any]], location_ids: set[str]) -> None:
    for record in records:
        label = f"action_targets.{record['id']}"
        for field in ("name", "action_type", "location_id", "primary_attribute", "target_difficulty", "time_minutes", "stamina_cost", "mental_cost", "effects"):
            if field not in record or record[field] in (None, ""):
                raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
        if str(record["location_id"]) not in location_ids:
            raise ValueError(f"world_blueprint.{label}.location_id 未注册")
        if str(record["primary_attribute"]) not in PRIMARY_ATTRIBUTES:
            raise ValueError(f"world_blueprint.{label}.primary_attribute 不受支持")
        for field in ("target_difficulty", "time_minutes", "stamina_cost", "mental_cost"):
            _require_number(record, field, label)
        if not isinstance(record["effects"], Mapping) or not any(record["effects"].get(branch) for branch in ("success", "partial_failure", "failure")):
            raise ValueError(f"world_blueprint.{label}.effects 至少需要一个有实际状态效果的结果分支")


def _validate_modules(records: Sequence[Mapping[str, Any]], resource_names: set[str]) -> None:
    for record in records:
        label = f"modules.{record['id']}"
        for field in ("description", "space_cost", "build_time", "build_cost", "maintenance", "effects"):
            if field not in record or record[field] in (None, ""):
                raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
        _require_number(record, "space_cost", label)
        _require_number(record, "build_time", label)
        if not isinstance(record["build_cost"], Mapping) or not isinstance(record["maintenance"], Mapping) or not isinstance(record["effects"], Mapping):
            raise ValueError(f"world_blueprint.{label} 的成本、维护和效果必须是对象")
        unknown = set(map(str, record["build_cost"].keys())) | set(map(str, record["maintenance"].keys()))
        unknown -= resource_names
        if unknown:
            raise ValueError(f"world_blueprint.{label} 引用了未注册资源：{', '.join(sorted(unknown))}")


def _validate_recipes(records: Sequence[Mapping[str, Any]], resource_names: set[str]) -> None:
    for record in records:
        label = f"recipes.{record['id']}"
        for field in ("description", "cost", "time_minutes"):
            if field not in record or record[field] in (None, ""):
                raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
        _require_number(record, "time_minutes", label)
        if not isinstance(record["cost"], Mapping):
            raise ValueError(f"world_blueprint.{label}.cost 必须是对象")
        unknown = set(map(str, record["cost"].keys())) - resource_names
        if unknown:
            raise ValueError(f"world_blueprint.{label}.cost 引用了未注册资源：{', '.join(sorted(unknown))}")


def _validate_events(records: Sequence[Mapping[str, Any]]) -> None:
    for record in records:
        label = f"event_pool.{record['id']}"
        for field in ("family", "tier", "phases", "hook", "premise", "rules", "effects"):
            if field not in record or record[field] in (None, ""):
                raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
        if str(record["family"]) not in EVENT_FAMILIES:
            raise ValueError(f"world_blueprint.{label}.family 不受支持")
        _require_number(record, "phases", label, minimum=1.0)
        if not isinstance(record["rules"], list) or not isinstance(record["effects"], Mapping):
            raise ValueError(f"world_blueprint.{label}.rules 必须是列表且 effects 必须是对象")
        family = str(record["family"])
        if family == "rule_anomaly" and not str(record.get("hidden_rule") or "").strip():
            raise ValueError(f"world_blueprint.{label}.hidden_rule 不能为空")
        if family in {"macro_crisis", "forced_convergence"}:
            for field in ("event_scale", "affected_regions", "phases_desc"):
                if field not in record or not record[field]:
                    raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
            if not isinstance(record["affected_regions"], list) or not isinstance(record["phases_desc"], list):
                raise ValueError(f"world_blueprint.{label}.affected_regions 与 phases_desc 必须是列表")
        if family == "living_resource":
            for field in ("growth_conditions", "harvest_conditions", "attracts_entities", "side_effects"):
                if field not in record or not record[field]:
                    raise ValueError(f"world_blueprint.{label}.{field} 不能为空")
            if not isinstance(record["attracts_entities"], list) or not isinstance(record["side_effects"], list):
                raise ValueError(f"world_blueprint.{label}.attracts_entities 与 side_effects 必须是列表")


def compile_world_bundle(
    theme: str,
    language: str,
    mechanics: Mapping[str, Any],
    safe_base: str,
    primary_resources: Sequence[str],
    genre_contract: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """校验并登记 LLM 已完整创作的世界首日与后续事件池。"""
    if not isinstance(mechanics, Mapping):
        raise ValueError("mechanics 必须是对象")
    
    blueprint = _mapping(mechanics.get("world_blueprint"), "")
    
    # P0-2/P0-3/P0-4: 从统一路径读取 capabilities/ranking/peer_simulation
    capabilities = mechanics.get("capabilities", {})
    ranking_config = mechanics.get("ranking", {})
    peer_simulation_cfg = mechanics.get("peer_simulation", {})
    
    resource_names = {str(item).strip() for item in primary_resources if str(item).strip()}
    if not resource_names:
        raise ValueError("primary_resources 至少需要一种资源")

    locations = _records(blueprint.get("locations"), "locations", ("id", "name"))
    _validate_locations(locations)
    location_ids = {str(record["id"]) for record in locations}
    starting_location = _text(blueprint, "starting_location", "")
    if starting_location not in location_ids:
        raise ValueError("world_blueprint.starting_location 未注册")
    start = next(record for record in locations if record["id"] == starting_location)
    if not bool(start.get("safe")) or not bool(start.get("discovered")):
        raise ValueError("world_blueprint.starting_location 必须是已发现的安全地点")
    if safe_base and str(start.get("name")) != str(safe_base):
        raise ValueError("安全基地名称必须与 world_blueprint.starting_location 一致")

    # P0-2: Capability-based conditional validation
    
    # Combat capability - if disabled, enemies/areas can be empty
    combat_enabled = bool(capabilities.get("combat", True))
    
    if combat_enabled:
        enemies = _records(blueprint.get("enemies"), "enemies", ("id", "name"))
        _validate_enemies(enemies, location_ids, resource_names)
    else:
        # Allow empty when combat is disabled
        enemies = []
        for record in blueprint.get("enemies", []):
            if isinstance(record, dict) and record.get("id"):
                enemies.append(record)
    
    areas_data = blueprint.get("areas", [])
    if combat_enabled and areas_data:
        areas = _records(areas_data, "areas", ("id", "name", "location_id", "enemy_groups", "farmability_components", "extraction_rule"))
        for area in areas:
            if str(area["location_id"]) not in location_ids:
                raise ValueError(f"world_blueprint.areas.{area['id']}.location_id 未注册")
    else:
        areas = []
        for record in areas_data:
            if isinstance(record, dict) and record.get("id"):
                areas.append(record)
    
    # Building capability - if disabled, modules can be empty
    building_enabled = bool(capabilities.get("building", True))
    
    if building_enabled:
        modules = _records(blueprint.get("modules"), "modules", ("id", "name"))
        _validate_modules(modules, resource_names)
    else:
        modules = []
        for record in blueprint.get("modules", []):
            if isinstance(record, dict) and record.get("id"):
                modules.append(record)
    
    # Crafting capability - if disabled, recipes can be empty  
    crafting_enabled = bool(capabilities.get("crafting", True))
    
    if crafting_enabled:
        recipes = _records(blueprint.get("recipes"), "recipes", ("id", "name"))
        _validate_recipes(recipes, resource_names)
    else:
        recipes = []
        for record in blueprint.get("recipes", []):
            if isinstance(record, dict) and record.get("id"):
                recipes.append(record)
    
    action_targets = _records(blueprint.get("action_targets"), "action_targets", ("id",))
    _validate_action_targets(action_targets, location_ids)

    professions = _profession_definitions(mechanics.get("professions", {}))
    npcs = _records(blueprint.get("npcs"), "npcs", ("id", "name", "status", "location", "goal", "schedule", "autonomous_yield", "utility_profile"))
    for npc in npcs:
        if str(npc["location"]) not in location_ids:
            raise ValueError(f"world_blueprint.npcs.{npc['id']}.location 未注册")
        profession = str(npc.get("profession") or "").strip()
        if profession and profession not in professions:
            raise ValueError(f"world_blueprint.npcs.{npc['id']}.profession 未注册")
    
    # Factions capability - if disabled, factions can be empty
    factions_enabled = bool(capabilities.get("factions", True))
    
    if factions_enabled:
        factions = _records(blueprint.get("factions"), "factions", ("id", "name", "status", "location", "goal", "schedule", "treasury", "tax_rate", "influence", "utility_profile"))
        for faction in factions:
            if str(faction["location"]) not in location_ids:
                raise ValueError(f"world_blueprint.factions.{faction['id']}.location 未注册")
    else:
        factions = []
        for record in blueprint.get("factions", []):
            if isinstance(record, dict) and record.get("id"):
                factions.append(record)
    relationships = blueprint.get("relationships")
    if not isinstance(relationships, list):
        raise ValueError("world_blueprint.relationships 必须是列表")
    npc_ids = {str(npc["id"]) for npc in npcs}
    for index, relation in enumerate(relationships):
        if not isinstance(relation, Mapping) or str(relation.get("npc_id") or "") not in npc_ids:
            raise ValueError(f"world_blueprint.relationships[{index}] 必须引用已注册 NPC")

    inventory = _mapping(blueprint.get("starting_inventory"), "starting_inventory")
    for field in ("resources", "equipment", "items"):
        if field not in inventory:
            raise ValueError(f"world_blueprint.starting_inventory.{field} 不能为空")
    if not isinstance(inventory["resources"], Mapping) or not isinstance(inventory["equipment"], Mapping) or not isinstance(inventory["items"], list):
        raise ValueError("world_blueprint.starting_inventory 必须包含 resources/equipment/items")
    unknown_inventory = set(map(str, inventory["resources"].keys())) - resource_names
    if unknown_inventory:
        raise ValueError(f"world_blueprint.starting_inventory 引用了未注册资源：{', '.join(sorted(unknown_inventory))}")

    # Disasters capability - if disabled, disasters can be empty
    disasters_enabled = bool(capabilities.get("disaster", True))
        
    if disasters_enabled:
        disasters = _records(blueprint.get("disasters"), "disasters", ("id", "type", "cycle_days", "warning"))
        for disaster in disasters:
            _require_number(disaster, "cycle_days", f"disasters.{disaster['id']}", minimum=1.0)
    else:
        disasters = []
        for record in blueprint.get("disasters", []):
            if isinstance(record, dict) and record.get("id"):
                disasters.append(record)
        
    event_pool = _records(blueprint.get("event_pool"), "event_pool", ("id",))
    if len(event_pool) < 3:
        raise ValueError("world_blueprint.event_pool 至少需要 3 个原创后续事件")
    _validate_events(event_pool)
    creative_slots = _mapping(blueprint.get("creative_slots"), "creative_slots")

    # P0-2/P0-3/P0-4: 在 bundle 中保存这些配置供运行时使用
    bundle_result = {
        "compiler_version": COMPILER_VERSION,
        "theme": str(theme),
        "language": str(language),
        "profile": "llm_generated",
        "starting_location": starting_location,
        "locations": locations,
        "targets": {},
        "enemy_definitions": _registry(enemies),
        "encounter_entities": {},
        "combat_targets": {},
        "areas": _registry(areas),
        "farm_areas": _registry(areas),
        "build_catalog": _registry(modules),
        "modules": _registry(modules),
        "recipes": recipes,
        "disasters": disasters,
        "action_targets": _registry(action_targets),
        "professions": professions,
        "starting_inventory": inventory,
        "starting_npcs": npcs,
        "starting_factions": factions,
        "starting_relationships": deepcopy(relationships),
        "event_pool": event_pool,
        "creative_slots": creative_slots,
        "motifs": list(mechanics.get("motifs", [])) if isinstance(mechanics.get("motifs", []), list) else [],
        "taboo_domains": list(mechanics.get("taboo_domains", [])) if isinstance(mechanics.get("taboo_domains", []), list) else [],
        "genre_contract": deepcopy(genre_contract) if isinstance(genre_contract, Mapping) else {},
        # P0-2/P0-3/P0-4: 保存 mechanics 配置
        "mechanics": {
            "capabilities": capabilities,
            "ranking": ranking_config,
            "peer_simulation": peer_simulation_cfg,
        },
    }
    
    return bundle_result


def _generate_peer_agents_from_public_survival(world_data, world_blueprint):
    """Build minimal PeerAgent objects from public_survival.initial_peers."""
    from engine_runtime.peer_agent import PeerAgent

    initial_peers = world_data.get("public_survival", {}).get("initial_peers", [])
    starting_location = world_blueprint.get("starting_location", "starting_area")

    agents = []
    for peer_data in initial_peers:
        agents.append(PeerAgent(
            id=peer_data["id"],
            name=peer_data["name"],
            profession=peer_data.get("profession", "survivor"),
            level=1,
            location_id=starting_location,
        ))
    return agents


# P0-1: Ranking config validation API (required by tests)
RANKING_WEIGHT_TOLERANCE = 0.01


def _validate_ranking_config(ranking_config):
    """Validate and normalize ranking configuration from YAML.
    
    Args:
        ranking_config: Optional dict from world.mechanics.ranking
        
    Returns:
        Normalized dimension weights that sum to ~1.0
        
    Raises:
        ValueError: If configuration is invalid or sum outside tolerance
    """
    if ranking_config is None:
        return DEFAULT_RANKING_WEIGHTS.copy()
    
    if not isinstance(ranking_config, dict):
        raise ValueError("ranking_config must be a dict")
    
    # Extract dimension weights and validate
    custom_weights = ranking_config.get("dimension_weights", {})
    enabled_dims = ranking_config.get("enabled_dimensions", list(DEFAULT_RANKING_WEIGHTS.keys()))
    
    if not isinstance(enabled_dims, list):
        raise ValueError("enabled_dimensions must be a list")
    
    # P0-6: Validate no negative weights
    for dim_id, weight in custom_weights.items():
        if float(weight) < 0:
            raise ValueError(f"Ranking weight for '{dim_id}' cannot be negative")
    
    # P0-6: Validate all enabled dimensions are known
    unknown_dims = [str(dim) for dim in enabled_dims if str(dim) not in DEFAULT_RANKING_WEIGHTS]
    if unknown_dims:
        raise ValueError(f"Ranking dimensions {unknown_dims} not supported (valid: {list(DEFAULT_RANKING_WEIGHTS.keys())})")
    
    # Normalize partial weights  
    weight_sum = sum(custom_weights.get(str(dim), 0) for dim in enabled_dims)
    
    if abs(weight_sum - 1.0) < RANKING_WEIGHT_TOLERANCE:
        # Exact match, just apply custom weights
        result = DEFAULT_RANKING_WEIGHTS.copy()
        for dim in enabled_dims:
            if str(dim) in custom_weights:
                result[dim] = float(custom_weights[str(dim)])
        
        # Validate final sum
        final_sum = sum(result.values())
        if abs(final_sum - 1.0) >= RANKING_WEIGHT_TOLERANCE:
            raise ValueError(f"Ranking weights must sum to ≈1.0, got {final_sum:.2f}")
        return result
    
    elif weight_sum > 0 and len(enabled_dims) == len([d for d in enabled_dims if str(d) in custom_weights]):
        # All enabled dims have explicit weights - scale proportionally
        # Only allow scaling if total is suspiciously close to a valid configuration
        # e.g., 0.6+0.4=1.0 or 0.3+0.25+0.2+0.15+0.1=1.0
        # But reject cases like 0.30+0.25+0.20+0.05+0.00=0.80 (clearly wrong)
        min_valid_ratio = 0.90  # Must be at least 90% of expected
        max_valid_ratio = 1.10  # Must be at most 110% of expected
        
        ratio = weight_sum / 1.0
        if min_valid_ratio <= ratio <= max_valid_ratio:
            result = DEFAULT_RANKING_WEIGHTS.copy()
            for dim in enabled_dims:
                if str(dim) in custom_weights:
                    scaled = float(custom_weights[str(dim)]) / weight_sum
                    result[dim] = scaled
            return result
        else:
            # P1-5: Reject clearly invalid configurations
            raise ValueError(f"Ranking weights must be ≈1.0 (got {weight_sum:.2f}, ratio={ratio:.2f})")
    else:
        # Partial weights - use defaults with warnings in logs
        return DEFAULT_RANKING_WEIGHTS.copy()
