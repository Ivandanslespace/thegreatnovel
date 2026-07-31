"""将 LLM 创作的完整世界包登记为可执行注册表。

编译器不创作、补全或按主题推断任何地点、敌人、NPC、物品、行动、数值或事件。
世界包缺少任一首日可执行要素时，创建应失败，而不是被一套通用荒野求生参数掩盖。
"""

from __future__ import annotations

from copy import deepcopy
from collections import defaultdict
from typing import Any, Dict, Mapping, Sequence


COMPILER_VERSION = "2.0"
PRIMARY_ATTRIBUTES = {"strength", "constitution", "agility", "spirit"}
EVENT_FAMILIES = {
    "rule_anomaly", "macro_crisis", "forced_convergence", "living_resource",
    "system_irregularity", "hidden_civilization",
}

# Default ranking weights and scales (defined here to avoid circular imports)
DEFAULT_RANKING_WEIGHTS = {
    "combat": 0.30,
    "resources": 0.25,
    "base": 0.20,
    "information": 0.15,
    "social": 0.10
}

DEFAULT_RANKING_SCALES = {
    "combat_multiplier": 0.1,
    "resource_multiplier": 0.5,
    "base_bonus": 20.0,
    "information_bonus": 25.0,
    "social_bonus": 20.0
}

RANKING_WEIGHT_TOLERANCE = 0.05  # Weights must sum to ~1.0 within ±0.05


def _validate_ranking_config(ranking_config: Any) -> Dict[str, Any]:
    """Validate and normalize ranking configuration from world blueprint.
    
    Args:
        ranking_config: Raw ranking config from world template
        
    Returns:
        Validated ranking config dict
        
    Raises:
        ValueError: If config is invalid
    """
    if ranking_config in (None, {}):
        return DEFAULT_RANKING_WEIGHTS.copy()
    
    if not isinstance(ranking_config, Mapping):
        raise ValueError("ranking config must be an object or empty")
    
    # Get enabled dimensions (empty means all defaults)
    enabled_dims = ranking_config.get("enabled_dimensions", [])
    if not isinstance(enabled_dims, list) or not enabled_dims:
        enabled_dims = list(DEFAULT_RANKING_WEIGHTS.keys())
    else:
        # Validate dimension IDs
        valid_base_ids = set(DEFAULT_RANKING_WEIGHTS.keys())
        for dim_id in enabled_dims:
            if str(dim_id) not in valid_base_ids:
                raise ValueError(f"ranking dimension '{dim_id}' not supported; use one of: {', '.join(sorted(valid_base_ids))}")
    
    # Get dimension weights with validation
    custom_weights = ranking_config.get("dimension_weights", {})
    if not isinstance(custom_weights, Mapping):
        raise ValueError("dimension_weights must be an object")
    
    # Validate that custom weights only reference enabled dimensions
    for weight_key in custom_weights:
        if str(weight_key) not in enabled_dims:
            raise ValueError(f"dimension_weights references disabled dimension '{weight_key}'")
    
    # Check if ALL enabled dims have weights defined or NONE do
    custom_weight_keys = {str(dim) for dim in enabled_dims if str(dim) in custom_weights}
    
    if not custom_weight_keys:
        # No custom weights at all - return defaults
        normalized_weights = {dim: DEFAULT_RANKING_WEIGHTS[dim] for dim in enabled_dims}
    elif len(custom_weight_keys) == len(enabled_dims):
        # All specified - validate they sum to 1.0 exactly
        custom_weight_sum = 0.0
        for dim in enabled_dims:
            val = float(custom_weights[str(dim)])
            if val < 0:
                raise ValueError(f"dimension_weights['{dim}'] cannot be negative")
            custom_weight_sum += val
        
        if abs(custom_weight_sum - 1.0) > RANKING_WEIGHT_TOLERANCE:
            raise ValueError(
                f"All dimension_weights must sum to ≈1.0 within ±{RANKING_WEIGHT_TOLERANCE}, "
                f"but got {custom_weight_sum:.3f}. Full list: {{dim: w for dim, w in temp_weights.items()}}"
            )
        
        # Use custom weights directly
        normalized_weights = {dim: float(custom_weights[str(dim)]) for dim in enabled_dims}
    else:
        # PARTIAL override - some specified, some use defaults
        # Strategy: normalize ONLY the custom values, keep defaults as-is
        # Example: combat=0.50 only -> scale combat down proportionally while others stay default
        custom_sum = sum(float(custom_weights[str(dim)]) for dim in enabled_dims if str(dim) in custom_weights)
        
        temp_weights = {}
        for dim in enabled_dims:
            if str(dim) in custom_weights:
                # Scale custom value to preserve relative proportions
                temp_weights[dim] = float(custom_weights[str(dim)]) / custom_sum
            else:
                # Keep default
                temp_weights[dim] = DEFAULT_RANKING_WEIGHTS[dim]
        
        normalized_weights = temp_weights
    
    result_scales = defaultdict(float)
    # Load default scales
    for key, value in DEFAULT_RANKING_SCALES.items():
        result_scales[key] = value
    
    # Override with custom scales if provided
    custom_scales = ranking_config.get("dimension_scales", {})
    if isinstance(custom_scales, Mapping):
        for k, v in custom_scales.items():
            if str(k) in enabled_dims or not str(k).startswith("_"):
                if isinstance(v, (int, float)):
                    result_scales[str(k)] = float(v)
    
    return {
        **normalized_weights,
        "_scales": dict(result_scales),
    }


