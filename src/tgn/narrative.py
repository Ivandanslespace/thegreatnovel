"""Deterministic narrative projection constrained to public event facts."""
from __future__ import annotations

import copy
from typing import Any

from .engine import available_actions
from .locales import normalize_locale

MAX_POLISHED_CHARS = 20000

_ACTION_TEXT = {
    "zh-CN": {"observe_rule": "观察了规则", "gather_resource": "获取了资源", "convert_leverage": "尝试转化杠杆", "negotiate": "进行了谈判", "organize": "组织了一次行动", "exploit_rule": "利用已知规则", "recover": "恢复体力", "ascend": "完成层级跃迁"},
    "fr-FR": {"observe_rule": "a observé la règle", "gather_resource": "a obtenu une ressource", "convert_leverage": "a tenté de convertir le levier", "negotiate": "a négocié", "organize": "a organisé une action", "exploit_rule": "a exploité la règle connue", "recover": "a récupéré", "ascend": "a franchi un palier"},
    "en": {"observe_rule": "observed the rule", "gather_resource": "secured a resource", "convert_leverage": "attempted to convert the leverage", "negotiate": "negotiated", "organize": "organized an action", "exploit_rule": "used the known rule", "recover": "recovered", "ascend": "crossed a tier"},
    "ar": {"observe_rule": "راقب القاعدة", "gather_resource": "حصل على مورد", "convert_leverage": "حاول تحويل الرافعة", "negotiate": "تفاوض", "organize": "نظّم إجراءً", "exploit_rule": "استغل القاعدة المعروفة", "recover": "استعاد قوته", "ascend": "عبر مستوى"},
}
_TURN_TITLE = {"zh-CN":"第{n}回", "fr-FR":"Tour {n}", "en":"Turn {n}", "ar":"الدور {n}"}
_KEYS = {
    "zh-CN": {"energy":"体力","max_energy":"体力上限","insight":"洞察","core":"核心资源","influence":"影响力","vitality":"生命","risk_exposure":"风险敞口","organization":"组织","rule_use":"规则利用","trust":"信任","resonance":"共振"},
    "fr-FR": {"energy":"énergie","max_energy":"énergie maximale","insight":"intuition","core":"ressource","influence":"influence","vitality":"vitalité","risk_exposure":"exposition","organization":"organisation","rule_use":"maîtrise des règles","trust":"confiance","resonance":"résonance"},
    "en": {"energy":"energy","max_energy":"maximum energy","insight":"insight","core":"core resource","influence":"influence","vitality":"vitality","risk_exposure":"risk exposure","organization":"organization","rule_use":"rule use","trust":"trust","resonance":"resonance"},
    "ar": {"energy":"الطاقة","max_energy":"الحد الأقصى للطاقة","insight":"البصيرة","core":"المورد الأساسي","influence":"التأثير","vitality":"الحيوية","risk_exposure":"التعرض للمخاطر","organization":"التنظيم","rule_use":"استخدام القواعد","trust":"الثقة","resonance":"الرنين"},
}

def _changes(locale: str, gain: dict, loss: dict, cost: dict | None = None) -> str:
    labels = _KEYS[locale]
    vals = []
    for k,v in (cost or {}).items():
        if v: vals.append(f"{labels.get(k,k)} {'+' if k == 'risk_exposure' else '-'}{v}")
    for k,v in gain.items():
        if v: vals.append(f"{labels.get(k,k)} +{v}")
    for k,v in loss.items():
        if v: vals.append(f"{labels.get(k,k)} -{v}")
    return ", ".join(vals) if vals else {"zh-CN":"结果已记录", "fr-FR":"Résultat enregistré", "en":"The result is recorded", "ar":"سُجّلت النتيجة"}[locale]


def _world_response(locale: str, facts: dict) -> str:
    response = facts.get("world_response") or {}
    rival = response.get("rival") or {}
    if not rival:
        return ""
    progress = rival.get("progress", 0)
    threat = rival.get("threat", 0)
    windows = len(response.get("opportunities") or [])
    templates = {
        "zh-CN": f"与此同时，竞争者推进到{progress}，威胁升至{threat}；仍有{windows}个机会窗口。",
        "fr-FR": f"Pendant ce temps, le rival atteint {progress}, la menace {threat}; {windows} fenêtre(s) restent ouvertes.",
        "en": f"Meanwhile, the rival reaches {progress}, threat {threat}; {windows} opportunity window(s) remain.",
        "ar": f"وفي الوقت نفسه بلغ تقدم المنافس {progress}، والتهديد {threat}؛ وبقيت {windows} نافذة فرصة.",
    }
    return templates[locale]

def _facts(event: Any) -> dict:
    return copy.deepcopy(getattr(event, "public_facts", {}) or {})

