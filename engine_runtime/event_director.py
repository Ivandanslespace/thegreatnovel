"""事件导演系统 — 创意事件的生成、评估与注入管线。

EventDirector 在每回合评估是否应该向选项管线注入一个创意事件。
流程：快速门控 → 机制碰撞生成候选 → 价值评分 → 频率门过滤 → 槽位消费 → 注入。

所有数据结构自包含，不依赖外部 schema 文件。
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .calculators import clamp, deterministic_roll, number, rounded


# ---------------------------------------------------------------------------
# 1a. Data Models
# ---------------------------------------------------------------------------

FAMILY_SLOT_MAP: Dict[str, str] = {
    "macro_crisis": "macro_crises",
    "rule_anomaly": "signature_anomalies",
    "living_resource": "living_resources",
    "forced_convergence": "forced_convergences",
    "taboo_rule": "taboo_rules",
    "hidden_civilization": "hidden_civilizations",
    "system_irregularity": "system_irregularities",
}


@dataclass
class EventBlueprint:
    """一个尚未落地的创意事件蓝图。"""

    event_id: str
    family: str  # macro_crisis / rule_anomaly / living_resource / forced_convergence …
    tier: str  # normal / variant / anomaly / regional_crisis / iconic
    phase_count: int = 1
    current_phase: int = 0
    value_score: float = 0.0
    content_contract: Dict[str, Any] = field(default_factory=dict)
    mechanism_collision: List[str] = field(default_factory=list)
    effects_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为纯字典，用于持久化或传输。"""
        return {
            "event_id": self.event_id,
            "family": self.family,
            "tier": self.tier,
            "phase_count": self.phase_count,
            "current_phase": self.current_phase,
            "value_score": self.value_score,
            "content_contract": deepcopy(self.content_contract),
            "mechanism_collision": list(self.mechanism_collision),
            "effects_summary": deepcopy(self.effects_summary),
        }


@dataclass
class CreativeSlotInventory:
    """创意槽位库存 — 控制每种事件家族同时存在的上限。"""

    signature_anomalies: int = 5
    living_resources: int = 3
    taboo_rules: int = 4
    macro_crises: int = 3
    forced_convergences: int = 2
    hidden_civilizations: int = 2
    system_irregularities: int = 3

    def remaining_for_family(self, family: str) -> int:
        """返回指定家族当前剩余槽位数。"""
        slot_name = FAMILY_SLOT_MAP.get(family, "")
        if not slot_name or slot_name not in self.__dataclass_fields__:
            return 0
        return max(0, getattr(self, slot_name, 0))

    def consume(self, family: str) -> bool:
        """消费一个槽位，成功返回 True。"""
        slot_name = FAMILY_SLOT_MAP.get(family, "")
        if not slot_name or slot_name not in self.__dataclass_fields__:
            return False
        current = getattr(self, slot_name, 0)
        if current <= 0:
            return False
        setattr(self, slot_name, current - 1)
        return True

    def regenerate(self, turns_elapsed: int) -> None:
        """每经过 10 回合，每个类别回复 1 点。"""
        if turns_elapsed <= 0:
            return
        regen = turns_elapsed // 10
        if regen <= 0:
            return
        for slot_name in self.__dataclass_fields__:
            default_val = self.__dataclass_fields__[slot_name].default
            current = getattr(self, slot_name, 0)
            setattr(self, slot_name, min(current + regen, default_val))

    def to_dict(self) -> Dict[str, int]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# ---------------------------------------------------------------------------
# 1b. EventValueCalculator
# ---------------------------------------------------------------------------

def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """从对象或 Mapping 中安全获取字段值。

    优先尝试属性访问（dataclass / object），失败时回退到字典键访问。
    """
    # Try attribute access first (works for dataclasses and plain objects)
    try:
        return getattr(obj, key)
    except AttributeError:
        pass
    # Fall back to dict-style access
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return default


