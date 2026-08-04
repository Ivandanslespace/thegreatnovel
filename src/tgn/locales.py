"""Fixed UTF-8 locale labels. Rules and numbers are locale-independent."""
from __future__ import annotations

SUPPORTED_LOCALES = ("zh-CN", "fr-FR", "en", "ar")
DEFAULT_LOCALE = "zh-CN"

_LABELS = {
    "zh-CN": {
        "status": "状态", "turn": "回合", "tier": "层级", "energy": "体力", "insight": "洞察",
        "core": "核心资源", "influence": "影响力", "observe_rule": "观察规则", "gather_resource": "获取/生产",
        "convert_leverage": "杠杆转化", "negotiate": "谈判", "organize": "组织行动", "exploit_rule": "利用规则",
        "ascend": "跃迁", "recover": "恢复", "finished": "已结束", "active": "进行中", "start": "序章开始",
        "reason_always": "始终可用", "reason_basic": "基础行动", "reason_rule": "已掌握规则", "reason_threshold": "达到门槛", "failure_reason": "掷骰低于阈值", "reason_unavailable": "行动不可用", "undiscovered": "尚未发现",
    },
    "fr-FR": {
        "status": "État", "turn": "Tour", "tier": "Palier", "energy": "Énergie", "insight": "Intuition",
        "core": "Ressource centrale", "influence": "Influence", "observe_rule": "Observer la règle", "gather_resource": "Obtenir/produire",
        "convert_leverage": "Convertir le levier", "negotiate": "Négocier", "organize": "Organiser", "exploit_rule": "Exploiter la règle",
        "ascend": "Transcender", "recover": "Récupérer", "finished": "Terminé", "active": "En cours", "start": "Prologue",
        "reason_always": "Toujours disponible", "reason_basic": "Action de base", "reason_rule": "Règle connue", "reason_threshold": "Seuil atteint", "failure_reason": "Jet sous le seuil", "reason_unavailable": "Action indisponible", "undiscovered": "Pas encore découvert",
    },
    "en": {
        "status": "Status", "turn": "Turn", "tier": "Tier", "energy": "Energy", "insight": "Insight",
        "core": "Core resource", "influence": "Influence", "observe_rule": "Observe rule", "gather_resource": "Acquire/produce",
        "convert_leverage": "Convert leverage", "negotiate": "Negotiate", "organize": "Organize", "exploit_rule": "Exploit rule",
        "ascend": "Ascend", "recover": "Recover", "finished": "Finished", "active": "Active", "start": "Prologue begins",
        "reason_always": "Always available", "reason_basic": "Basic action", "reason_rule": "Rule known", "reason_threshold": "Threshold reached", "failure_reason": "Roll below threshold", "reason_unavailable": "Action unavailable", "undiscovered": "Not yet discovered",
    },
    "ar": {
        "status": "الحالة", "turn": "الدور", "tier": "المستوى", "energy": "الطاقة", "insight": "البصيرة",
        "core": "المورد الأساسي", "influence": "التأثير", "observe_rule": "مراقبة القاعدة", "gather_resource": "اكتساب/إنتاج",
        "convert_leverage": "تحويل الرافعة", "negotiate": "تفاوض", "organize": "تنظيم", "exploit_rule": "استغلال القاعدة",
        "ascend": "ارتقاء", "recover": "استعادة", "finished": "منتهٍ", "active": "نشط", "start": "بداية المقدمة",
        "reason_always": "متاح دائماً", "reason_basic": "إجراء أساسي", "reason_rule": "القاعدة معروفة", "reason_threshold": "تم بلوغ العتبة", "failure_reason": "الرمي أدنى من العتبة", "reason_unavailable": "الإجراء غير متاح", "undiscovered": "لم يُكتشف بعد",
    },
}

def normalize_locale(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    raw = str(locale).strip().replace("_", "-")
    low = raw.lower()
    aliases = {"zh": "zh-CN", "zh-cn": "zh-CN", "cn": "zh-CN", "fr": "fr-FR", "fr-fr": "fr-FR", "en-us": "en", "en-gb": "en", "en": "en", "ar": "ar", "ar-sa": "ar"}
    if low in aliases:
        return aliases[low]
    if raw in SUPPORTED_LOCALES:
        return raw
    raise ValueError(f"unsupported locale: {locale!r}; expected one of {SUPPORTED_LOCALES}")

def label(locale: str, key: str) -> str:
    return _LABELS[normalize_locale(locale)].get(key, key)

def labels(locale: str) -> dict[str, str]:
    return dict(_LABELS[normalize_locale(locale)])
