from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from novel_authoring.canon.projection import CanonProjection
from novel_authoring.config import Settings
from novel_authoring.contracts.draft import DraftOutput, DraftStateChange
from novel_authoring.domain.models import ContinuationMode, NarrativeFunction, Severity
from novel_authoring.metrics.formulas import (
    character_fit,
    payoff_cooldown_allowed,
    style_fit,
)
from novel_authoring.planning.models import ChapterContract
from novel_authoring.validation.models import (
    ValidationFinding,
    ValidationReport,
    ValidatorName,
)


@dataclass(frozen=True)
class ValidationContext:
    draft: DraftOutput
    contract: ChapterContract
    projection: CanonProjection
    settings: Settings


def _finding(
    code: str,
    message: str,
    *,
    severity: Severity = Severity.ERROR,
    evidence: list[str] | None = None,
    location: str | None = None,
    suggested_fix: str | None = None,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=severity,
        message=message,
        evidence=evidence or [],
        location=location,
        suggested_fix=suggested_fix,
    )


_SEVERITY_RANK = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.ERROR: 2,
    Severity.FATAL: 3,
}


def _report(
    validator: ValidatorName,
    findings: list[ValidationFinding],
    measurements: dict[str, Any] | None = None,
) -> ValidationReport:
    blocking = any(
        finding.severity in {Severity.ERROR, Severity.FATAL} for finding in findings
    )
    severity = max(
        (finding.severity for finding in findings),
        key=lambda item: _SEVERITY_RANK[item],
        default=Severity.INFO,
    )
    return ValidationReport(
        validator=validator,
        passed=not blocking,
        severity=severity,
        findings=findings,
        measurements=measurements or {},
    )


def _changes(context: ValidationContext, kind: str) -> list[DraftStateChange]:
    return [change for change in context.draft.state_changes if change.kind == kind]


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}