class EventValueCalculator:
    """六维价值评分 + 四类惩罚的创意事件评估器。

    EventValue =
      25% world_fit + 20% novelty + 20% consequence
    + 15% relevance + 10% social_spread + 10% foreshadowing
    - repeat_penalty - meaningless_weird_penalty - rule_conflict_penalty - slot_exhausted_penalty
    """

    WEIGHTS: Dict[str, float] = {
        "world_fit": 0.25,
        "novelty": 0.20,
        "consequence": 0.20,
        "relevance": 0.15,
        "social_spread": 0.10,
        "foreshadowing": 0.10,
    }

    # -- public API ----------------------------------------------------------

    def score(
        self,
        blueprint: EventBlueprint,
        state: Any,
        world: Mapping[str, Any],
    ) -> EventBlueprint:
        """为蓝图计算综合价值评分并写回 blueprint.value_score。"""
        meta = _get_field(state, "meta", {})
        meta = meta if isinstance(meta, Mapping) else {}
        narrative_state = meta.get("narrative_state", {}) if isinstance(meta.get("narrative_state"), Mapping) else {}
        event_history: List[Mapping[str, Any]] = list(meta.get("event_pattern_history", []))
        pressure: Dict[str, Any] = narrative_state.get("pressure_components", {}) if isinstance(narrative_state.get("pressure_components"), Mapping) else {}
        social = _get_field(state, "data", {})
        social = social if isinstance(social, Mapping) else {}

        dims = {
            "world_fit": self._world_fit(blueprint, world),
            "novelty": self._novelty(blueprint, event_history),
            "consequence": self._consequence(blueprint),
            "relevance": self._relevance(blueprint, pressure),
            "social_spread": self._social_spread(blueprint, social),
            "foreshadowing": self._foreshadowing(blueprint, meta),
        }

        base = sum(self.WEIGHTS[k] * dims[k] for k in self.WEIGHTS)

        # Penalties
        repeat_pen = self._repeat_penalty(blueprint, event_history)
        meaningless_pen = self._meaningless_weird_penalty(blueprint)
        conflict_pen = self._rule_conflict_penalty(blueprint, world)
        slot_pen = self._slot_exhausted_penalty(blueprint, world)

        raw = base - repeat_pen - meaningless_pen - conflict_pen - slot_pen
        blueprint.value_score = rounded(clamp(raw, 0.0, 100.0))
        return blueprint

    # -- dimension helpers ---------------------------------------------------

    def _world_fit(self, bp: EventBlueprint, world: Mapping[str, Any]) -> float:
        """检查事件家族是否匹配世界主题/禁忌领域。"""
        motifs: List[str] = world.get("motifs", []) if isinstance(world.get("motifs"), list) else []
        taboo_domains: List[str] = world.get("taboo_domains", []) if isinstance(world.get("taboo_domains"), list) else []
        theme: str = str(world.get("theme", ""))

        score = 30.0  # baseline

        collision_rules = bp.mechanism_collision
        for rule in collision_rules:
            rule_lower = rule.lower()
            for motif in motifs:
                if motif.lower() in rule_lower or rule_lower in motif.lower():
                    score += 12.0
            for taboo in taboo_domains:
                if taboo.lower() in rule_lower or rule_lower in taboo.lower():
                    score += 10.0

        # Theme-specific bonus
        if theme and bp.family in ("macro_crisis", "rule_anomaly"):
            score += 8.0

        return clamp(score, 0.0, 100.0)

    def _novelty(self, bp: EventBlueprint, history: Sequence[Mapping[str, Any]]) -> float:
        """100 - 近期同家族事件数 × 15。"""
        recent = list(history[-20:])
        same_family_count = sum(
            1 for e in recent
            if str(e.get("family", e.get("event_family", ""))) == bp.family
        )
        return clamp(100.0 - same_family_count * 15.0, 0.0, 100.0)

    def _consequence(self, bp: EventBlueprint) -> float:
        """统计事件影响的状态维度数，越多分越高。"""
        effects = bp.effects_summary
        dimensions = [
            "resources", "relationships", "locations", "rankings",
            "achievements", "inventory", "factions", "npcs",
            "base", "progression", "narrative", "time",
        ]
        hit = sum(1 for d in dimensions if d in effects and effects[d])
        return clamp(hit * 10.0, 0.0, 100.0)

    def _relevance(self, bp: EventBlueprint, pressure: Mapping[str, Any]) -> float:
        """将事件家族与当前最高压力分量匹配。"""
        if not pressure:
            return 40.0

        FAMILY_PRESSURE_MAP: Dict[str, List[str]] = {
            "macro_crisis": ["survival_threat", "resource_scarcity", "world_phase_approaching"],
            "rule_anomaly": ["information_unknown", "failure_accumulation"],
            "living_resource": ["resource_scarcity", "regional_competition"],
            "forced_convergence": ["time_pressure", "interpersonal_conflict", "regional_competition"],
            "taboo_rule": ["information_unknown", "failure_accumulation"],
            "hidden_civilization": ["information_unknown", "world_phase_approaching"],
            "system_irregularity": ["failure_accumulation", "information_unknown"],
        }

        matched_keys = FAMILY_PRESSURE_MAP.get(bp.family, [])
        if not matched_keys:
            return 30.0

        max_pressure = 0.0
        for key in matched_keys:
            val = clamp(number(pressure.get(key, 0)))
            if val > max_pressure:
                max_pressure = val

        return clamp(max_pressure, 0.0, 100.0)

    def _social_spread(self, bp: EventBlueprint, state_data: Mapping[str, Any]) -> float:
        """统计事件涉及的 NPC / 势力 / 公共系统数量。"""
        involved = bp.content_contract.get("involved_entities", [])
        if not isinstance(involved, list):
            involved = []

        npcs = state_data.get("npcs", [])
        factions = state_data.get("factions", [])
        npc_ids = {n.get("id") for n in npcs if isinstance(n, Mapping)}
        faction_ids = {f.get("id") for f in factions if isinstance(f, Mapping)}

        entity_count = len(involved)
        # Check implicit references
        contract_str = str(bp.content_contract).lower()
        for nid in npc_ids:
            if str(nid).lower() in contract_str:
                entity_count += 1
        for fid in faction_ids:
            if str(fid).lower() in contract_str:
                entity_count += 1

        return clamp(entity_count * 18.0, 0.0, 100.0)

    def _foreshadowing(self, bp: EventBlueprint, meta: Mapping[str, Any]) -> float:
        """检查事件是否连接到活跃谜团或开放循环。"""
        mysteries: List[Any] = meta.get("active_mystery_records", [])
        if not isinstance(mysteries, list):
            mysteries_raw = meta.get("active_mysteries", [])
            if isinstance(mysteries_raw, list):
                mysteries = [{"id": m} for m in mysteries_raw]
            else:
                mysteries = []

        open_loops: List[Any] = meta.get("open_loops", [])
        if not isinstance(open_loops, list):
            open_loops = []

        if not mysteries and not open_loops:
            return 20.0

        score = 10.0
        contract_str = str(bp.content_contract).lower()
        for mystery in mysteries:
            mid = str(mystery.get("id", "")) if isinstance(mystery, Mapping) else str(mystery)
            if mid.lower() in contract_str:
                score += 25.0
        for loop in open_loops:
            lid = str(loop.get("id", "")) if isinstance(loop, Mapping) else str(loop)
            if lid.lower() in contract_str:
                score += 20.0

        return clamp(score, 0.0, 100.0)

    # -- penalty helpers -----------------------------------------------------

    def _repeat_penalty(self, bp: EventBlueprint, history: Sequence[Mapping[str, Any]]) -> float:
        """近 10 事件中同家族每次 -12，最多 -60。"""
        recent = list(history[-10:])
        count = sum(
            1 for e in recent
            if str(e.get("family", e.get("event_family", ""))) == bp.family
        )
        return clamp(count * 12.0, 0.0, 60.0)

    @staticmethod
    def _meaningless_weird_penalty(bp: EventBlueprint) -> float:
        """事件没有定义任何规则/约束 → -30。"""
        contract = bp.content_contract
        has_rules = bool(contract.get("hidden_rule") or contract.get("rules") or contract.get("phases") or contract.get("growth_conditions"))
        return 0.0 if has_rules else 30.0

    @staticmethod
    def _rule_conflict_penalty(bp: EventBlueprint, world: Mapping[str, Any]) -> float:
        """事件与已知世界事实矛盾 → -50。"""
        world_facts: List[str] = world.get("established_facts", []) if isinstance(world.get("established_facts"), list) else []
        if not world_facts:
            return 0.0
        contradictions = bp.content_contract.get("contradictions", [])
        if isinstance(contradictions, list) and contradictions:
            return 50.0
        # Heuristic: check if hidden_rule negates any fact keyword
        hidden_rule = str(bp.content_contract.get("hidden_rule", "")).lower()
        for fact in world_facts:
            negated = f"不{fact}" in hidden_rule or f"非{fact}" in hidden_rule or f"no {fact}" in hidden_rule
            if negated:
                return 50.0
        return 0.0

    @staticmethod
    def _slot_exhausted_penalty(bp: EventBlueprint, world: Mapping[str, Any]) -> float:
        """创意槽位为 0 → -100。"""
        creative_slots = world.get("creative_slots", {})
        if not isinstance(creative_slots, Mapping):
            return 0.0
        slot_name = FAMILY_SLOT_MAP.get(bp.family, "")
        if slot_name and slot_name in creative_slots:
            if int(creative_slots.get(slot_name, 1)) <= 0:
                return 100.0
        return 0.0


