"""Build and validate the machine-readable Distillation Package V1."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from novel_authoring.db.database import Database
from novel_authoring.distill.mapping import map_evidence, mapping_summary
from novel_authoring.distill.models import (
    CharacterVoiceProfile,
    ContinuityCandidate,
    ContinuityVerificationStatus,
    CraftControl,
    DistillationPackageManifest,
    DistilledEvidence,
    DistilledInformationClass,
    DistilledObservation,
    DistillScope,
    LiteraryArc,
    ThemeQuestion,
)
from novel_authoring.utils import json_dumps, utc_now


class DistillationPackageError(ValueError):
    """Raised when an output cannot form a strict package."""


_LOCATOR_RE = re.compile(
    r"`?(?P<source>[A-Za-z0-9][A-Za-z0-9_-]*)\s*(?:·|/|\||,|;)\s*"
    r"(?P<segment>segment-[A-Za-z0-9_-]+)\s*(?:·|/|\||,|;)\s*"
    r"(?:行|lines?|line)\s*(?P<start>\d+)"
    r"(?:\s*[-–—]\s*(?P<end>\d+))?`?",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_FIELD_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:`)?([^：:]+?)(?:`)?\s*[：:]\s*(.+?)\s*$")
_LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
_SOURCE_MARKERS = {
    "observation",
    "finding",
    "source_supported",
    "source supported",
    "事实观察",
    "观察",
}
_INTERPRETATION_MARKERS = {
    "inference",
    "interpretation",
    "mechanism",
    "transferable principle",
    "transferable_principle",
    "机制",
    "可迁移原则",
}
_CONTROL_MARKERS = {"control", "controls", "craft control", "写作控制", "控制"}
_RISK_MARKERS = {"risk", "risks", "风险"}
_CONFIDENCE_MARKERS = {"confidence", "置信度"}
_FALLBACK_MARKERS = {
    "immutable while supported",
    "mutable state",
    "check rule",
    "open",
    "已支付",
    "部分支付",
    "未闭环",
    "待确认",
    "冲突",
}


@dataclass(frozen=True, slots=True)
class _Section:
    title: str
    body: str
    fields: dict[str, list[str]]
    evidence: tuple[DistilledEvidence, ...]


@dataclass(frozen=True, slots=True)
class _Finding:
    dimension: str
    section: _Section
    observation: DistilledObservation


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, values: Iterable[Any]) -> None:
    lines = [json_dumps(value.model_dump(mode="json")) for value in values]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8", newline="\n")


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip("`" ).lower())


def _sections(text: str) -> list[_Section]:
    raw_sections: list[tuple[str, list[str]]] = []
    current_title = "全文"
    current_lines: list[str] = []
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match is not None:
            if current_lines:
                raw_sections.append((current_title, current_lines))
            current_title = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines or not raw_sections:
        raw_sections.append((current_title, current_lines))
    result: list[_Section] = []
    for title, lines in raw_sections:
        body = "\n".join(lines).strip()
        fields: dict[str, list[str]] = {}
        for line in lines:
            match = _FIELD_RE.match(line)
            if match is None:
                continue
            fields.setdefault(_normalize_key(match.group(1)), []).append(match.group(2).strip())
        result.append(
            _Section(
                title=title,
                body=body,
                fields=fields,
                evidence=tuple(_extract_evidence(body)),
            )
        )
    return result


def _extract_evidence(text: str) -> list[DistilledEvidence]:
    result: list[DistilledEvidence] = []
    seen: set[tuple[str, str, int, int]] = set()
    for match in _LOCATOR_RE.finditer(text):
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        key = (match.group("source"), match.group("segment"), start, end)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            DistilledEvidence(
                source_id=match.group("source"),
                segment_id=match.group("segment"),
                start_line=start,
                end_line=end,
            )
        )
    return result


def _confidence(section: _Section) -> float:
    values = section.fields.get("confidence") or section.fields.get("置信度") or []
    if not values:
        return 0.7
    value = values[0].strip().lower()
    known = {"high": 0.9, "medium-high": 0.8, "medium": 0.65, "low": 0.4}
    if value in known:
        return known[value]
    try:
        return max(0.0, min(1.0, float(value)))
    except ValueError:
        return 0.7


def _first_field(section: _Section, names: set[str]) -> str:
    for name in names:
        values = section.fields.get(name)
        if values:
            return values[0].strip()
    return ""


def _finding_marker(section: _Section) -> tuple[str, DistilledInformationClass, str]:
    for key, values in section.fields.items():
        if not values:
            continue
        if key in _SOURCE_MARKERS:
            return key, DistilledInformationClass.TEXTUAL_OBSERVATION, values[0]
        if key in _INTERPRETATION_MARKERS:
            return key, DistilledInformationClass.INTERPRETATION, values[0]
        if key in _CONTROL_MARKERS:
            return key, DistilledInformationClass.CRAFT_CONTROL, values[0]
        if key in _FALLBACK_MARKERS:
            return key, DistilledInformationClass.TEXTUAL_OBSERVATION, values[0]
    if section.body:
        first = next(
            (line.strip(" -*") for line in section.body.splitlines() if line.strip()),
            section.title,
        )
        return "finding", DistilledInformationClass.EMERGENT_FINDING, first
    return "", DistilledInformationClass.EMERGENT_FINDING, ""


def _is_finding(section: _Section) -> bool:
    if not section.body:
        return False
    if any(
        key in _SOURCE_MARKERS | _INTERPRETATION_MARKERS | _CONTROL_MARKERS | _FALLBACK_MARKERS
        for key in section.fields
    ):
        return True
    if section.evidence:
        return True
    return any(
        marker in section.body.lower()
        for marker in ("source_supported", "inference", "transferable principle", "finding:")
    )


def _runtime_uses(scope: DistillScope) -> list[str]:
    if scope is DistillScope.SELF_BOOK:
        return [
            "story_atlas_soft_understanding",
            "candidate_planning",
            "draft_controls",
            "soft_validation",
            "continuity_discovery",
        ]
    if scope is DistillScope.COMPARATIVE_REFERENCE:
        return ["synthesis", "transferable_principle", "craft_control"]
    return ["abstract_mechanism", "craft_control", "neutral_style_variable"]


def _parse_findings(
    root: Path,
    dimension: str,
    scope: DistillScope,
    scope_id: str,
    source_ids: set[str],
) -> list[_Finding]:
    path = root / f"{dimension}.md"
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        raise DistillationPackageError(f"缺少有效 Dimension Artifact：{dimension}.md")
    sections = [
        section
        for section in _sections(path.read_text(encoding="utf-8"))
        if _is_finding(section)
    ]
    if not sections:
        raise DistillationPackageError(f"Dimension Artifact 没有合法 Finding：{dimension}.md")
    findings: list[_Finding] = []
    for index, section in enumerate(sections, start=1):
        kind, information_class, statement = _finding_marker(section)
        evidence = list(section.evidence)
        unknown_sources = sorted({item.source_id for item in evidence} - source_ids)
        if unknown_sources:
            raise DistillationPackageError(
                f"{dimension}.md 使用了未声明 source_id：{', '.join(unknown_sources)}"
            )
        if information_class not in {
            DistilledInformationClass.CRAFT_CONTROL,
            DistilledInformationClass.INTERPRETATION,
        } and not evidence:
            raise DistillationPackageError(
                f"{dimension}.md 的来源性 Finding 缺少 source_id/locator：{section.title}"
            )
        if not statement:
            raise DistillationPackageError(
                f"{dimension}.md Finding statement 为空：{section.title}"
            )
        observation = DistilledObservation(
            observation_id=f"obs-{dimension}-{index:04d}",
            dimension=dimension,
            kind=kind,
            statement=statement,
            scope_type=scope,
            scope_id=scope_id,
            confidence=_confidence(section),
            evidence=evidence,
            runtime_uses=_runtime_uses(scope),
            information_class=information_class,
        )
        findings.append(_Finding(dimension=dimension, section=section, observation=observation))
    return findings


def _parse_arcs(findings: list[_Finding]) -> list[LiteraryArc]:
    arcs: list[LiteraryArc] = []
    for index, finding in enumerate(findings, start=1):
        title = finding.section.title
        if not re.search(r"(?:弧|arc)", title, re.IGNORECASE):
            continue
        evidence = list(finding.observation.evidence)
        if not evidence:
            continue
        ordered = sorted(evidence, key=lambda item: (item.segment_id, item.start_line))
        mechanism = _first_field(finding.section, _INTERPRETATION_MARKERS)
        causal = mechanism or finding.observation.statement
        arcs.append(
            LiteraryArc(
                arc_id=f"literary-arc-{index:04d}",
                name=title,
                start_segment=ordered[0].segment_id,
                end_segment=ordered[-1].segment_id,
                start_chapter=ordered[0].chapter_id,
                end_chapter=ordered[-1].chapter_id,
                state_before=_first_field(finding.section, {"state before", "状态之前"}),
                causal_summary=causal,
                state_after=_first_field(finding.section, {"state after", "状态之后"}),
                theme_questions=[],
                representative_segments=[item.segment_id for item in ordered],
                evidence=evidence,
            )
        )
    return arcs


def _parse_controls(findings: list[_Finding]) -> list[CraftControl]:
    controls: list[CraftControl] = []
    for index, finding in enumerate(findings, start=1):
        section = finding.section
        recommended = _first_field(section, _CONTROL_MARKERS)
        description = _first_field(section, _INTERPRETATION_MARKERS) or (
            finding.observation.statement
        )
        if not recommended:
            if finding.observation.information_class is not DistilledInformationClass.CRAFT_CONTROL:
                continue
            recommended = finding.observation.statement
        risks = []
        for key in _RISK_MARKERS:
            risks.extend(section.fields.get(key, []))
        controls.append(
            CraftControl(
                control_id=f"craft-control-{finding.dimension}-{index:04d}",
                category=finding.dimension,
                description=description,
                applies_to=[finding.dimension],
                recommended_behavior=recommended,
                risks=risks,
                evidence=list(finding.observation.evidence),
            )
        )
    return controls


def _parse_candidates(findings: list[_Finding]) -> list[ContinuityCandidate]:
    candidates: list[ContinuityCandidate] = []
    for index, finding in enumerate(findings, start=1):
        searchable = f"{finding.section.title}\n{finding.section.body}".lower()
        if not re.search(r"open|待确认|未闭环|悬念|冲突|gap|unknown", searchable, re.IGNORECASE):
            continue
        statement = (
            _first_field(finding.section, {"open", "待确认", "未闭环", "finding"})
            or finding.observation.statement
        )
        severity = "high" if "conflict" in searchable or "冲突" in searchable else "medium"
        candidates.append(
            ContinuityCandidate(
                candidate_id=f"continuity-candidate-{index:04d}",
                category=finding.section.title,
                statement=statement,
                severity=severity,
                evidence=list(finding.observation.evidence),
                verification_status=ContinuityVerificationStatus.UNVERIFIED,
                runtime_resolution="进入 review queue；不得自动写入 Canon",
            )
        )
    return candidates


def _parse_voice_profiles(findings: list[_Finding]) -> list[CharacterVoiceProfile]:
    profiles: list[CharacterVoiceProfile] = []
    for index, finding in enumerate(findings, start=1):
        section = finding.section
        markers = section.fields.get("voice") or section.fields.get("声音") or []
        controls = section.fields.get("controls") or section.fields.get("控制") or []
        if not markers and not controls:
            continue
        profiles.append(
            CharacterVoiceProfile(
                profile_id=f"voice-profile-{index:04d}",
                character_id=section.title,
                voice_markers=markers,
                dialogue_controls=controls,
                evidence=list(finding.observation.evidence),
            )
        )
    return profiles


def _parse_theme_questions(findings: list[_Finding]) -> list[ThemeQuestion]:
    questions: list[ThemeQuestion] = []
    for index, finding in enumerate(findings, start=1):
        question = (
            _first_field(finding.section, {"question", "theme question", "主题问题", "问题"})
            or finding.section.title
        )
        answers = finding.section.fields.get("competing answers", [])
        questions.append(
            ThemeQuestion(
                question_id=f"theme-question-{index:04d}",
                question=question,
                competing_answers=answers,
                evidence=list(finding.observation.evidence),
            )
        )
    return questions


def _all_evidence(
    findings: list[_Finding],
    arcs: list[LiteraryArc],
    controls: list[CraftControl],
    candidates: list[ContinuityCandidate],
    profiles: list[CharacterVoiceProfile],
    questions: list[ThemeQuestion],
) -> list[DistilledEvidence]:
    values: list[DistilledEvidence] = []
    for finding in findings:
        values.extend(finding.observation.evidence)
    for item in [*arcs, *controls, *candidates, *profiles, *questions]:
        values.extend(getattr(item, "evidence", []))
    return _dedupe_evidence(values)


def _dedupe_evidence(values: Iterable[DistilledEvidence]) -> list[DistilledEvidence]:
    unique: dict[tuple[str, str, int, int], DistilledEvidence] = {}
    for item in values:
        unique[(item.source_id, item.segment_id, item.start_line, item.end_line)] = item
    return list(unique.values())


def _validate_internal_references(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"无法读取 Markdown：{path} ({exc})")
            continue
        for raw_target in _LINK_RE.findall(text):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            candidate = (path.parent / target).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                errors.append(f"内部引用越界：{path.name} -> {raw_target}")
                continue
            if not candidate.is_file():
                errors.append(f"内部引用不存在：{path.name} -> {raw_target}")
    return errors


def _validate_originality(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"无法读取 Markdown artifact：{path} ({exc})")
            continue
        if any(len(line) > 2000 for line in text.splitlines()):
            errors.append(f"Markdown artifact 含疑似长段原文：{path.name}")
        if re.search(r"(?im)^\s*(?:source_text|quote_bank)\s*[:：]", text):
            errors.append(f"Markdown artifact 不得保存 source_text/quote_bank：{path.name}")
    machine = root / "machine"
    if not machine.is_dir():
        return ["machine 目录不存在"]
    for path in machine.rglob("*.json*"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"无法读取 machine artifact：{path} ({exc})")
            continue
        if any(len(line) > 2000 for line in text.splitlines()):
            errors.append(f"machine artifact 含疑似长段原文：{path.name}")
        if '"source_text"' in text or '"quote_bank"' in text:
            errors.append(f"machine artifact 不得保存 source_text/quote_bank：{path.name}")
    return errors


def _map_findings(
    database: Database,
    book_id: str,
    edition_id: str,
    preparation_manifest: Path,
    findings: list[_Finding],
) -> list[_Finding]:
    mapped: list[_Finding] = []
    for finding in findings:
        evidence = [
            map_evidence(database, book_id, edition_id, preparation_manifest, item)
            for item in finding.observation.evidence
        ]
        mapped.append(
            _Finding(
                dimension=finding.dimension,
                section=finding.section,
                observation=finding.observation.model_copy(update={"evidence": evidence}),
            )
        )
    return mapped


def _validate_preparation_contract(
    preparation_manifest: Path,
    *,
    book_id: str,
    edition_id: str,
    scope: DistillScope,
    mode: str,
    source_ids: set[str],
) -> None:
    try:
        prepared = json.loads(preparation_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DistillationPackageError(
            f"冻结 preparation manifest 无法读取：{preparation_manifest}"
        ) from exc
    if not isinstance(prepared, dict):
        raise DistillationPackageError("冻结 preparation manifest 必须是 object")
    declared_book = prepared.get("book_id")
    declared_edition = prepared.get("edition_id")
    if declared_book is not None and str(declared_book) != book_id:
        raise DistillationPackageError("preparation book_id 与 task 不一致")
    if declared_edition is not None and str(declared_edition) != edition_id:
        raise DistillationPackageError("preparation edition_id 与 task 不一致")
    prepared_source_ids = {
        str(item["source_id"])
        for item in prepared.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }
    if prepared_source_ids and source_ids != prepared_source_ids:
        raise DistillationPackageError("distill source_ids 与冻结 preparation 不一致")
    declared_scope = str(prepared.get("scope") or "").upper()
    source_scope = str(prepared.get("source_scope") or "").upper()
    if declared_scope in {item.value for item in DistillScope}:
        if scope is not DistillScope.COMPARATIVE_REFERENCE and scope.value != declared_scope:
            raise DistillationPackageError("distill scope 与冻结 preparation 不一致")
        if (
            scope is DistillScope.COMPARATIVE_REFERENCE
            and mode != "compare"
        ):
            raise DistillationPackageError("COMPARATIVE_REFERENCE 只能用于 compare mode")
    elif source_scope in {"BOOK_CANONICAL_SOURCE", "BOOK_EFFECTIVE_EDITION"}:
        if scope is not DistillScope.SELF_BOOK:
            raise DistillationPackageError("BOOK preparation 只能使用 SELF_BOOK scope")
    if mode == "compare" and scope is not DistillScope.COMPARATIVE_REFERENCE:
        raise DistillationPackageError("compare mode 必须使用 COMPARATIVE_REFERENCE scope")


def build_distillation_package(
    database: Database,
    book_id: str,
    edition_id: str,
    request: dict[str, Any],
    skill_root: Path,
) -> dict[str, Any]:
    """Build machine artifacts from validated Markdown and map their evidence."""

    root = Path(skill_root).expanduser().resolve()
    dimensions = [str(item) for item in request.get("dimensions", [])]
    if not dimensions:
        raise DistillationPackageError("distill request 没有 selected dimensions")
    source_ids = {str(item) for item in request.get("source_ids", [])}
    if not source_ids:
        raise DistillationPackageError("distill request 没有 source_ids")
    try:
        scope = DistillScope(str(request.get("scope") or DistillScope.EXTERNAL_REFERENCE.value))
    except ValueError as exc:
        raise DistillationPackageError("distill request scope 无效") from exc
    scope_id = str(request.get("scope_id") or book_id)
    preparation_manifest = (
        Path(str(request.get("preparation_manifest") or "")).expanduser().resolve()
    )
    if not preparation_manifest.is_file():
        raise DistillationPackageError(f"冻结 preparation manifest 不存在：{preparation_manifest}")
    _validate_preparation_contract(
        preparation_manifest,
        book_id=book_id,
        edition_id=edition_id,
        scope=scope,
        mode=str(request.get("mode") or "create"),
        source_ids=source_ids,
    )
    findings: list[_Finding] = []
    by_dimension: dict[str, list[_Finding]] = {}
    for dimension in dimensions:
        parsed = _parse_findings(root, dimension, scope, scope_id, source_ids)
        by_dimension[dimension] = parsed
        findings.extend(parsed)
    findings = _map_findings(database, book_id, edition_id, preparation_manifest, findings)
    by_dimension = {
        dimension: [item for item in findings if item.dimension == dimension]
        for dimension in dimensions
    }
    plot_findings = by_dimension.get("plot", [])
    continuity_findings = by_dimension.get("continuity", [])
    arcs = _parse_arcs(plot_findings)
    controls = _parse_controls(findings)
    candidates = _parse_candidates(continuity_findings)
    profiles = _parse_voice_profiles(by_dimension.get("characters", []))
    questions = _parse_theme_questions(by_dimension.get("themes", []))
    evidence = _all_evidence(findings, arcs, controls, candidates, profiles, questions)
    machine = root / "machine"
    machine.mkdir(parents=True, exist_ok=True)
    observations = [item.observation for item in findings]
    _write_jsonl(machine / "observations.jsonl", observations)
    if arcs:
        _write_json(
            machine / "literary_arcs.json",
            [item.model_dump(mode="json") for item in arcs],
        )
    if candidates:
        _write_jsonl(machine / "continuity_candidates.jsonl", candidates)
    if controls:
        _write_json(
            machine / "craft_controls.json",
            [item.model_dump(mode="json") for item in controls],
        )
    if profiles:
        _write_json(
            machine / "character_voice_profiles.json",
            [item.model_dump(mode="json") for item in profiles],
        )
    if questions:
        _write_json(
            machine / "theme_questions.json",
            [item.model_dump(mode="json") for item in questions],
        )
    if evidence:
        _write_jsonl(machine / "evidence_mappings.jsonl", evidence)

    artifacts: dict[str, str] = {
        "SKILL.md": "SKILL.md",
        "distillation-report.md": "distillation-report.md",
        **{dimension: f"{dimension}.md" for dimension in dimensions},
        "machine/package.json": "machine/package.json",
        "machine/observations.jsonl": "machine/observations.jsonl",
    }
    optional = {
        "machine/literary_arcs.json": bool(arcs),
        "machine/continuity_candidates.jsonl": bool(candidates),
        "machine/craft_controls.json": bool(controls),
        "machine/character_voice_profiles.json": bool(profiles),
        "machine/theme_questions.json": bool(questions),
        "machine/evidence_mappings.jsonl": bool(evidence),
    }
    artifacts.update({key: key for key, present in optional.items() if present})
    package = DistillationPackageManifest(
        distill_id=str(request.get("distill_id") or ""),
        book_id=book_id,
        edition_id=edition_id,
        scope=scope,
        mode=str(request.get("mode") or "create"),
        depth=str(request.get("depth") or "standard"),
        dimensions=dimensions,
        source_ids=sorted(source_ids),
        source_count=len(source_ids),
        created_at=utc_now(),
        package_version="distillation-package-v1",
        artifacts=artifacts,
        warnings=[
            f"{status}: {count}"
            for status, count in mapping_summary(evidence).items()
            if status != "EXACT" and count
        ],
    )
    _write_json(machine / "package.json", package.model_dump(mode="json"))
    errors = _validate_internal_references(root) + _validate_originality(root)
    if errors:
        raise DistillationPackageError("；".join(errors))
    summary = {
        "selected_dimensions": dimensions,
        "produced_dimensions": sorted(
            dimension for dimension in dimensions if (root / f"{dimension}.md").is_file()
        ),
        "finding_count": len(observations),
        "mapped_evidence_count": sum(
            item.mapping_status.value == "EXACT" for item in evidence
        ),
        "unmapped_count": sum(item.mapping_status.value == "UNMAPPED" for item in evidence),
        "conflicting_count": sum(
            item.mapping_status.value == "CONFLICTING" for item in evidence
        ),
        "partial_count": sum(item.mapping_status.value == "PARTIAL" for item in evidence),
        "continuity_candidate_count": len(candidates),
        "craft_control_count": len(controls),
        "literary_arc_count": len(arcs),
        "scope": scope.value,
        "mapping_summary": mapping_summary(evidence),
    }
    return {"manifest": package, "summary": summary}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise DistillationPackageError(f"JSONL 行必须是 object：{path}")
        values.append(value)
    return values


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DistillationPackageError(f"JSON artifact 无法读取：{path}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise DistillationPackageError(f"JSON artifact 必须是 object 数组：{path}")
    return value


def validate_distillation_package(
    root: Path,
    *,
    expected_book_id: str | None = None,
    expected_edition_id: str | None = None,
    expected_scope: str | None = None,
    expected_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """Strictly validate an already-built package without calling Codex."""

    package_path = Path(root).expanduser().resolve() / "machine" / "package.json"
    if not package_path.is_file():
        raise DistillationPackageError("缺少 machine/package.json")
    try:
        package = DistillationPackageManifest.model_validate_json(
            package_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise DistillationPackageError(f"machine/package.json 不符合严格模型：{exc}") from exc
    errors: list[str] = []
    if expected_book_id and package.book_id != expected_book_id:
        errors.append("package book_id 与 task 不一致")
    if expected_edition_id and package.edition_id != expected_edition_id:
        errors.append("package edition_id 与 task 不一致")
    if expected_scope and package.scope.value != expected_scope:
        errors.append("package scope 与 task 不一致")
    selected = expected_dimensions or package.dimensions
    if set(package.dimensions) != set(selected):
        errors.append("package dimensions 与 task 不一致")
    for key, relative in package.artifacts.items():
        path = (package_path.parent.parent / relative).resolve()
        try:
            path.relative_to(package_path.parent.parent.resolve())
        except ValueError:
            errors.append(f"package artifact 越界：{key}")
            continue
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"package artifact 缺失或为空：{key}")
    try:
        observations = [
            DistilledObservation.model_validate(item)
            for item in _read_jsonl(package_path.parent / "observations.jsonl")
        ]
        arcs = [
            LiteraryArc.model_validate(item)
            for item in _read_json_array(package_path.parent / "literary_arcs.json")
        ]
        controls = [
            CraftControl.model_validate(item)
            for item in _read_json_array(package_path.parent / "craft_controls.json")
        ]
        candidates = [
            ContinuityCandidate.model_validate(item)
            for item in _read_jsonl(package_path.parent / "continuity_candidates.jsonl")
        ]
        profiles = [
            CharacterVoiceProfile.model_validate(item)
            for item in _read_json_array(
                package_path.parent / "character_voice_profiles.json"
            )
        ]
        questions = [
            ThemeQuestion.model_validate(item)
            for item in _read_json_array(package_path.parent / "theme_questions.json")
        ]
    except Exception as exc:
        raise DistillationPackageError(f"machine artifact 不符合严格模型：{exc}") from exc
    for observation in observations:
        if observation.dimension not in package.dimensions:
            errors.append(f"observation dimension 未被 selected：{observation.dimension}")
        if any(item.source_id not in package.source_ids for item in observation.evidence):
            errors.append(f"observation 使用未声明 source_id：{observation.observation_id}")
        if package.scope is not DistillScope.SELF_BOOK and observation.information_class in {
            DistilledInformationClass.TEXTUAL_OBSERVATION,
            DistilledInformationClass.CONTINUITY_CANDIDATE,
        }:
            errors.append(
                "外部 scope 不得把来源事实作为 runtime observation："
                f"{observation.observation_id}"
            )
    for item in [*arcs, *controls, *candidates, *profiles, *questions]:
        if any(
            evidence.source_id not in package.source_ids
            for evidence in getattr(item, "evidence", [])
        ):
            errors.append("machine artifact 使用未声明 source_id")
    for dimension in selected:
        artifact = Path(root).expanduser().resolve() / f"{dimension}.md"
        if not artifact.is_file() or not artifact.read_text(encoding="utf-8").strip():
            errors.append(f"selected dimension 缺少有效 artifact：{dimension}.md")
        elif not any(
            _is_finding(section)
            for section in _sections(artifact.read_text(encoding="utf-8"))
        ):
            errors.append(f"selected dimension 没有合法 Finding：{dimension}.md")
    errors.extend(_validate_internal_references(Path(root).expanduser().resolve()))
    errors.extend(_validate_originality(Path(root).expanduser().resolve()))
    if errors:
        raise DistillationPackageError("；".join(dict.fromkeys(errors)))
    evidence = _dedupe_evidence(
        item for observation in observations for item in observation.evidence
    )
    mapping_path = package_path.parent / "evidence_mappings.jsonl"
    try:
        mappings = [
            DistilledEvidence.model_validate(item) for item in _read_jsonl(mapping_path)
        ]
    except Exception as exc:
        raise DistillationPackageError(f"evidence_mappings.jsonl 不符合严格模型：{exc}") from exc
    expected_mapping = {
        (item.source_id, item.segment_id, item.start_line, item.end_line): item.mapping_status
        for item in evidence
    }
    actual_mapping = {
        (item.source_id, item.segment_id, item.start_line, item.end_line): item.mapping_status
        for item in mappings
    }
    if expected_mapping != actual_mapping:
        errors.append("evidence_mappings 与 observations evidence 不一致")
    if errors:
        raise DistillationPackageError("；".join(dict.fromkeys(errors)))
    summary = {
        "selected_dimensions": selected,
        "produced_dimensions": [
            dimension
            for dimension in selected
            if (Path(root).expanduser().resolve() / f"{dimension}.md").is_file()
        ],
        "finding_count": len(observations),
        "mapped_evidence_count": sum(item.mapping_status.value == "EXACT" for item in evidence),
        "unmapped_count": sum(item.mapping_status.value == "UNMAPPED" for item in evidence),
        "conflicting_count": sum(item.mapping_status.value == "CONFLICTING" for item in evidence),
        "partial_count": sum(item.mapping_status.value == "PARTIAL" for item in evidence),
        "scope": package.scope.value,
        "literary_arc_count": len(arcs),
        "craft_control_count": len(controls),
        "continuity_candidate_count": len(candidates),
        "mapping_summary": mapping_summary(evidence),
        "package": package.model_dump(mode="json"),
    }
    return summary


__all__ = [
    "DistillationPackageError",
    "build_distillation_package",
    "validate_distillation_package",
]