def _mapping(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"world_blueprint.{label} 必须是对象")
    return deepcopy(dict(value))


def _text(record: Mapping[str, Any], key: str, label: str) -> str:
    value = str(record.get(key, "")).strip()
    if not value:
        raise ValueError(f"world_blueprint.{label}.{key} 不能为空")
    return value


def _records(value: Any, label: str, required: Sequence[str], *,
             required_if_capability: str | None = None,
             capability_enabled: bool = True) -> list[Dict[str, Any]]:
    """校验并登记记录列表。
    
    Args:
        value: 原始列表数据
        label: 字段路径标签（如 "enemies"）
        required: 必需字段列表
        required_if_capability: 当此能力启用时才强制要求的字段组（用于条件验证）
        capability_enabled: 若为 False 且存在列表，则跳过非核心字段的强制要求
    
    Raises:
        ValueError: 当列表为空或记录缺少必需字段时抛出
    """
    # 如果能力被禁用且列表为空或被省略（None），允许空列表
    if not capability_enabled:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"world_blueprint.{label} 必须是列表或省略（当前能力已禁用）")
        if not value:
            return []
    
    # 能力启用时，要求至少有一条记录
    if capability_enabled:
        if not isinstance(value, list) or not value:
            raise ValueError(f"world_blueprint.{label} 至少需要一条记录（能力已启用）")
    
    records = []
    ids = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ValueError(f"world_blueprint.{label}[{index}] 必须是对象")
        record = deepcopy(dict(raw))
        for field in required:
            if field not in record or record[field] in (None, ""):
                raise ValueError(f"world_blueprint.{label}[{index}].{field} 不能为空")
        
        # 如果有关联的能力且该能力未启用，跳过条件性必需字段
        if required_if_capability and not capability_enabled:
            # 移除这些字段而不报错
            for field in required_if_capability:
                record.pop(field, None)
        
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
    
    # P0-6: Validate and extract ranking configuration
    ranking_config = mechanics.get("ranking", {})
    validated_ranking = _validate_ranking_config(ranking_config)
    
    # Read capability flags (backward compatible: default to all enabled if missing)
    capabilities = mechanics.get("world_blueprint", {}).get("mechanics", {}).get("capabilities", {})
    capability_state = {
        "combat": bool(capabilities.get("combat", True)),
        "building": bool(capabilities.get("building", True)),
        "crafting": bool(capabilities.get("crafting", True)),
        "trading": bool(capabilities.get("trading", True)),
        "factions": bool(capabilities.get("factions", True)),
        "disasters": bool(capabilities.get("disasters", True)),
    }
    
    blueprint = _mapping(mechanics.get("world_blueprint"), "")
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
    
    # 敌人系统：根据 combat 能力决定是否必需
    if capability_state["combat"]:
        enemies = _records(blueprint.get("enemies"), "enemies", ("id", "name"), 
                          capability_enabled=True)
        _validate_enemies(enemies, location_ids, resource_names)
    else:
        enemies = _records(blueprint.get("enemies"), "enemies", ("id", "name"), 
                          capability_enabled=False)
        
    # 区域系统：战斗启用时需要敌群、可耕作性、提取规则；禁用时仅需要基本信息
    if capability_state["combat"]:
        areas = _records(blueprint.get("areas"), "areas", 
                        ("id", "name", "location_id", "enemy_groups", "farmability_components", "extraction_rule"),
                        capability_enabled=True)
        for area in areas:
            if str(area["location_id"]) not in location_ids:
                raise ValueError(f"world_blueprint.areas.{area['id']}.location_id 未注册")
    else:
        areas = _records(blueprint.get("areas"), "areas", 
                        ("id", "name", "location_id"),
                        capability_enabled=False)
        raw_areas = blueprint.get("areas")
        if isinstance(raw_areas, list):
            for area in raw_areas:
                if str(area["location_id"]) not in location_ids:
                    raise ValueError(f"world_blueprint.areas.{area['id']}.location_id 未注册")
        
    # 建造系统：根据 building 能力决定是否必需
    if capability_state["building"]:
        modules = _records(blueprint.get("modules"), "modules", ("id", "name"),
                          capability_enabled=True)
        _validate_modules(modules, resource_names)
    else:
        modules = _records(blueprint.get("modules"), "modules", ("id", "name"),
                          capability_enabled=False)
        
    # 制作系统：根据 crafting 能力决定是否必需  
    if capability_state["crafting"]:
        recipes = _records(blueprint.get("recipes"), "recipes", ("id", "name"),
                          capability_enabled=True)
        _validate_recipes(recipes, resource_names)
    else:
        recipes = _records(blueprint.get("recipes"), "recipes", ("id", "name"),
                          capability_enabled=False)
        
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
        
    # 势力系统：根据 factions 能力决定是否必需
    if capability_state["factions"]:
        factions = _records(blueprint.get("factions"), "factions", 
                           ("id", "name", "status", "location", "goal", "schedule", "treasury", "tax_rate", "influence", "utility_profile"),
                           capability_enabled=True)
        for faction in factions:
            if str(faction["location"]) not in location_ids:
                raise ValueError(f"world_blueprint.factions.{faction['id']}.location 未注册")
    else:
        factions = _records(blueprint.get("factions"), "factions", 
                           ("id", "name"),
                           capability_enabled=False)
        
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
    
    # 灾难系统：根据 disasters 能力决定是否必需
    if capability_state["disasters"]:
        disasters = _records(blueprint.get("disasters"), "disasters", ("id", "type", "cycle_days", "warning"),
                            capability_enabled=True)
        for disaster in disasters:
            _require_number(disaster, "cycle_days", f"disasters.{disaster['id']}", minimum=1.0)
    else:
        disasters = _records(blueprint.get("disasters"), "disasters", ("id", "type"),
                            capability_enabled=False)
        
    event_pool = _records(blueprint.get("event_pool"), "event_pool", ("id",))
    if len(event_pool) < 3:
        raise ValueError("world_blueprint.event_pool 至少需要 3 个原创后续事件")
    _validate_events(event_pool)
    creative_slots = _mapping(blueprint.get("creative_slots"), "creative_slots")

    # P0-6: Embed validated ranking config into generation bundle
    result_bundle = {
        "compiler_version": COMPILER_VERSION,
        "theme": str(theme),
        "language": str(language),
        "profile": "llm_generated",
        "starting_location": starting_location,
        "locations": locations,
        "enemies": enemies,
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
        "ranking_config": validated_ranking,  # P0-6: Inject ranking weights/scales
    }
    
    return result_bundle


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