def validate_canon(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    mode = context.contract.mode
    for change in _changes(context, "fact"):
        payload = _clean_payload(change.payload)
        existing = context.projection.facts.get(change.record_id)
        revision_marker = bool(
            payload.get("supersedes_fact_id") or payload.get("revision_reason")
        )
        if (
            existing is not None
            and _clean_payload(existing) != payload
            and (mode is not ContinuationMode.EXPLICIT_REVISION or not revision_marker)
        ):
            findings.append(
                _finding(
                    "CANON_FACT_OVERWRITE",
                    f"事实 {change.record_id} 与当前正史值不一致。",
                    evidence=[json.dumps(_clean_payload(existing), ensure_ascii=False)],
                    location=f"state_changes:{change.record_id}",
                    suggested_fix="沿用正史值，或切换 explicit_revision 并提供修订来源。",
                )
            )
        subject = payload.get("subject_id")
        predicate = payload.get("predicate")
        if predicate is not None:
            for fact_id, fact in context.projection.facts.items():
                if fact_id == change.record_id:
                    continue
                if fact.get("subject_id") == subject and fact.get("predicate") == predicate:
                    old_object = fact.get("object", fact.get("object_json"))
                    new_object = payload.get("object", payload.get("object_json"))
                    if old_object != new_object and (
                        mode is not ContinuationMode.EXPLICIT_REVISION
                        or not revision_marker
                    ):
                        findings.append(
                            _finding(
                                "CANON_PREDICATE_CONFLICT",
                                f"{subject!s}.{predicate!s} 已有不同正史值（{fact_id}）。",
                                evidence=[json.dumps(old_object, ensure_ascii=False)],
                                location=f"state_changes:{change.record_id}",
                            )
                        )
        if bool(payload.get("retcon")) and mode is not ContinuationMode.EXPLICIT_REVISION:
            findings.append(
                _finding(
                    "SILENT_RETCON",
                    "faithful/constrained 模式禁止把 retcon 静默写入正史。",
                    location=f"state_changes:{change.record_id}",
                )
            )
    return _report("Canon Validator", findings)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def validate_timeline(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    existing_orders = [
        number
        for item in context.projection.timeline.values()
        if (number := _number(item.get("order_key"))) is not None
    ]
    latest_order = max(existing_orders, default=None)
    for change in _changes(context, "timeline"):
        payload = change.payload
        start = _number(payload.get("story_time_start"))
        end = _number(payload.get("story_time_end"))
        order = _number(payload.get("order_key"))
        if start is not None and end is not None and end < start:
            findings.append(
                _finding(
                    "TIMELINE_REVERSED_RANGE",
                    "story_time_end 早于 story_time_start。",
                    location=f"state_changes:{change.record_id}",
                )
            )
        is_non_linear = bool(payload.get("parallel") or payload.get("flashback"))
        if (
            latest_order is not None
            and order is not None
            and order < latest_order
            and not is_non_linear
        ):
            findings.append(
                _finding(
                    "TIMELINE_ORDER_ROLLBACK",
                    f"order_key={order:g} 早于当前正史 {latest_order:g}，且未声明并行或回忆。",
                    location=f"state_changes:{change.record_id}",
                )
            )
        after_id = payload.get("sequence_after")
        if after_id and str(after_id) not in context.projection.timeline:
            findings.append(
                _finding(
                    "TIMELINE_UNKNOWN_PREDECESSOR",
                    f"sequence_after 指向未知时间线记录 {after_id}。",
                    location=f"state_changes:{change.record_id}",
                )
            )
    return _report(
        "Timeline Validator", findings, {"latest_order_key": latest_order}
    )


def validate_knowledge(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    known: set[tuple[str, str]] = set()
    for edge in context.projection.knowledge.values():
        state = str(edge.get("knowledge_state", "KNOWN")).upper()
        if state not in {"UNKNOWN", "FALSE", "DENIED"}:
            known.add((str(edge.get("character_id")), str(edge.get("fact_id"))))
    learned = {
        (str(change.payload.get("character_id")), str(change.payload.get("fact_id")))
        for change in _changes(context, "knowledge")
    }
    for claim in context.draft.knowledge_claims:
        pair = (claim.character_id, claim.fact_id)
        if claim.basis == "already_known" and pair not in known:
            findings.append(
                _finding(
                    "KNOWLEDGE_NOT_ESTABLISHED",
                    f"{claim.character_id} 的知识 {claim.fact_id} 未在正史建立。",
                    location="knowledge_claims",
                    suggested_fix="改为在本章可观察地获知，并提交 knowledge state change。",
                )
            )
        if claim.basis == "learned_in_draft" and pair not in learned:
            findings.append(
                _finding(
                    "KNOWLEDGE_LEARNING_NOT_RECORDED",
                    f"{claim.character_id} 在本章获知 {claim.fact_id}，但没有知识边状态变化。",
                    location="knowledge_claims",
                )
            )
    return _report("Knowledge Validator", findings)


def validate_character(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    score: float | None = None
    try:
        config = context.settings.metrics["character_fit"]
        score = character_fit(context.draft.character_fit_inputs, config)
        minimum = float(config["minimum"])
        if score < minimum:
            findings.append(
                _finding(
                    "CHARACTER_FIT_BELOW_MINIMUM",
                    f"人物契合度 {score:.2f} 低于硬门 {minimum:.2f}。",
                    location="character_fit_inputs",
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        findings.append(
            _finding(
                "CHARACTER_FIT_INPUT_INVALID",
                f"人物契合度输入无效：{exc}",
                location="character_fit_inputs",
            )
        )
    for violation in context.draft.character_bottom_line_violations:
        findings.append(
            _finding(
                "CHARACTER_BOTTOM_LINE",
                violation,
                severity=Severity.FATAL,
                location="character_bottom_line_violations",
            )
        )
    return _report("Character Validator", findings, {"character_fit": score})


def validate_economy_power(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    for change in _changes(context, "resource"):
        payload = change.payload
        before = _number(payload.get("before_quantity"))
        delta = _number(payload.get("delta"))
        after = _number(payload.get("after_quantity", payload.get("quantity")))
        existing = context.projection.resources.get(change.record_id)
        existing_quantity = (
            None if existing is None else _number(existing.get("quantity"))
        )
        if (
            before is not None
            and existing_quantity is not None
            and abs(before - existing_quantity) > 1e-9
        ):
            findings.append(
                _finding(
                    "RESOURCE_BASE_MISMATCH",
                    f"资源起点 {before:g} 与正史 {existing_quantity:g} 不一致。",
                    location=f"state_changes:{change.record_id}",
                )
            )
        if (
            before is not None
            and delta is not None
            and after is not None
            and abs(before + delta - after) > 1e-9
        ):
            findings.append(
                _finding(
                    "RESOURCE_NOT_CONSERVED",
                    "before_quantity + delta 不等于 after_quantity。",
                    location=f"state_changes:{change.record_id}",
                )
            )
        if after is not None and after < 0:
            findings.append(
                _finding(
                    "RESOURCE_NEGATIVE",
                    "资源结余不得为负。",
                    location=f"state_changes:{change.record_id}",
                )
            )
        increased = after is not None and after > (before if before is not None else 0)
        if increased and not (payload.get("source") or payload.get("causal_source")):
            findings.append(
                _finding(
                    "RESOURCE_SOURCE_MISSING",
                    "资源增加缺少 source/causal_source。",
                    location=f"state_changes:{change.record_id}",
                )
            )
    for change in _changes(context, "capability"):
        payload = change.payload
        absolute = _number(payload.get("absolute_capacity"))
        effective = _number(payload.get("effective_capacity"))
        if absolute is not None and absolute < 0 or effective is not None and effective < 0:
            findings.append(
                _finding(
                    "CAPABILITY_NEGATIVE",
                    "能力值不得为负。",
                    location=f"state_changes:{change.record_id}",
                )
            )
        if absolute is not None and effective is not None and effective > absolute:
            findings.append(
                _finding(
                    "CAPABILITY_EXCEEDS_ABSOLUTE",
                    "effective_capacity 不得高于 absolute_capacity。",
                    location=f"state_changes:{change.record_id}",
                )
            )
        if bool(payload.get("increased")) and not (
            payload.get("source") or payload.get("causal_source")
        ):
            findings.append(
                _finding(
                    "CAPABILITY_SOURCE_MISSING",
                    "战力提升缺少可追溯来源。",
                    location=f"state_changes:{change.record_id}",
                )
            )
    return _report("Economy / Power Validator", findings)


def _quotes_in_prose(
    prose: str,
    quotes: list[str],
    key: str,
    findings: list[ValidationFinding],
) -> None:
    if not quotes:
        findings.append(
            _finding(
                "CONTRACT_EVIDENCE_EMPTY",
                f"合同证据 {key} 为空。",
                location=f"contract_evidence:{key}",
            )
        )
    for quote in quotes:
        if quote not in prose:
            findings.append(
                _finding(
                    "EVIDENCE_NOT_IN_PROSE",
                    f"证据短句不在正文中：{quote}",
                    evidence=[quote],
                    location=key,
                )
            )


def validate_contract(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    required = {
        "required_irreversible_change",
        "required_cost",
        "ending_state",
        *(f"commit:{item}" for item in context.contract.commit_updates),
    }
    for key in sorted(required):
        quotes = context.draft.contract_evidence.get(key)
        if quotes is None:
            findings.append(
                _finding(
                    "CONTRACT_REQUIREMENT_MISSING",
                    f"正文输出未为合同要求 {key} 提供证据。",
                    location="contract_evidence",
                )
            )
            continue
        _quotes_in_prose(context.draft.prose_markdown, quotes, key, findings)
    for change in context.draft.state_changes:
        _quotes_in_prose(
            context.draft.prose_markdown,
            change.evidence_quotes,
            f"state_changes:{change.record_id}",
            findings,
        )
    return _report(
        "Contract Validator",
        findings,
        {"requirements_checked": len(required)},
    )


def validate_debt(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    debt = context.contract.narrative_debt
    advance_value = debt.get("advance", [])
    pay_value = debt.get("fully_pay", [])
    allowed_value = debt.get("new_major_hooks_allowed", 0)
    required_advance = (
        {str(item) for item in advance_value}
        if isinstance(advance_value, list)
        else set()
    )
    required_pay = (
        {str(item) for item in pay_value} if isinstance(pay_value, list) else set()
    )
    missing_advance = required_advance - set(context.draft.promises_advanced)
    missing_pay = required_pay - set(context.draft.promises_paid)
    if missing_advance:
        findings.append(
            _finding(
                "DEBT_ADVANCE_MISSING",
                f"未推进合同承诺：{sorted(missing_advance)}",
                location="promises_advanced",
            )
        )
    if missing_pay:
        findings.append(
            _finding(
                "DEBT_PAYOFF_MISSING",
                f"未兑现合同承诺：{sorted(missing_pay)}",
                location="promises_paid",
            )
        )
    allowed = int(allowed_value) if isinstance(allowed_value, int) else 0
    if context.draft.new_major_hooks > allowed:
        findings.append(
            _finding(
                "DEBT_HOOK_OVERLOAD",
                f"新增重大悬念 {context.draft.new_major_hooks}，合同只允许 {allowed}。",
                location="new_major_hooks",
            )
        )
    return _report("Debt Validator", findings)


def validate_payoff(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    payoff_changes = _changes(context, "payoff")
    needs_payoff = context.contract.primary_function in {
        NarrativeFunction.PARTIAL_PAYOFF,
        NarrativeFunction.MAJOR_PAYOFF,
    }
    if needs_payoff and not payoff_changes:
        findings.append(
            _finding(
                "PAYOFF_STATE_CHANGE_MISSING",
                "兑现章节没有 payoff 状态变化。",
                location="state_changes",
            )
        )
    for change in payoff_changes:
        payload = change.payload
        for key in ("causal_source", "cost", "behavior_change"):
            if not payload.get(key):
                findings.append(
                    _finding(
                        "PAYOFF_CAUSAL_FIELD_MISSING",
                        f"兑现记录缺少 {key}。",
                        location=f"state_changes:{change.record_id}",
                    )
                )
        if context.contract.primary_function is NarrativeFunction.MAJOR_PAYOFF:
            aftershocks = payload.get("aftershock_obligations")
            if not isinstance(aftershocks, list) or len(aftershocks) < 4:
                findings.append(
                    _finding(
                        "PAYOFF_AFTERSHOCK_PLAN_MISSING",
                        "重大兑现必须列出至少四类余波义务。",
                        location=f"state_changes:{change.record_id}",
                    )
                )
            cooldown_group = payload.get("cooldown_group")
            chapters_since = payload.get("chapters_since_same_subtype")
            occurrence_count = payload.get("same_subtype_occurrence_count")
            if not isinstance(cooldown_group, str) or not isinstance(
                occurrence_count, int
            ):
                findings.append(
                    _finding(
                        "PAYOFF_COOLDOWN_EVIDENCE_MISSING",
                        "重大兑现必须声明 cooldown_group 与同子类型历史次数。",
                        location=f"state_changes:{change.record_id}",
                    )
                )
            else:
                try:
                    allowed = payoff_cooldown_allowed(
                        group=cooldown_group,
                        chapters_since_last=(
                            chapters_since if isinstance(chapters_since, int) else None
                        ),
                        occurrence_count=occurrence_count,
                        config=context.settings.metrics["payoff_cooldown"],
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    findings.append(
                        _finding(
                            "PAYOFF_COOLDOWN_INPUT_INVALID",
                            f"爽点冷却证据无效：{exc}",
                            location=f"state_changes:{change.record_id}",
                        )
                    )
                else:
                    if not allowed:
                        findings.append(
                            _finding(
                                "PAYOFF_COOLDOWN_ACTIVE",
                                "同子类型爽点仍在冷却期或已是一生一次事件。",
                                location=f"state_changes:{change.record_id}",
                            )
                        )
    return _report("Payoff Validator", findings)


def validate_repetition(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    normalized_tags = {item.strip().casefold() for item in context.draft.structure_tags}
    for forbidden in context.contract.forbidden_repetitions:
        normalized = forbidden.strip().casefold()
        if normalized in normalized_tags or any(
            normalized and normalized in tag for tag in normalized_tags
        ):
            findings.append(
                _finding(
                    "FORBIDDEN_REPETITION",
                    f"命中合同禁止的近期结构：{forbidden}",
                    location="structure_tags",
                )
            )
    recent_signatures = {
        str(value.get("signature", "")).casefold()
        for value in context.projection.repetition.values()
        if value.get("signature")
    }
    repeated = sorted(normalized_tags & recent_signatures)
    if repeated:
        findings.append(
            _finding(
                "RECENT_STRUCTURE_REUSED",
                f"结构标签与近期记录完全重复：{repeated}",
                location="structure_tags",
            )
        )
    return _report("Repetition Validator", findings)


def validate_style(context: ValidationContext) -> ValidationReport:
    findings: list[ValidationFinding] = []
    score: float | None = None
    try:
        score = style_fit(
            context.draft.style_fit_inputs,
            context.settings.metrics["style_fit"],
        )
        if score < 75:
            findings.append(
                _finding(
                    "STYLE_FIT_LOW",
                    f"文风契合度仅 {score:.2f}，建议人工复核。",
                    severity=Severity.WARNING,
                    location="style_fit_inputs",
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        findings.append(
            _finding(
                "STYLE_FIT_INPUT_INVALID",
                f"文风契合度输入无效：{exc}",
                location="style_fit_inputs",
            )
        )
    for violation in context.draft.style_boundary_violations:
        findings.append(
            _finding(
                "STYLE_BOUNDARY_VIOLATION",
                violation,
                location="style_boundary_violations",
            )
        )
    return _report("Style Validator", findings, {"style_fit": score})


VALIDATORS: tuple[Callable[[ValidationContext], ValidationReport], ...] = (
    validate_canon,
    validate_timeline,
    validate_knowledge,
    validate_character,
    validate_economy_power,
    validate_contract,
    validate_debt,
    validate_payoff,
    validate_repetition,
    validate_style,
)