def fallback_text(locale: str, event: Any, campaign: Any) -> str:
    """Render a close-third-person chapter using only public facts."""
    loc = normalize_locale(locale); f = _facts(event); action = f.get("action_id") or getattr(event, "action_id", None)
    turn = int(f.get("turn", getattr(event, "turn", 0))); roll = f.get("roll"); success = f.get("success")
    gain = f.get("gained") or {}; loss = f.get("loss") or {}; cost = f.get("cost") or {}
    if loc == "zh-CN":
        if getattr(event, "kind", "") == "genesis": return f"序章｜{f.get('title', campaign.world.get('title', '新世界'))}\n{campaign.premise}在远处形成边界。她先记下能够看见的地标与风险，决定从一条可验证的线索开始。"
        if getattr(event, "kind", "") == "finish": return f"终章｜她停在第{f.get('tier', campaign.tier)}层，控制分数为{f.get('control_score', 0)}。世界没有替她收尾；留下的关系、代价与未完窗口，成为下一段历史的入口。"
        verb = _ACTION_TEXT[loc].get(action, action or "行动")
        outcome = "行动成功" if success else "行动失败，代价已经落下"
        detail = ("变化：" + _changes(loc, gain, loss, cost))
        return f"第{turn}回｜她{verb}。眼前的威胁与机会迫使她作出单一判断，于是行动落地；{outcome}（掷骰{roll}）。{detail}。{_world_response(loc, f)}"
    if loc == "fr-FR":
        if getattr(event, "kind", "") == "genesis": return f"Prologue | {f.get('title', campaign.world.get('title','Nouveau monde'))}\n{campaign.premise}. Elle note les repères visibles et choisit une piste vérifiable."
        if getattr(event, "kind", "") == "finish": return f"Épilogue | Elle s'arrête au palier {f.get('tier', campaign.tier)}, avec un contrôle de {f.get('control_score', 0)}. Les conséquences restent dans le monde."
        verb = _ACTION_TEXT[loc].get(action, action or "a agi"); outcome = "L'action réussit" if success else "L'action échoue et le coût demeure"; detail = "Variation: " + _changes(loc, gain, loss, cost)
        return f"Tour {turn} | Elle {verb}. Une menace ou une occasion impose un seul choix; elle tranche. {outcome} (jet {roll}). {detail}. {_world_response(loc, f)}"
    if loc == "en":
        if getattr(event, "kind", "") == "genesis": return f"Prologue | {f.get('title', campaign.world.get('title','New world'))}\n{campaign.premise}. She marks the visible landmarks and chooses one testable lead."
        if getattr(event, "kind", "") == "finish": return f"Epilogue | She stops at tier {f.get('tier', campaign.tier)}, control {f.get('control_score', 0)}. Consequences remain in the world."
        verb = _ACTION_TEXT[loc].get(action, action or "acted"); outcome = "The action succeeds" if success else "The action fails, and the cost remains"; detail = "Change: " + _changes(loc, gain, loss, cost)
        return f"Turn {turn} | She {verb}. A threat or opening demands one judgment, and she commits. {outcome} (roll {roll}). {detail}. {_world_response(loc, f)}"
    if getattr(event, "kind", "") == "genesis": return f"المقدمة | {f.get('title', campaign.world.get('title','عالم جديد'))}\n{campaign.premise}. تسجل المعالم الظاهرة وتختار دليلاً قابلاً للاختبار."
    if getattr(event, "kind", "") == "finish": return f"الخاتمة | تتوقف عند المستوى {f.get('tier', campaign.tier)}، والسيطرة {f.get('control_score', 0)}. تبقى العواقب في العالم."
    verb = _ACTION_TEXT[loc].get(action, action or "تحركت"); outcome = "نجح الإجراء" if success else "فشل الإجراء وبقيت الكلفة"; detail = "التغيير: " + _changes(loc, gain, loss, cost)
    return f"الدور {turn} | {verb}. يفرض التهديد أو الفرصة حكماً واحداً؛ فتلتزم به. {outcome} (الرمي {roll}). {detail}. {_world_response(loc, f)}"

def narration_brief(campaign: Any, event: Any | None = None) -> dict:
    event = event or (campaign.events[-1] if campaign.events else None)
    public = _facts(event) if event else {}
    return {"turn": int(getattr(event, "turn", campaign.turn) if event else campaign.turn), "authoritative_public_facts": public, "allowed_actions": [a["action_id"] for a in available_actions(campaign)], "style_constraints": ["close third person", "one action and causal closure", "threat/opportunity -> judgment -> action -> quantified result -> consequence -> hook"], "forbidden_claims": ["hidden event facts", "hidden campaign state", "unobserved core rule", "unearned rewards, people, deaths, or relationships"]}

def project_chapters(campaign: Any) -> list[dict]:
    """Upgrade engine placeholders while preserving hashes and public facts."""
    existing = {int(ch.get("turn", -1)): ch for ch in (campaign.chapters or [])}
    out = []
    for event in campaign.events:
        ch = dict(existing.get(int(event.turn), {})); ch.pop("text", None); public = _facts(event); title = public.get("title") or ({"zh-CN":"序章", "fr-FR":"Prologue", "en":"Prologue", "ar":"المقدمة"}[campaign.locale] if event.kind == "genesis" else ({"zh-CN":"终章", "fr-FR":"Épilogue", "en":"Epilogue", "ar":"الخاتمة"}[campaign.locale] if event.kind == "finish" else _TURN_TITLE[campaign.locale].format(n=event.turn)))
        fallback = fallback_text(campaign.locale, event, campaign)
        ch.update({"turn": int(event.turn), "title": title, "fallback_text": fallback, "polished_text": ch.get("polished_text"), "public_facts": public, "event_hash": event.event_hash})
        out.append(ch)
    campaign.chapters = out
    return out

def apply_polished(campaign: Any, turn: int, text: str) -> dict:
    if not isinstance(text, str) or not text.strip(): raise ValueError("narration text must not be empty")
    if len(text) > MAX_POLISHED_CHARS: raise ValueError("narration text is too large")
    project_chapters(campaign)
    for ch in campaign.chapters:
        if int(ch["turn"]) == int(turn): ch["polished_text"] = text; return ch
    raise ValueError(f"unknown turn: {turn}")
