"""Deterministic review helpers for the Phase 5 real generation benchmark.

These functions intentionally report observable structure only.  They do not
claim to measure literary quality, semantic novelty, or truth alignment.
Human review and the hidden-truth reveal remain separate stages.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any

_SPACE_RE = re.compile(r"\s+")
_CHAPTER_RE = re.compile(r"第\s*\d+\s*章|chapter\s*\d+", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_PUNCT_RE = re.compile(r"[，。！？；：、,.!?;:]+")


def normalize_prose(value: str) -> str:
    """Remove presentation noise while retaining the prose's word order."""

    normalized = _CHAPTER_RE.sub("第X章", value)
    normalized = _NUMBER_RE.sub("N", normalized)
    normalized = _SPACE_RE.sub("", normalized)
    return normalized.strip()


def _bigrams(value: str) -> set[str]:
    normalized = normalize_prose(value)
    if len(normalized) < 2:
        return {normalized} if normalized else set()
    return {normalized[index : index + 2] for index in range(len(normalized) - 1)}


def _similarity(left: str, right: str) -> float:
    first = _bigrams(left)
    second = _bigrams(right)
    if not first and not second:
        return 1.0
    if not first or not second:
        return 0.0
    jaccard = len(first & second) / len(first | second)
    sequence = SequenceMatcher(None, normalize_prose(left), normalize_prose(right)).ratio()
    return round((jaccard + sequence) / 2, 4)


def _sentence_skeletons(value: str) -> list[str]:
    sentences = re.split(r"[。！？!?；;]+", value)
    result: list[str] = []
    for sentence in sentences:
        compact = _SPACE_RE.sub("", sentence)
        if not compact:
            continue
        compact = _NUMBER_RE.sub("N", compact)
        compact = re.sub(r"[“”‘’\"'（）()「」【】\[\]，,、:：]", "", compact)
        result.append(compact[:28])
    return result


def compare_prose(left: str, right: str) -> dict[str, Any]:
    """Return structural similarity signals for two generated chapters."""

    left_skeletons = _sentence_skeletons(left)
    right_skeletons = _sentence_skeletons(right)
    repeated = sorted(set(left_skeletons) & set(right_skeletons))
    paragraphs_left = [item.strip() for item in re.split(r"\n\s*\n", left) if item.strip()]
    paragraphs_right = [item.strip() for item in re.split(r"\n\s*\n", right) if item.strip()]
    return {
        "normalized_similarity": _similarity(left, right),
        "paragraph_count": {"left": len(paragraphs_left), "right": len(paragraphs_right)},
        "sentence_count": {"left": len(left_skeletons), "right": len(right_skeletons)},
        "repeated_sentence_skeletons": repeated[:20],
        "opening_similarity": _similarity(left[:180], right[:180]),
        "ending_similarity": _similarity(left[-180:], right[-180:]),
    }


def template_diagnostics(chapters: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Detect repeated normalized templates without producing a quality score."""

    items = list(chapters)
    pairwise: list[dict[str, Any]] = []
    for left, right in combinations(items, 2):
        comparison = compare_prose(str(left["prose"]), str(right["prose"]))
        pairwise.append(
            {
                "left": left.get("chapter"),
                "right": right.get("chapter"),
                **comparison,
            }
        )
    normalized_groups: dict[str, list[Any]] = {}
    for item in items:
        normalized_groups.setdefault(normalize_prose(str(item["prose"])), []).append(
            item.get("chapter")
        )
    duplicate_groups = [
        chapters_for_template
        for chapters_for_template in normalized_groups.values()
        if len(chapters_for_template) > 1
    ]
    max_similarity = max(
        (float(item["normalized_similarity"]) for item in pairwise),
        default=0.0,
    )
    status = (
        "PROSE_TEMPLATE_COLLAPSE"
        if duplicate_groups or max_similarity >= 0.88
        else "DIVERGENT"
    )
    return {
        "chapter_count": len(items),
        "status": status,
        "duplicate_normalized_templates": duplicate_groups,
        "max_normalized_similarity": max_similarity,
        "pairwise": pairwise,
        "interpretation": (
            "结构信号显示两章存在同一归一化模板；需要人工审阅创新性。"
            if status == "PROSE_TEMPLATE_COLLAPSE"
            else "未检测到完全相同或高相似的归一化正文模板。"
        ),
    }


def _iter_files(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(item for item in path.rglob("*") if item.is_file())
    return sorted(set(result), key=lambda item: item.as_posix().casefold())


def anti_leak_audit(
    *,
    variant: str,
    generation_files: Iterable[Path],
    hidden_root: Path,
    hidden_texts: Iterable[str] = (),
) -> dict[str, Any]:
    """Audit the frozen generation inputs after truth reveal.

    It checks file/path provenance and only reports exact hidden chapter
    snippets when a caller supplies them after the generation lock.  It does
    not infer leakage from ordinary shared names.
    """

    files = _iter_files(generation_files)
    hidden = Path(hidden_root).expanduser().resolve()
    hidden_path_text = hidden.as_posix().casefold()
    path_hits: list[str] = []
    text_hits: list[dict[str, Any]] = []
    hidden_values = [normalize_prose(value) for value in hidden_texts if value.strip()]
    for path in files:
        path_text = path.as_posix().casefold()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if hidden_path_text in path_text or "hidden_ground_truth" in text.casefold():
            path_hits.append(str(path))
        normalized = normalize_prose(text)
        for index, hidden_value in enumerate(hidden_values):
            if len(hidden_value) >= 24 and hidden_value in normalized:
                text_hits.append({"path": str(path), "truth_index": index})
    runtime_hits: list[dict[str, str]] = []
    if variant == "A":
        forbidden_non_null = (
            "effective_runtime_state",
            "earned_surface",
            "baseline_recall_candidates",
        )
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if '"runtime_state_enabled": false' not in text:
                continue
            for key in forbidden_non_null:
                matches = re.finditer(
                    rf'"{re.escape(key)}"\s*:\s*([^,\n}}]+)',
                    text,
                )
                for match in matches:
                    value = match.group(1).strip()
                    if value not in {"null", "[]", "{}"}:
                        runtime_hits.append({"path": str(path), "field": key})
    return {
        "variant": variant,
        "generation_file_count": len(files),
        "hidden_root_referenced": bool(path_hits),
        "hidden_text_found_in_generation_inputs": bool(text_hits),
        "hidden_path_hits": path_hits,
        "hidden_text_hits": text_hits,
        "runtime_state_non_null_hits": runtime_hits,
        "passed": not path_hits and not text_hits and not runtime_hits,
    }


__all__ = ["anti_leak_audit", "compare_prose", "normalize_prose", "template_diagnostics"]