# ---------------------------------------------------------------------------
# 1c. FrequencyGate
# ---------------------------------------------------------------------------

class FrequencyGate:
    """控制各 tier 在最近窗口内的实际分布是否低于目标。"""

    TARGETS: Dict[str, float] = {
        "normal": 0.50,
        "variant": 0.25,
        "anomaly": 0.15,
        "regional_crisis": 0.08,
        "iconic": 0.02,
    }
    WINDOW: int = 20
    TOLERANCE: float = 0.10  # ±10%

    def should_trigger(self, tier: str, history: Sequence[Mapping[str, Any]]) -> bool:
        """若该 tier 在最近 WINDOW 回合中的实际占比低于目标 - 容差，返回 True。"""
        target = self.TARGETS.get(tier)
        if target is None:
            return True  # unknown tier → allow

        recent = list(history[-self.WINDOW:])
        if not recent:
            return True  # no history → allow

        tier_count = sum(
            1 for e in recent
            if str(e.get("tier", e.get("event_tier", "normal"))) == tier
        )
        actual_ratio = tier_count / len(recent)
        return actual_ratio < (target - self.TOLERANCE)


# ---------------------------------------------------------------------------
# 1d. MechanismCollider
# ---------------------------------------------------------------------------

class MechanismCollider:
    """基于主题机制碰撞模板生成事件蓝图候选。

    每个模板定义参与碰撞的规则、异常类型和社会维度，
    Collider 从中组合出完整的 EventBlueprint。
    """

    COLLISION_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
        "废土列车": [
            {
                "rules": ["列车运行", "车厢所有权"],
                "anomaly": "identity",
                "social": "ranking",
                "family": "rule_anomaly",
                "tier": "anomaly",
                "phases": 2,
                "hook": "一节无主车厢突然亮起了灯",
                "premise": "某节车厢的登记信息被篡改，车主身份指向一个已死之人。",
                "hidden_rule": "车厢所有权变更需经过三次公开声明，否则在下一个停靠站被强制拍卖。",
                "effects": {"relationships": True, "locations": True, "rankings": True},
            },
            {
                "rules": ["燃料", "夜间异常"],
                "anomaly": "invitation",
                "social": "trading",
                "family": "living_resource",
                "tier": "variant",
                "phases": 1,
                "hook": "燃料舱里长出了什么",
                "premise": "一种发光的菌类在燃料舱壁繁殖，吞噬柴油的同时散发出甜味。",
                "growth_conditions": "每次夜间停靠且燃料>30%时增殖",
                "harvest_conditions": "手动清除可回收为低级燃料；高温灼烧会释放有毒气体",
                "attracts_entities": ["流浪商人", "药剂师"],
                "side_effects": ["车厢气味改变", "邻近舱室温度升高"],
                "effects": {"resources": True, "inventory": True, "npcs": True},
            },
            {
                "rules": ["车厢战斗", "公共区域"],
                "anomaly": "convergence",
                "social": "conflict",
                "family": "forced_convergence",
                "tier": "regional_crisis",
                "phases": 3,
                "hook": "餐车里的对峙",
                "premise": "两个势力同时宣称对餐车的管辖权，乘客被迫选边。",
                "event_scale": "整列列车",
                "affected_regions": ["餐车", "相邻车厢", "车顶"],
                "phases_desc": ["紧张升级", "公开冲突", "强制仲裁"],
                "effects": {"relationships": True, "factions": True, "resources": True, "locations": True},
            },
            {
                "rules": ["列车时刻表", "世界边界"],
                "anomaly": "cosmic",
                "social": "belief",
                "family": "macro_crisis",
                "tier": "iconic",
                "phases": 4,
                "hook": "列车驶入了地图上不存在的一段",
                "premise": "窗外出现了不该存在的城市轮廓，列车时刻表上多出一个从未标注的站点。",
                "event_scale": "世界级别",
                "affected_regions": ["车窗外景", "时刻表", "导航系统"],
                "phases_desc": ["景观异常", "设备失灵", "旅客恐慌", "站点抵达"],
                "effects": {"narrative": True, "locations": True, "progression": True, "time": True},
            },
            {
                "rules": ["黑市交易", "车厢改装"],
                "anomaly": "technology",
                "social": "economy",
                "family": "system_irregularity",
                "tier": "variant",
                "phases": 1,
                "hook": "一个不存在的供应商出现在采购清单上",
                "premise": "有人在内部采购系统中注册了一个虚假供应商，却能真实发货。",
                "hidden_rule": "每接受一次发货，供应商权限就扩大一级，三级后获得车厢访问权。",
                "effects": {"resources": True, "inventory": True, "base": True},
            },
        ],
        "巨兽的背脊": [
            {
                "rules": ["巨兽迁徙", "定居点"],
                "anomaly": "geological",
                "social": "territory",
                "family": "macro_crisis",
                "tier": "regional_crisis",
                "phases": 3,
                "hook": "脚下的地面开始倾斜",
                "premise": "巨兽改变迁徙路线，定居点面临滑落深渊的风险。",
                "event_scale": "区域",
                "affected_regions": ["定居点", "悬崖边缘", "水源地"],
                "phases_desc": ["震动加剧", "地基开裂", "紧急迁移"],
                "effects": {"locations": True, "resources": True, "npcs": True, "time": True},
            },
            {
                "rules": ["寄生生态", "采集"],
                "anomaly": "biological",
                "social": "knowledge",
                "family": "living_resource",
                "tier": "anomaly",
                "phases": 2,
                "hook": "背脊上长出了一片从没见过的花",
                "premise": "一种新寄生物种在巨兽背脊繁殖，既有药用价值也可能伤害宿主。",
                "growth_conditions": "每 5 回合自动扩展一个区域",
                "harvest_conditions": "采集需要生物学知识；过度采集会激怒巨兽",
                "attracts_entities": ["草药师", "外来研究团"],
                "side_effects": ["巨兽行为改变", "新区域解锁"],
                "effects": {"resources": True, "locations": True, "progression": True},
            },
            {
                "rules": ["部落联盟", "祭祀"],
                "anomaly": "cultural",
                "social": "diplomacy",
                "family": "rule_anomaly",
                "tier": "variant",
                "phases": 1,
                "hook": "祭祀仪式上出现了不属于任何部落的祭品",
                "premise": "一个神秘祭品出现在共享祭坛上，各部落对其来源争执不休。",
                "hidden_rule": "接受祭品的部落获得临时增益，但必须在三个回合内回献等价物。",
                "effects": {"relationships": True, "factions": True, "rankings": True},
            },
            {
                "rules": ["深渊回声", "记忆"],
                "anomaly": "metaphysical",
                "social": "identity",
                "family": "forced_convergence",
                "tier": "anomaly",
                "phases": 2,
                "hook": "你听到了自己还没说过的话",
                "premise": "深渊回声开始预播未来对话片段，迫使相关者提前做出选择。",
                "event_scale": "个人",
                "affected_regions": ["意识空间", "对话场景"],
                "phases_desc": ["片段回响", "选择锁定"],
                "effects": {"narrative": True, "relationships": True, "time": True},
            },
        ],
        "渊驮": [
            {
                "rules": ["深渊层阶", "重力异常"],
                "anomaly": "spatial",
                "social": "navigation",
                "family": "macro_crisis",
                "tier": "regional_crisis",
                "phases": 3,
                "hook": "脚下的阶梯开始向下延伸，没有尽头",
                "premise": "某层阶的重力场崩溃，向下坍缩为一个无底通道。",
                "event_scale": "多层阶",
                "affected_regions": ["崩溃层阶", "相邻层阶", "深渊核心"],
                "phases_desc": ["重力波动", "结构坍缩", "通道稳定"],
                "effects": {"locations": True, "resources": True, "time": True},
            },
            {
                "rules": ["驮兽契约", "深渊生物"],
                "anomaly": "symbiosis",
                "social": "bonding",
                "family": "living_resource",
                "tier": "variant",
                "phases": 1,
                "hook": "你的驮兽开始主动带你去你没要求的地方",
                "premise": "驮兽感知到深渊中新出现的矿脉，试图引导主人前往。",
                "growth_conditions": "每次成功引导后驮兽感知范围扩大",
                "harvest_conditions": "跟随引导可获得稀有矿物；拒绝则驮兽忠诚度下降",
                "attracts_entities": ["深渊猎人", "矿物商人"],
                "side_effects": ["新区域发现", "驮兽疲劳"],
                "effects": {"resources": True, "locations": True, "progression": True},
            },
            {
                "rules": ["层阶归属", "深渊法则"],
                "anomaly": "legal",
                "social": "authority",
                "family": "rule_anomaly",
                "tier": "anomaly",
                "phases": 2,
                "hook": "这一层的规则变了——而且只有你注意到了",
                "premise": "某层阶的渊驮法则被悄然改写，其他人浑然不觉。",
                "hidden_rule": "知晓新法则的人在此层阶内获得优势，但每次使用会被标记。",
                "effects": {"narrative": True, "locations": True, "achievements": True},
            },
        ],
    }

    # -- public API ----------------------------------------------------------

    def generate_candidates(
        self,
        world: Mapping[str, Any],
        pressure: Mapping[str, Any],
        active_events: Sequence[Mapping[str, Any]],
        social_state: Mapping[str, Any],
    ) -> List[EventBlueprint]:
        """生成 3-5 个事件蓝图候选。"""
        theme = str(world.get("theme", ""))
        templates = self.COLLISION_TEMPLATES.get(theme, self._generic_templates())

        # Filter out families that are already at capacity in active events
        active_families = [
            str(e.get("family", e.get("event_family", "")))
            for e in active_events
            if isinstance(e, Mapping)
        ]

        # Determine highest pressure component for relevance sorting
        highest_pressure_key = ""
        highest_pressure_val = 0.0
        for k, v in (pressure if isinstance(pressure, Mapping) else {}).items():
            val = number(v)
            if val > highest_pressure_val:
                highest_pressure_val = val
                highest_pressure_key = k

        candidates: List[EventBlueprint] = []
        for tmpl in templates:
            family = tmpl.get("family", "rule_anomaly")
            bp = self._build_blueprint(tmpl, theme, active_families)
            if bp is not None:
                candidates.append(bp)

        # If we got fewer than 3, pad with generic templates
        if len(candidates) < 3:
            for tmpl in self._generic_templates():
                if len(candidates) >= 5:
                    break
                bp = self._build_blueprint(tmpl, theme, active_families)
                if bp is not None:
                    candidates.append(bp)

        return candidates[:5]

    # -- private helpers -----------------------------------------------------

    def _build_blueprint(
        self,
        tmpl: Mapping[str, Any],
        theme: str,
        active_families: Sequence[str],
    ) -> Optional[EventBlueprint]:
        """从模板构建 EventBlueprint，失败返回 None。"""
        family = str(tmpl.get("family", "rule_anomaly"))
        tier = str(tmpl.get("tier", "normal"))
        rules = tmpl.get("rules", [])
        if not isinstance(rules, list):
            rules = []

        # Build stable event_id from theme + rules + hook
        id_seed = f"{theme}|{'|'.join(rules)}|{tmpl.get('hook', '')}"
        eid = hashlib.sha256(id_seed.encode("utf-8")).hexdigest()[:12]

        # Build content_contract based on family
        contract: Dict[str, Any] = {
            "visible_hook": tmpl.get("hook", f"{family} 事件"),
            "premise": tmpl.get("premise", ""),
            "theme": theme,
        }

        if family == "rule_anomaly":
            contract["hidden_rule"] = tmpl.get("hidden_rule", "")
        elif family in ("macro_crisis", "forced_convergence"):
            contract["event_scale"] = tmpl.get("event_scale", "local")
            contract["affected_regions"] = tmpl.get("affected_regions", [])
            contract["phases"] = tmpl.get("phases_desc", [])
        elif family == "living_resource":
            contract["growth_conditions"] = tmpl.get("growth_conditions", "")
            contract["harvest_conditions"] = tmpl.get("harvest_conditions", "")
            contract["attracts_entities"] = tmpl.get("attracts_entities", [])
            contract["side_effects"] = tmpl.get("side_effects", [])

        # Collect involved entities
        contract["involved_entities"] = tmpl.get("attracts_entities", [])

        effects = tmpl.get("effects", {})
        if not isinstance(effects, Mapping):
            effects = {}

        phase_count = int(tmpl.get("phases", 1))

        return EventBlueprint(
            event_id=eid,
            family=family,
            tier=tier,
            phase_count=phase_count,
            current_phase=0,
            value_score=0.0,
            content_contract=contract,
            mechanism_collision=list(rules),
            effects_summary=dict(effects),
        )

    @staticmethod
    def _generic_templates() -> List[Dict[str, Any]]:
        """当主题无专属模板时的通用候选。"""
        return [
            {
                "rules": ["资源分配", "社会秩序"],
                "anomaly": "scarcity",
                "social": "competition",
                "family": "macro_crisis",
                "tier": "variant",
                "phases": 2,
                "hook": "公共资源突然枯竭",
                "premise": "一项被广泛依赖的公共资源毫无预兆地断供，各方势力开始争夺替代品。",
                "event_scale": "区域",
                "affected_regions": ["市场", "仓储区", "公共空间"],
                "phases_desc": ["恐慌蔓延", "势力博弈"],
                "effects": {"resources": True, "factions": True, "relationships": True},
            },
            {
                "rules": ["信息流通", "信任"],
                "anomaly": "deception",
                "social": "trust",
                "family": "rule_anomaly",
                "tier": "anomaly",
                "phases": 1,
                "hook": "一条被所有人采信的消息，来源却是空的",
                "premise": "一则无法追溯来源的传言开始影响群体决策。",
                "hidden_rule": "每有一个 NPC 采信传言，其扩散范围翻倍；三次传播后变为既定事实。",
                "effects": {"relationships": True, "narrative": True, "factions": True},
            },
            {
                "rules": ["探索", "未知区域"],
                "anomaly": "discovery",
                "social": "expansion",
                "family": "living_resource",
                "tier": "normal",
                "phases": 1,
                "hook": "一片新区域自行显现",
                "premise": "一个此前不存在的区域出现在已知地图边缘，似乎在缓慢生长。",
                "growth_conditions": "每 8 回合扩展一次边界",
                "harvest_conditions": "探索可获取独特资源；忽视则区域自行消退",
                "attracts_entities": ["探险家", "制图师"],
                "side_effects": ["地图更新", "新路径解锁"],
                "effects": {"locations": True, "resources": True, "progression": True},
            },
            {
                "rules": ["时间", "因果关系"],
                "anomaly": "temporal",
                "social": "urgency",
                "family": "forced_convergence",
                "tier": "regional_crisis",
                "phases": 2,
                "hook": "两件事不可能同时发生——但它们发生了",
                "premise": "两个互斥事件在同一时间窗口内触发，迫使玩家做出取舍。",
                "event_scale": "个人",
                "affected_regions": ["决策空间"],
                "phases_desc": ["冲突显现", "强制选择"],
                "effects": {"time": True, "narrative": True, "relationships": True},
            },
        ]


# ---------------------------------------------------------------------------
# 1e. EventDirector Main Class
# ---------------------------------------------------------------------------

class EventDirector:
    """创意事件导演 — 整合门控、碰撞、评分与注入的主入口。

    典型用法::

        director = EventDirector(engine)
        candidates = director.evaluate_turn()
        # candidates 可直接传入 OptionDirector.compile() 参与选项竞争
    """

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.calculator = EventValueCalculator()
        self.gate = FrequencyGate()
        self.collider = MechanismCollider()

    # -- public API ----------------------------------------------------------

    def evaluate_turn(self) -> List[Dict[str, Any]]:
        """主入口：评估当前回合并返回可注入选项管线的事件候选列表。"""
        state = self.engine.state
        world: Mapping[str, Any] = state.data.get("world", {}) if isinstance(state.data, Mapping) else {}
        creative_slots: Mapping[str, Any] = world.get("creative_slots", {}) if isinstance(world.get("creative_slots"), Mapping) else {}

        if not creative_slots:
            return []

        # 1. Quick gate (O(1))
        if not self._quick_gate(state):
            return []

        # 2. Generate candidates via mechanism collision
        meta = state.meta if isinstance(state.meta, Mapping) else {}
        narrative_state = meta.get("narrative_state", {}) if isinstance(meta.get("narrative_state"), Mapping) else {}
        pressure: Dict[str, Any] = narrative_state.get("pressure_components", {}) if isinstance(narrative_state.get("pressure_components"), Mapping) else {}
        active_events: List[Mapping[str, Any]] = state.data.get("event_queue", []) if isinstance(state.data, Mapping) else []
        social: Dict[str, Any] = {
            "npcs": state.data.get("npcs", []) if isinstance(state.data, Mapping) else [],
            "factions": state.data.get("factions", []) if isinstance(state.data, Mapping) else [],
        }

        candidates = self.collider.generate_candidates(
            dict(world), pressure, active_events, social
        )

        if not candidates:
            return []

        # 3. Score all candidates
        scored = [
            self.calculator.score(bp, state, dict(world))
            for bp in candidates
        ]

        # 4. Filter viable (score > 40)
        viable = [bp for bp in scored if bp.value_score > 40]
        if not viable:
            return []

        # 5. Frequency gate filter
        viable = [
            bp for bp in viable
            if self.gate.should_trigger(
                bp.tier,
                meta.get("event_pattern_history", []) if isinstance(meta.get("event_pattern_history"), list) else [],
            )
        ]
        if not viable:
            return []

        # 6. Select best, consume slot
        best = max(viable, key=lambda bp: bp.value_score)
        slot_kwargs = {
            k: v
            for k, v in creative_slots.items()
            if k in CreativeSlotInventory.__dataclass_fields__
        }
        slot_inv = CreativeSlotInventory(**slot_kwargs)
        if not slot_inv.consume(best.family):
            return []  # No slots available

        # 7. Handle phased events
        if best.phase_count > 1:
            self._inject_phased_event(best, state)

        # 8. Convert to candidate dict for option pipeline
        return [self._blueprint_to_candidate(best)]

    # -- private helpers -----------------------------------------------------

    @staticmethod
    def _quick_gate(state: Any) -> bool:
        """O(1) 确定性门控 — 约 50% 的回合通过。

        使用回合编号的模运算：turn % 3 == 0 或 turn % 4 == 0 时触发。
        """
        meta = state.meta if isinstance(state.meta, Mapping) else {}
        turn = int(meta.get("current_turn", 0))
        return turn % 3 == 0 or turn % 4 == 0

    @staticmethod
    def _inject_phased_event(blueprint: EventBlueprint, state: Any) -> None:
        """将多阶段事件写入 event_queue，复用已有触发机制。"""
        meta = state.meta if isinstance(state.meta, Mapping) else {}
        current_turn = int(meta.get("current_turn", 0))
        event_entry: Dict[str, Any] = {
            "id": f"director_{blueprint.event_id}",
            "status": "pending",
            "trigger_conditions": {
                "turn": current_turn + 1,
                "director_event": True,
            },
            "phase_count": blueprint.phase_count,
            "current_phase": 0,
            "content_contract": deepcopy(blueprint.content_contract),
            "family": blueprint.family,
            "tier": blueprint.tier,
        }
        if isinstance(state.data, Mapping):
            state.data.setdefault("event_queue", []).append(event_entry)

    @staticmethod
    def _blueprint_to_candidate(blueprint: EventBlueprint) -> Dict[str, Any]:
        """将 EventBlueprint 转换为 game_turn.py 选项管线所需的候选字典。"""
        return {
            "category": "director_event",
            "label": blueprint.content_contract.get(
                "visible_hook", f"{blueprint.family} 事件"
            ),
            "description": blueprint.content_contract.get("premise", ""),
            "action": {
                "action_id": f"director-{blueprint.event_id}",
                "type": "DIRECTOR_EVENT",
                "event_family": blueprint.family,
                "event_tier": blueprint.tier,
                "phase": blueprint.current_phase,
                "content_contract": deepcopy(blueprint.content_contract),
            },
        }

    # -- external validation & presentation dedup ----------------------------

    def evaluate_external_validation_opportunity(self) -> Optional[Dict[str, Any]]:
        """Detect when 'external validation' payoff is appropriate.

        Trigger conditions:
        - Protagonist has shown recent growth (level up, skill gain, etc.)
        - External parties still underestimate protagonist
        - Credible observer exists (high-level NPC, professional, etc.)
        - Behavioral evidence available (observer can see protagonist in action)
        - Social consequence is meaningful (observer's behavior change affects story)

        Returns payoff_function dict if appropriate, None otherwise.
        """
        state = self.engine.state
        meta = state.meta if isinstance(state.meta, Mapping) else {}

        # Check recent protagonist growth
        recent_events = state.event_history()[-20:]
        growth_events = [
            e for e in recent_events
            if e.get("record", {}).get("type") in (
                "LEVEL_UP", "SKILL_GAIN", "TALENT_CHOICE",
            )
        ]

        if len(growth_events) < 2:
            return None  # Not enough recent growth

        # Check for underestimation (observer's prior belief vs reality)
        observations = meta.get("observations", [])
        if not isinstance(observations, list):
            observations = []
        recent_observations = [
            o for o in observations
            if o.get("turn", 0) >= state.current_turn - 5
        ]

        # Check if credible observer exists
        npcs: Any = state.data.get("npcs", {}) if isinstance(state.data, Mapping) else {}
        peer_players: Any = (
            state.data.get("peer_players", []) if isinstance(state.data, Mapping) else []
        )

        credible_observers: List[str] = []
        if isinstance(npcs, dict):
            for npc_id, npc_data in npcs.items():
                if not isinstance(npc_data, dict):
                    continue
                # High-level NPCs or professionals are credible observers
                if npc_data.get("level", 1) >= 5 or npc_data.get("profession") in (
                    "鉴定师", "望气师", "professional_judge",
                ):
                    credible_observers.append(npc_id)

        if isinstance(peer_players, list):
            for peer in peer_players:
                if not isinstance(peer, dict):
                    continue
                if peer.get("level", 1) >= 5 or peer.get("rarity_score", 0) >= 70:
                    peer_id = peer.get("id")
                    if peer_id:
                        credible_observers.append(peer_id)

        if not credible_observers:
            return None  # No credible observers available

        # Check if protagonist is currently underestimated
        protagonist_power = self._estimate_protagonist_power()

        underestimated = False
        for obs in recent_observations:
            if not isinstance(obs, Mapping):
                continue
            if obs.get("target_id") == "protagonist":
                prior_belief = obs.get("prior_belief", {})
                prior_estimate = (
                    prior_belief.get("estimate", "unknown")
                    if isinstance(prior_belief, Mapping)
                    else "unknown"
                )
                if prior_estimate in ("ordinary", "moderately_strong", "ordinary_elite"):
                    if protagonist_power > 70:  # Protagonist is actually very strong
                        underestimated = True
                        break

        if not underestimated:
            return None  # Not currently underestimated

        # All conditions met - return payoff function
        return {
            "type": "external_validation",
            "reveal_subject": "protagonist_capability",
            "observer_credibility": "high",
            "prior_underestimation": "high",
            "social_consequence": "meaningful",
            "trigger_conditions": {
                "protagonist_recent_growth": "high",
                "external_underestimation": "high",
                "credible_observer_exists": True,
                "behavioral_evidence_available": True,
            },
            "allowed_reveals": [
                "protagonist_far_exceeds_observer",
                "regional_standards_cannot_evaluate",
            ],
            "forbidden_reveals": [
                "protagonist_all_skills",
                "hidden_talent_names",
                "precise_weaknesses",
            ],
            "expected_aftermath": [
                "observer_strategy_changed",
                "information_may_spread",
            ],
        }

    def _estimate_protagonist_power(self) -> float:
        """Estimate protagonist's current power level (0-100)."""
        state = self.engine.state
        player = state.player if isinstance(state.player, Mapping) else {}

        # Simple power estimation based on level, attributes, and equipment
        level = int(player.get("level", 1))
        attributes = player.get("attributes", {})

        base_power = level * 10
        attribute_bonus = (
            sum(v for v in attributes.values() if isinstance(v, (int, float)))
            if isinstance(attributes, dict)
            else 0
        )

        return min(100.0, float(base_power + attribute_bonus))

    def check_presentation_repetition(self, surface_method: str) -> float:
        """Check how recently this surface method was used.

        Returns penalty score (0-50): higher = more recently used = higher penalty.
        """
        meta = (
            self.engine.state.meta if isinstance(self.engine.state.meta, Mapping) else {}
        )
        presentation_history = meta.get("presentation_history", [])
        if not isinstance(presentation_history, list):
            presentation_history = []

        recent_uses = [
            p for p in presentation_history[-10:]
            if isinstance(p, Mapping) and p.get("surface_method") == surface_method
        ]

        if not recent_uses:
            return 0.0

        # More recent = higher penalty
        turns_since_last = (
            self.engine.state.current_turn - recent_uses[-1].get("turn", 0)
        )

        if turns_since_last <= 5:
            return 50.0  # Very recently used
        elif turns_since_last <= 15:
            return 30.0  # Somewhat recently used
        else:
            return 10.0  # Used but not too recently
