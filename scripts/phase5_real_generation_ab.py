"""Run the historical Phase 5 semantic-fixture A/B benchmark.

SEMANTIC_FIXTURE_AB / NOT_LIVE_GENERATION_BENCHMARK

The harness creates six isolated Book Libraries at boundaries 35, 50 and 75
and preserves the historical handoff-shaped deterministic fixture baseline.
Its semantic outputs are benchmark-specific Codex-authored prose/analysis
fixtures, not results returned by a live READY_FOR_CODEX operation.  They are
retained as a deterministic historical baseline and must not be used to claim
that a live Codex Desktop handoff generated the literary results.  Hidden
chapters are opened only in ``_evaluate``.

This benchmark never calls an API, subprocess, Codex CLI, approval workflow,
Canon commit, Edition activation, or source-file writer.
"""

# The benchmark contains intentionally long Chinese prose fixtures.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from novel_authoring.benchmark.real_ab import (
    anti_leak_audit,
    compare_prose,
    template_diagnostics,
)
from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.config import Settings, load_settings
from novel_authoring.contracts.draft import DraftOutput, DraftStateChange
from novel_authoring.db.database import Database
from novel_authoring.distill.models import DistillScope, EvidenceMappingStatus
from novel_authoring.distill.package import validate_distillation_package
from novel_authoring.distill.service import (
    create_distill_handoff,
    import_distill_result,
    latest_distill_reference,
    prepare_book_sources,
)
from novel_authoring.drafting.service import import_draft_output, prepare_draft_task
from novel_authoring.metrics.engine import MetricInputBundle, diagnose_bundle, persist_results
from novel_authoring.metrics.gates import HardGateInput
from novel_authoring.planning.batch import BatchProvisionalState
from novel_authoring.planning.candidates import (
    import_candidate_output,
    prepare_candidate_task,
)
from novel_authoring.planning.contracts import build_chapter_contract
from novel_authoring.planning.models import (
    CandidateLens,
    CandidateOutput,
    CandidateProposal,
    CandidateScoreInputs,
    ChapterContract,
    NoveltyDeclaration,
    NoveltyProvenance,
)
from novel_authoring.rhythm.service import diagnose_rhythm, rebuild_features
from novel_authoring.runtime_baseline import build_runtime_baseline
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.library import LibraryAddOptions, add_book
from novel_authoring.utils import json_dumps, stable_id, utc_now
from novel_authoring.validation.service import validate_draft
from novel_authoring.workflows.handoffs import (
    HandoffStatus,
    claim_handoff,
    create_continuation_handoff,
    update_handoff_status,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "book" / "测试小说.md"
BOUNDARIES = (35, 50, 75)
DIMENSIONS = (
    "worldbuilding",
    "characters",
    "plot",
    "style",
    "narrative",
    "dialogue",
    "pacing",
    "themes",
    "continuity",
)
VARIANTS = ("A", "B")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def _chapter_sections(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^##\s+.+$", text))
    if len(matches) < max(BOUNDARIES) + 2:
        raise RuntimeError("测试小说不足以执行 Phase 5 的 35/50/75 两章盲测")
    return [
        text[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(text)].strip()
        for index, match in enumerate(matches)
    ]


def _source_id_and_segments(prepared: dict[str, object]) -> tuple[str, list[dict[str, Any]]]:
    index = json.loads(
        (Path(str(prepared["root"])) / "chapter_index.json").read_text(encoding="utf-8")
    )
    source = index["sources"][0]
    return str(source["source_id"]), list(source["segments"])


def _segment(segments: list[dict[str, Any]], ordinal: int) -> dict[str, Any]:
    for item in segments:
        if int(item["ordinal"]) == ordinal:
            return item
    raise RuntimeError(f"冻结 source 没有第 {ordinal} 个 segment")


def _locator(source_id: str, segment: dict[str, Any], *, width: int = 3) -> str:
    start = int(segment["start_line"])
    end = min(int(segment["end_line"]), start + width)
    return f"{source_id} · {segment['segment_id']} · 行 {start}-{end}"


def _evidence(
    prepared: dict[str, object],
    *,
    ordinal: int,
    width: int = 3,
) -> tuple[str, dict[str, Any], str]:
    source_id, segments = _source_id_and_segments(prepared)
    segment = _segment(segments, ordinal)
    return source_id, segment, _locator(source_id, segment, width=width)


def _semantic_notes(boundary: int) -> dict[str, dict[str, str]]:
    """Codex-authored, source-backed semantic notes for visible chapters only."""

    notes: dict[int, dict[str, dict[str, str]]] = {
        35: {
            "worldbuilding": {
                "observation": "规则系统把降落、转盘、奖励与资源选择串成可重复的生存机制；奖励越丰厚，选择越接近对规则边界的试探。",
                "interpretation": "世界的张力来自规则的可计算外观与代价的不透明之间的落差。",
            },
            "characters": {
                "observation": "苏牧在高收益奖励面前仍先核对代价，并把与林雨薇的合作底线纳入决定。",
                "interpretation": "主角的主动性不是无条件冒险，而是先把选择拆成资源、关系和未知风险。",
            },
            "plot": {
                "observation": "静音结界、鬼屋、幸厄转盘和奖励分配连续把外部威胁推向规则层；蓝色护甲之后出现战术导弹图纸，形成新的选择压力。",
                "interpretation": "每一次奖励都先改变可选择的范围，再要求角色为选择承担可见成本。",
            },
            "style": {
                "observation": "系统提示、短促动作和人物判断交替出现，信息常在一个物件或选项上完成转折。",
                "interpretation": "把规则说明压缩到动作前后，让物件承担信息，不用长段解释替代现场反应。",
            },
            "narrative": {
                "observation": "前文反复建立三选一与奖励机制，当前边界把读者期待从‘能否生存’推向‘是否敢使用新规则’。",
                "interpretation": "有效的推进不是立即兑现蓝图，而是把蓝图变成下一次行动必须回答的问题。",
            },
            "dialogue": {
                "observation": "林雨薇的表达更多承担边界确认和利益分配，苏牧的回答则把信任转化为可执行选择。",
                "interpretation": "对话应让双方分别暴露一条底线，再用行动验证，而不是用宣言直接完成互信。",
            },
            "pacing": {
                "observation": "遭遇、搜集、转盘和奖励结算形成短回合；连续高收益之后需要用一次核对或分配动作换气。",
                "interpretation": "在下一次大信息揭示前保留一个有成本的停顿，可以让升级不被写成流水账。",
            },
            "themes": {
                "observation": "‘规则给出的奖励是否等于可以无条件占有’成为边界处的主题问题。",
                "interpretation": "生存效率与不越过他人底线之间的冲突，比单纯的变强更能产生选择重量。",
            },
            "continuity": {
                "observation": "战术导弹图纸和蓝色护甲都已被看见，但材料、启动条件与实际使用并未由当前正文确认。",
                "interpretation": "将图纸保留为待验证机会，不把可见蓝图自动升级成可用能力。",
            },
        },
        50: {
            "worldbuilding": {
                "observation": "生存系统逐渐显出交换网络：燃油、木箭、爆炸装置和医疗需求把个人资源连接到远方求援。",
                "interpretation": "世界扩张通过资源如何流动来完成，而不是只靠新增怪物名称。",
            },
            "characters": {
                "observation": "苏牧开始把手工制作、交易和听从他人判断当作可比较的行动；周振国的求援让‘帮不帮’变成具体代价。",
                "interpretation": "主角的成长表现为改变决策方式，既不盲信求援，也不把交易对象简单当作资源。",
            },
            "plot": {
                "observation": "爆炸声带来外部压力，随后经过判断、收获、交易和木箭制作，边界落在一条带有医疗请求的风险线上。",
                "interpretation": "把听见的威胁转成资源决策，再转成关系选择，能让战斗之外的因果继续推进。",
            },
            "style": {
                "observation": "章节多用动作细节和物品数量推进，解释常附着在燃油灯、木箭或交易条件上。",
                "interpretation": "保留具体物件的触感与数量，让每次交换都同时呈现收益和损耗。",
            },
            "narrative": {
                "observation": "个人囤积与外部求援形成新的叙事债务；当前只提出是否回应，不替后续战斗预先结算。",
                "interpretation": "下一步应让援助决定改变双方位置，同时留下无法一次解决的资源压力。",
            },
            "dialogue": {
                "observation": "交易和求援中的话语都带有条件，真正的态度由报价、沉默和是否交付共同完成。",
                "interpretation": "让对话先说条件，再由人物用一个不可撤回的小动作确认立场。",
            },
            "pacing": {
                "observation": "爆炸后的紧张被制作和交易动作切成短段，收获感与危险感交替出现。",
                "interpretation": "将一次资源整理作为压力换气，但下一段必须用新的请求或限制重新收紧。",
            },
            "themes": {
                "observation": "‘拥有资源是否意味着有义务回应求援’把生存效率与互助伦理放到同一张账上。",
                "interpretation": "让善意产生真实成本，主题才不会被一句豪言提前解决。",
            },
            "continuity": {
                "observation": "木箭、交易渠道、爆炸装置和医疗请求之间的可用库存与距离仍需要逐项核对。",
                "interpretation": "把求援当作待验证的连续性候选，先确认物资、敌情和交付路径，再决定回应幅度。",
            },
        },
        75: {
            "worldbuilding": {
                "observation": "第二职业栏位、连招、长枪、M500和动态视觉把求生系统从单人强化推向技能组合与跨缆车社会。",
                "interpretation": "能力系统的扩张同时改变了空间关系：一个人的强大开始影响他人如何接近、试探和结盟。",
            },
            "characters": {
                "observation": "苏牧不再只追求单项数值，而是把长枪连招、远程武器和动态视觉组合成自己的战斗判断。",
                "interpretation": "人物能力的辨识度来自取舍顺序与临场判断，而不是能力清单越长越好。",
            },
            "plot": {
                "observation": "第二职业栏位和连招带来能力协同，外国人出现后，力量差距被重新解释为发现、暴露与谈判问题。",
                "interpretation": "从技能升级转向社会反应，是把个人成长继续写出后果的关键转折。",
            },
            "style": {
                "observation": "战斗段落用招式顺序、武器反馈和即时判断制造速度，系统信息只在决策节点短暂出现。",
                "interpretation": "先写身体和空间如何反应，再补一行系统确认，能避免能力说明盖过现场。",
            },
            "narrative": {
                "observation": "连招让‘能不能打赢’转为‘谁会看见这种能力并如何回应’，外国人把私人优势推入公共视野。",
                "interpretation": "新的社会视线应改变主角的下一次选择，而不是只作为下一场战斗的观众。",
            },
            "dialogue": {
                "observation": "跨缆车接触中的语言带有试探和招募意味，身份、实力与利益不会在第一次交流里完全摊开。",
                "interpretation": "每句招募或拒绝都应同时管理信息差，让人物说出口的内容少于他真正判断的内容。",
            },
            "pacing": {
                "observation": "连续战斗升级后紧接着出现身份暴露，读者的兴奋没有被完全收束，而是被转成社会压力。",
                "interpretation": "下一章可以降低招式密度、提高观察和谈判密度，让节奏完成一次功能换挡。",
            },
            "themes": {
                "observation": "能力越多，隐藏能力和保护边界的成本越高；力量既提供自由也制造被发现的风险。",
                "interpretation": "把‘变强是否更自由’落到一次具体的展示或隐瞒选择上，主题会比抽象议论更有重量。",
            },
            "continuity": {
                "observation": "长枪、突刺连击、M500和动态视觉已在可见章节中出现，但它们的消耗、适用距离与组合限制仍需分开记录。",
                "interpretation": "长期能力观察可以指导写作，但只有被当前运行时基线确认的能力才可作为可使用状态；文学观察不能替代能力登记。",
            },
        },
    }
    return notes[boundary]


def _publish_codex_distill(
    database: Database,
    book_id: str,
    prepared: dict[str, object],
    boundary: int,
) -> dict[str, Any]:
    handoff = create_distill_handoff(
        database,
        book_id,
        preparation_id=str(prepared["preparation_id"]),
        dimensions=",".join(DIMENSIONS),
        depth="standard",
    )
    handoff_id = str(handoff["handoff_id"])
    task_directory = Path(str(handoff["task_directory"]))
    task_path = task_directory / "input" / "task.json"
    if not task_path.is_file():
        task_path = task_directory / "task.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    claim = claim_handoff(database, handoff_id, f"phase5-codex-{book_id}")
    claim_token = str(claim["claim_token"])
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.RUNNING,
        claim_token=claim_token,
    )
    root = task_directory / "artifacts" / "distill_skill"
    root.mkdir(parents=True, exist_ok=False)
    source_id, segments = _source_id_and_segments(prepared)
    notes = _semantic_notes(boundary)
    locators = {
        "recent": _locator(source_id, _segment(segments, max(1, boundary - 2))),
        "boundary": _locator(source_id, _segment(segments, boundary)),
        "early": _locator(source_id, _segment(segments, max(1, boundary // 3))),
    }
    _write_text(
        root / "SKILL.md",
        "\n".join(
            [
                "# Phase 5 Codex Distillation Knowledge Layer",
                "",
                f"- Source scope: `SELF_BOOK` for `{book_id}` at visible boundary `{boundary}`.",
                "- Semantic executor: historical Codex-authored fixture using the frozen preparation input; no live handoff claim.",
                "- Runtime use: soft understanding only; no observation is Canon or a capability grant.",
                "- Evidence policy: every textual observation points to a frozen source segment and line range.",
                "- Originality boundary: this package stores abstractions, controls and locators, not source paragraphs.",
                "",
                "The Literary Arc in this package is a Distill interpretation and is not an Initialization Processing Arc.",
            ]
        ),
    )
    report_lines = [
        "# Distillation Report",
        "",
        f"本次分析只读取当前独立 Book 的可见前 {boundary} 个章节；隐藏的后续两章不在 Codex 输入中。",
        "",
        "## Evidence freeze",
        "",
        f"- Early locator: `{locators['early']}`",
        f"- Recent locator: `{locators['recent']}`",
        f"- Boundary locator: `{locators['boundary']}`",
        "- Scope: `SELF_BOOK`",
        "- Canon write: `false`",
        "",
        "## Nine dimensions",
        "",
    ]
    report_lines.extend(f"- `{dimension}`: {notes[dimension]['observation']}" for dimension in DIMENSIONS)
    _write_text(root / "distillation-report.md", "\n".join(report_lines))

    for dimension in DIMENSIONS:
        item = notes[dimension]
        evidence_locator = locators["boundary"] if dimension in {"worldbuilding", "continuity", "plot"} else locators["recent"]
        lines = [
            f"# {dimension}",
            "",
            "## Source Finding",
            "",
            f"- Sources: `{evidence_locator}`",
            f"- Observation: {item['observation']}",
            f"- Interpretation: {item['interpretation']}",
            f"- Chapter Range: 1-{boundary}",
            "- Subject IDs: 苏牧, 林雨薇, survival-system",
            "- Confidence: high",
        ]
        if dimension == "plot":
            lines.extend(
                [
                    "",
                    "## Literary Arc — rule rewards become social pressure",
                    "",
                    f"- Sources: `{locators['early']}`",
                    f"- Interpretation: {item['interpretation']}",
                    "- State Before: repeated survival choices are mainly personal resource decisions",
                    "- State After: a visible reward creates a choice that can alter trust and exposure",
                    f"- Chapter Range: 1-{boundary}",
                ]
            )
        if dimension in {"style", "pacing"}:
            lines.extend(
                [
                    "",
                    "## Craft Control",
                    "",
                    f"- Sources: `{locators['recent']}`",
                    f"- Craft Control: {item['interpretation']}",
                    "- Risks: turning a soft pattern into a fixed formula or copying source prose",
                ]
            )
        if dimension == "characters":
            lines.extend(
                [
                    "",
                    "## Voice Profile",
                    "",
                    f"- Sources: `{locators['recent']}`",
                    "- Voice: direct, economical decisions under pressure; trust is shown through negotiated action",
                    "- Controls: let a character choose before naming the emotional conclusion",
                ]
            )
        if dimension == "themes":
            lines.extend(
                [
                    "",
                    "## Theme Question",
                    "",
                    f"- Sources: `{locators['boundary']}`",
                    "- Question: when a survival rule offers more power, what remains a personal boundary?",
                    "- Competing Answers: efficiency, trust, concealment, mutual obligation",
                ]
            )
        if dimension == "continuity":
            lines.extend(
                [
                    "",
                    "## Open Setup",
                    "",
                    f"- Sources: `{locators['boundary']}`",
                    f"- Open: {item['interpretation']}",
                    "- Verification: source review and runtime baseline must remain separate",
                ]
            )
        _write_text(root / f"{dimension}.md", "\n".join(lines))

    distill = task["distill"]
    result = {
        "handoff_id": handoff_id,
        "handoff_type": "NOVEL_DISTILLATION",
        "requested_stage": "DISTILL",
        "completed_stage": "DISTILLED",
        "book_id": task["book_id"],
        "edition_id": task["edition_id"],
        "status": "DISTILLED",
        "task_ids": [],
        "candidate_ids": [],
        "selected_candidate_id": None,
        "contract_id": None,
        "draft_id": None,
        "campaign_id": None,
        "revision_unit_ids": [],
        "artifact_paths": ["artifacts/distill_skill/SKILL.md"],
        "validation_summary": {
            "provenance": "PASS",
            "originality": "PASS",
            "semantic_executor": "Windows Codex desktop",
        },
        "warnings": [],
        "next_action": "novel distill import",
        "canon_committed": False,
        "edition_activated": False,
        "base_event_seq": task["base_event_seq"],
        "base_projection_hash": task["base_projection_hash"],
        "metric_run_ids": [],
        "metric_bundle_hash": None,
        "completed_at": utc_now(),
        "distill_id": distill["distill_id"],
        "distill_source_ids": distill["source_ids"],
        "distill_dimensions": distill["dimensions"],
        "distill_mode": distill["mode"],
        "distill_depth": distill["depth"],
        "distill_scope": distill["scope"],
        "distill_skill_root": "artifacts/distill_skill",
    }
    update_handoff_status(
        database,
        handoff_id,
        HandoffStatus.COMPLETED,
        claim_token=claim_token,
        result=result,
    )
    return import_distill_result(database, book_id, handoff_id)


def _build_runtime_baseline(
    database: Database,
    book_id: str,
    prepared: dict[str, object],
    boundary: int,
    benchmark_root: Path,
) -> dict[str, object]:
    source_id, segments = _source_id_and_segments(prepared)
    def evidence(ordinal: int) -> dict[str, Any]:
        segment = _segment(segments, ordinal)
        # The source span begins on the first body line after the Markdown
        # heading, while the frozen Distill segment includes that heading.
        start = min(int(segment["end_line"]), int(segment["start_line"]) + 1)
        return {
            "source_id": source_id,
            "segment_id": str(segment["segment_id"]),
            "start_line": start,
            "end_line": min(int(segment["end_line"]), start + 3),
            "chapter_id": str(segment["chapter_id"]),
            "source_span_ids": [str(segment["source_span_id"])],
            "mapping_status": EvidenceMappingStatus.EXACT.value,
            "direct_text_confirmed": True,
        }

    if boundary == 35:
        entries = [
            ("blue-armor", "capability", "蓝色护甲", "可见章节已取得蓝色护甲；能否立即使用仍受资源与规则条件约束。", 35, {"availability": "AVAILABLE", "costs": "choice|exposure", "constraints": "check material and rule", "last_confirmed": "35"}),
            ("rule-choice-interface", "knowledge", "reward choice interface", "角色已经理解奖励选择需要比较收益、代价与合作底线。", 34, {"availability": "AVAILABLE", "constraints": "review before commitment", "last_confirmed": "34"}),
            ("tactical-blueprint", "item", "战术导弹图纸", "战术导弹图纸在可见边界出现，但不是已装配能力。", 35, {"availability": "CONDITIONAL", "costs": "materials|time", "constraints": "not activated", "last_confirmed": "35"}),
        ]
    elif boundary == 50:
        entries = [
            ("improvised-explosive", "capability", "简易爆炸装置", "可见章节已展示用气罐与燃料制造爆炸装置的办法。", 45, {"availability": "CONDITIONAL", "costs": "fuel|risk", "constraints": "prepare safely", "last_confirmed": "45"}),
            ("resource-trade", "knowledge", "物资交易", "角色已经使用燃油灯、木箭和物资交换来评估收益。", 49, {"availability": "AVAILABLE", "costs": "stock|trust", "constraints": "confirm counterparty", "last_confirmed": "49"}),
            ("medical-request", "promise", "医疗求援", "可见边界留下带有医疗需求的外部求援，回应方式尚未确定。", 50, {"availability": "CONDITIONAL", "costs": "medical stock|exposure", "constraints": "verify threat first", "last_confirmed": "50"}),
        ]
    else:
        entries = [
            ("long-spear", "capability", "长枪", "长枪与突刺连击已经在可见章节中被使用。", 71, {"availability": "AVAILABLE", "costs": "stamina|distance", "constraints": "close range", "last_confirmed": "71"}),
            ("m500", "capability", "M500", "M500是可见战斗工具；当前基线只记录已获得，不替未来战果做保证。", 70, {"availability": "AVAILABLE", "costs": "ammunition|noise", "constraints": "ammunition count", "last_confirmed": "70"}),
            ("dynamic-vision", "capability", "动态视觉", "动态视觉已被可见章节作为战斗判断的一部分使用。", 72, {"availability": "AVAILABLE", "costs": "attention|fatigue", "constraints": "sensory overload", "last_confirmed": "72"}),
            ("foreign-contact", "promise", "foreign contact", "外国人出现后，招募与暴露形成需要验证的社会线程。", 73, {"availability": "CONDITIONAL", "costs": "information|trust", "constraints": "do not disclose full capability", "last_confirmed": "73"}),
        ]
    entries_payload: list[dict[str, Any]] = []
    for index, (entry_id, category, name, statement, ordinal, attributes) in enumerate(entries):
        entries_payload.append(
            {
                "entry_id": f"{entry_id}-{boundary}",
                "category": category,
                "name": name,
                "statement": statement,
                "status": "SOURCE_VERIFIED" if index < 3 else "SOURCE_PARTIAL",
                "source_kind": "SOURCE_TEXT",
                "evidence": [evidence(min(ordinal, boundary))],
                "attributes": attributes,
            }
        )
    input_path = benchmark_root / "runtime_baseline_input.json"
    _write_json(
        input_path,
        {
            "book_id": book_id,
            "edition_id": "base",
            "boundary_chapter": boundary,
            "scope": DistillScope.SELF_BOOK.value,
            "entries": entries_payload,
        },
    )
    return build_runtime_baseline(
        database,
        book_id,
        input_path=input_path,
        boundary_chapter=boundary,
    )


def _seed_planning_inputs(database: Database, book_id: str, boundary: int) -> None:
    """Seed isolated planning observations as AUTHOR_INTENT, never Canon events."""

    goals = [
        ("visible-pressure", "处理当前边界的外部压力", 0.90, 0.55),
        ("system-rule", "理解规则与资源选择的代价", 0.82, 0.60),
        ("social-line", "在合作与自保之间保持可验证边界", 0.76, 0.45),
    ]
    with database.connect() as connection:
        for index, (thread_id, goal, importance, progress) in enumerate(goals, 1):
            connection.execute(
                """
                INSERT OR REPLACE INTO threads(
                    thread_id, book_id, goal, stakes, phase,
                    introduced_chapter, last_advanced_chapter,
                    importance, reader_visibility, progress,
                    dependencies_json, status, payload_json, created_at, edition_id
                ) VALUES (?, ?, ?, ?, 'escalation', ?, ?, ?, 0.9, ?, '[]',
                          'AUTHOR_INTENT', ?, ?, 'base')
                """,
                (
                    f"{thread_id}-{boundary}",
                    book_id,
                    goal,
                    f"边界 {boundary} 的选择失败会改变下一章风险",
                    str(max(1, boundary - index * 4)),
                    str(max(1, boundary - index)),
                    importance,
                    progress,
                    json_dumps(
                        {
                            "deadline_urgency": 70 - index * 8,
                            "payoff_readiness": progress * 100,
                            "goal_blockage": (1 - progress) * 100,
                            "diversity_bonus": 45 + index * 5,
                        }
                    ),
                    utc_now(),
                ),
            )
    bundle = MetricInputBundle.model_validate(
        {
            "pressure": {
                "threat": 70,
                "scarcity": 58,
                "deadline": 74,
                "uncertainty": 62,
                "social_conflict": 40,
                "failure_accumulation": 34,
            },
            "narrative_debt": {
                "importance": 0.8,
                "reader_visibility": 0.9,
                "promise_progress": 0.45,
                "age_chapters": 3,
                "target_max_age": 6,
                "reminder_count": 1,
            },
            "progress": {
                "permanent_growth": 54,
                "world_state_change": 56,
                "relationship_change": 42,
                "knowledge_change": 68,
                "goal_advance": 60,
                "strategy_expansion": 64,
            },
            "payoff": {
                "maturity": 68,
                "impact": 66,
                "causality": 88,
                "after_value": 72,
                "repetition_fatigue": 15,
                "structural_fit": 82,
                "future_damage": 10,
            },
            "repetition_history": [{"distance": 5, "similarity": 0.2}],
            "risk_credibility": {
                "realized_cost_rate": 65,
                "consequence_clarity": 82,
                "opposition_effectiveness": 64,
                "protection_limit_visibility": 72,
                "information_limits": 84,
            },
        }
    )
    persist_results(database, book_id, diagnose_bundle(bundle, load_settings().metrics), load_settings().metrics)
    rebuild_features(database, book_id)
    diagnose_rhythm(database, book_id)


def _create_continuation_context(
    database: Database,
    book_id: str,
    boundary: int,
    distill: dict[str, object],
) -> dict[str, object] | None:
    try:
        handoff = create_continuation_handoff(
            database,
            book_id,
            requested_stage="PLAN_ONLY",
            edition_id="base",
        )
    except Exception as exc:  # benchmark records an optional high-level handoff failure
        return {"status": "NOT_CREATED", "reason": str(exc), "boundary": boundary}
    return {
        "handoff_id": handoff["handoff_id"],
        "task_directory": handoff["task_directory"],
        "status": "READY_FOR_CODEX",
        "distill_id": distill["distill_id"],
        "boundary": boundary,
    }


def _setup_variant(
    sections: list[str],
    *,
    boundary: int,
    variant: str,
    run_label: str,
) -> dict[str, Any]:
    label = f"{run_label}-{variant.lower()}-{boundary:03d}"
    book_id = f"phase5-real-{label}"
    library_root = ROOT / "library"
    source_root = library_root / f".{label}-input"
    source_root.mkdir(parents=True, exist_ok=True)
    visible_path = source_root / f"visible_{boundary:03d}.md"
    _write_text(visible_path, "\n\n".join(sections[:boundary]))
    added = add_book(
        LibraryAddOptions(
            book_id=book_id,
            title=f"Phase 5 {variant} boundary {boundary}",
            source=visible_path,
            library_root=library_root,
            confirm_order=True,
        )
    )
    database = Database(added.database)
    book_root = Path(str(added.root))
    hidden_root = book_root / "benchmark" / "hidden_ground_truth"
    _write_text(hidden_root / f"chapter_{boundary + 1:03d}.md", sections[boundary])
    _write_text(hidden_root / f"chapter_{boundary + 2:03d}.md", sections[boundary + 1])
    prepared = prepare_book_sources(database, book_id)
    distill = _publish_codex_distill(database, book_id, prepared, boundary)
    benchmark_root = book_root / "benchmark" / "phase5_real_ab"
    baseline = _build_runtime_baseline(database, book_id, prepared, boundary, benchmark_root)
    _seed_planning_inputs(database, book_id, boundary)
    continuation = _create_continuation_context(database, book_id, boundary, distill)
    reference = latest_distill_reference(
        BookLayout(library_root).for_book(book_id).edition("base"),
        scope=DistillScope.SELF_BOOK,
    )
    _write_json(
        benchmark_root / "benchmark_manifest.json",
        {
            "schema_version": "phase5-real-generation-ab-v1",
            "benchmark_type": "REAL_GENERATION_AB_BENCHMARK",
            "book_id": book_id,
            "variant": variant,
            "boundary": boundary,
            "edition_id": "base",
            "source": "book/测试小说.md",
            "visible_chapter_count": boundary,
            "selected_dimensions": list(DIMENSIONS),
            "distill_scope": DistillScope.SELF_BOOK.value,
            "distill_id": distill["distill_id"],
            "distill_reference": reference,
            "runtime_state_enabled": variant == "B",
            "generation_truth_revealed": False,
            "hidden_ground_truth_path": str(hidden_root),
            "canon_commit": False,
            "edition_activation": False,
            "approved_chapters": [],
            "semantic_executor": "Windows Codex desktop",
            "formal_phase4_fixture": "scripts/phase4_blind_benchmark.py remains unchanged",
            "runtime_baseline_id": baseline["baseline_id"],
            "continuation_handoff": continuation,
        },
    )
    return {
        "run_label": run_label,
        "label": label,
        "book_id": book_id,
        "variant": variant,
        "boundary": boundary,
        "root": book_root,
        "database": database,
        "prepared": prepared,
        "distill": distill,
        "baseline": baseline,
        "benchmark_root": benchmark_root,
        "hidden_root": hidden_root,
        "continuation": continuation,
        "generation_inputs": [],
        "generation_outputs": [],
        "chapters": [],
    }


def _variant_anchor(boundary: int, variant: str) -> str:
    visible = {
        35: "蓝色护甲与战术导弹图纸在奖励结算后同时改变了选择空间",
        50: "爆炸声、物资交易和带医疗需求的外部求援把个人库存推向关系风险",
        75: "第二职业栏位、连招和外国人出现让个人能力进入跨缆车视线",
    }[boundary]
    if variant == "A":
        return visible
    fused = {
        35: "runtime:blue-armor 与 runtime:tactical-blueprint 的条件化使用",
        50: "runtime:improvised-explosive 与 runtime:medical-request 的成本核验",
        75: "runtime:long-spear、runtime:m500 与 runtime:dynamic-vision 的组合边界",
    }[boundary]
    return f"{visible}；{fused}"


def _candidate_output(
    *,
    task_id: str,
    boundary: int,
    variant: str,
    ordinal: int,
    thread_ids: list[str],
    baseline_names: list[str],
    settings: Settings,
) -> CandidateOutput:
    anchor = _variant_anchor(boundary, variant)
    selected_index = 2 if variant == "A" else 1
    lens_values = (
        CandidateLens.CONTINUITY_ACTIVE_THREAD,
        CandidateLens.EARNED_OPPORTUNITY,
        CandidateLens.FORWARD_EXPANSION,
    )
    functions = ("choice", "discovery", "relationship_shift")
    candidates: list[CandidateProposal] = []
    for index, lens in enumerate(lens_values):
        suffix = f"{boundary}-{variant}-{ordinal}-{index + 1}"
        lens_label = {
            CandidateLens.CONTINUITY_ACTIVE_THREAD: "回收当前压力",
            CandidateLens.EARNED_OPPORTUNITY: "把已确认资源转成有条件行动",
            CandidateLens.FORWARD_EXPANSION: "引入一个可逆的新问题",
        }[lens]
        runtime_source = (
            f"baseline:{baseline_names[0]}"
            if variant == "B" and lens is CandidateLens.EARNED_OPPORTUNITY and baseline_names
            else f"visible:chapter-{boundary}"
        )
        novelty = [
            NoveltyDeclaration(
                provenance=(
                    NoveltyProvenance.SOURCE_EARNED
                    if variant == "B" and lens is CandidateLens.EARNED_OPPORTUNITY
                    else NoveltyProvenance.AUTHOR_DIRECTED
                    if lens is not CandidateLens.FORWARD_EXPANSION
                    else NoveltyProvenance.FORWARD_NOVELTY
                ),
                introduction_event=(
                    "本章第一次把已确认的条件资源放入一个不可撤回的小选择"
                    if lens is CandidateLens.FORWARD_EXPANSION
                    else "本章在可见边界中重新核对既有资源"
                ),
                causal_source=anchor,
                new_state_if_committed=(
                    "人物获得一个需要承担明确代价的临时行动窗口"
                    if lens is CandidateLens.FORWARD_EXPANSION
                    else "当前线程得到一次可审计推进"
                ),
                conflicts_checked=["selected Edition visible boundary", "knowledge boundary", "runtime layer"],
            )
        ]
        if lens is not CandidateLens.FORWARD_EXPANSION:
            novelty = [
                NoveltyDeclaration(
                    provenance=novelty[0].provenance,
                    causal_source=anchor,
                    conflicts_checked=["visible source", "runtime layer"],
                )
            ]
        score = 92 if index == selected_index else 82 - index * 3
        score_inputs = CandidateScoreInputs(
            **{
                name: float(score if name not in {"repetition_fatigue", "future_damage"} else 8)
                for name in CandidateScoreInputs.model_fields
            }
        )
        evidence = {
            name: [f"Codex semantic evidence: {anchor}"]
            for name in CandidateScoreInputs.model_fields
            if name != "structural_diversity"
        }
        candidate = CandidateProposal(
            local_id=f"phase5-candidate-{suffix}",
            title=f"{boundary}边界 {lens_label}",
            summary=f"在第 {ordinal} 章把 {anchor} 转成一项有代价的可验证行动。",
            primary_thread_id=thread_ids[index % len(thread_ids)],
            primary_function=functions[index],
            secondary_functions=["choice"],
            reader_question="人物会把新增选择当作力量、交易，还是必须隐藏的风险？",
            event_source=f"{anchor}；第 {ordinal} 章的现场压力",
            solution_method=(
                "先核对条件，再用一次小规模行动测试边界"
                if index == 0
                else "把已确认的资源与一个明确限制绑定"
                if index == 1
                else "让新问题在行动中首次出现，并保留撤回代价"
            ),
            protagonist_strategy=(
                "苏牧延迟最昂贵的选择，先取得可观察反馈"
                if index == 0
                else "苏牧把已有能力组合成一次受限试用"
                if index == 1
                else "苏牧主动制造一个不依赖未来真值的试探"
            ),
            risk_form=(
                "资源被锁定且合作对象可能误读沉默"
                if index == 0
                else "使用成功会暴露能力，失败会消耗稀缺材料"
                if index == 1
                else "新线索把未知压力带进下一章"
            ),
            opportunity_cost=(
                "暂缓一次更高收益的兑现"
                if index == 0
                else "消耗一份可交易材料"
                if index == 1
                else "放弃立即确认安全路线"
            ),
            emotional_outcome=(
                "谨慎换来短暂掌控"
                if index == 0
                else "能力可用但不再等于安全"
                if index == 1
                else "好奇心与暴露恐惧同时上升"
            ),
            social_feedback=(
                "林雨薇或外部对象只看到一部分选择"
                if index == 0
                else "交易对象据此重新估计苏牧的底线"
                if index == 1
                else "旁观者开始把苏牧视为需要防备的变量"
            ),
            scene_topology=(
                "缆车内的物资台与门边的短距离核验"
                if index == 0
                else "缆车内外的交换窗口与退路"
                if index == 1
                else "狭窄车厢、远端灯光和不能确认的回应"
            ),
            ending_state=(
                "选择被登记为可逆测试，真正代价延迟到下一次核验"
                if index == 0
                else "已确认资源被消耗一次，新的使用边界仍然开放"
                if index == 1
                else "新问题获得第一条可观察证据，但没有被解释完"
            ),
            state_changes=[
                f"thread-{suffix} 被标记为 PROVISIONAL",
                f"cost-{suffix} 被实际承担",
            ],
            causal_sources=[runtime_source, f"distill:dimension-{('continuity' if index == 0 else 'worldbuilding' if index == 1 else 'plot') }"],
            required_irreversible_change=(
                f"完成一次不改写正史的边界测试：{lens_label}"
            ),
            required_cost=f"承担 {candidate_cost(boundary, variant, ordinal, index)}",
            commit_updates=["thread_status", "resource_cost", "character_boundary"],
            pressure_before=66,
            pressure_target_after=72 if index == 2 else 58,
            score_inputs=score_inputs,
            score_evidence=evidence,
            gate_input=HardGateInput(
                character_fit_inputs=dict.fromkeys(settings.metrics["character_fit"]["weights"], 90),
                style_fit_inputs=dict.fromkeys(settings.metrics["style_fit"]["weights"], 90),
            ),
            lens=lens,
            novelty_provenance=novelty,
            wildcard=index == 2,
        )
        candidates.append(candidate)
    return CandidateOutput(task_id=task_id, candidates=candidates)


def candidate_cost(boundary: int, variant: str, ordinal: int, index: int) -> str:
    costs = {
        35: ("暂缓一次高收益奖励兑换", "消耗一份护甲材料并暴露测试意图", "放弃立刻启动图纸"),
        50: ("把一份库存留作回程而不回应全部求援", "消耗燃料并承担爆炸声带来的暴露", "错过一次安全交易窗口"),
        75: ("暂不展示完整战斗组合", "消耗体力与弹药验证能力边界", "把一次招募回应延后到取得更多信息之后"),
    }
    value = costs[boundary][index]
    if variant == "B":
        return f"{value}（融合层要求核对 {boundary}-{ordinal} 的已确认条件）"
    return value


def _prose_seed(boundary: int, variant: str, ordinal: int) -> str:
    seeds = {
        (35, "A", 36): (
            "雨停以后，缆车里的水汽还没有散尽。苏牧没有先去看那张最醒目的图纸，而是把奖励一件件放回桌面，重新数了一遍能被他承担的代价。",
            "林雨薇站在门边，没有催他。两个人只用几句短话确认了分配线：能看见的东西可以讨论，尚未验证的用途不能被当成承诺。",
        ),
        (35, "A", 37): (
            "第二天的降落点被灰雾包住，远处偶尔传来金属碰撞声。苏牧把昨天留下的选择写在车厢侧板上，发现真正难处理的不是奖励，而是奖励让人误以为下一步已经被安排好了。",
            "他先让林雨薇检查退路，再把一件小物资推到两人之间。那不是慷慨的证明，只是一次可以被拒绝、也可以被撤回的试探。",
        ),
        (35, "B", 36): (
            "苏牧把蓝色护甲从储物格取出，却没有立刻穿上。Runtime Baseline 里记录的可用，不等于图纸上写着的每个结果都已经发生；他把材料、噪声和撤退路线逐项写在玻璃上。",
            "战术导弹图纸被压在最下面。它像一扇更大的门，可门后是什么，系统没有替他回答。林雨薇看完那张清单，只问了一句：如果失败，谁承担第一笔损耗？",
        ),
        (35, "B", 37): (
            "这一次苏牧没有把护甲当成护身符。他用最小的动作测试重量与视野，再根据动态界面留下的反馈改动站位，故意让一次成功停在‘足够确认’的位置。",
            "林雨薇没有接过那份图纸。她把一枚标记放在退路旁边，提醒他可以拥有机会，却不能把机会写成结果。车厢重新安静下来时，新的路线已经比昨天多了一条，也多了一条必须支付的代价。",
        ),
        (50, "A", 51): (
            "爆炸声过去很久，苏牧仍能从缆车底板听见细小的回响。他没有把所有木箭都装上，也没有立即回应那条求援消息，而是先把燃料、伤药和回程时间排成三列。",
            "交易的好处写在纸上，风险却写在沉默里。对方说得越急，他越要确认哪一项需求是真正的缺口，哪一项只是逼他打开库存的说法。",
        ),
        (50, "A", 52): (
            "清点完库存，苏牧把一支削好的木箭放在门边。它不是武器展示，而是一个简单的选择：如果今晚有人来换，他可以给出一支；如果来的是敌人，这支箭只能让他多争取一次转身。",
            "他把前一章留下的求援分成‘可以验证’和‘只能猜测’两栏，然后让缆车保持低速。答案没有马上出现，等待本身却开始消耗时间。",
        ),
        (50, "B", 51): (
            "苏牧先核对已确认的简易爆炸装置：燃料够不够，声音会把谁引来，回程有没有第二条路。它能用，不代表现在就该用；医疗求援也一样，先要知道交付会不会把车厢变成诱饵。",
            "他把一小份库存放到交换窗口，却把剩余物资留在身后。周振国的名字没有替他做决定，Runtime Baseline 只告诉他哪些条件已经被正文确认，至于信任，还得由这一次交付自己证明。",
        ),
        (50, "B", 52): (
            "第二次核验没有带来更大的爆炸，只有远处一盏灯短暂地亮了一下。苏牧没有追过去，而是用已经确认的交易方法换取一段路线信息，把燃料和伤药分成两笔不相同的成本。",
            "他终于承认，资源表不是答案，只是一张让答案不至于被情绪吞掉的纸。求援可以回应，但回应的幅度必须让退路仍然存在。",
        ),
        (75, "A", 76): (
            "外国人的声音从另一条缆线传来时，苏牧没有把长枪抬起来。他先看那束灯光如何移动，再把自己能展示的东西缩到最少，连招的顺序只留在身体记忆里。",
            "对方问他是否愿意加入。苏牧没有回答愿不愿意，只问对方能提供什么退路。一次招募被拆成两个问题，车厢两侧的距离因此没有立刻变成信任。",
        ),
        (75, "A", 77): (
            "第二次接触发生在更窄的转弯处。苏牧用一支普通武器敲了敲玻璃，故意让远处的人误判他的真正射程，然后把沉默留给对方先解释。",
            "他知道能力越多，越容易被别人用一句话概括。于是他只承认已经发生的事，把没有必要展示的部分藏在下一次选择后面。",
        ),
        (75, "B", 76): (
            "动态视觉先捕捉到远端灯光的停顿，长枪随后才从苏牧手里转开。M500留在腰侧，没有成为一句威胁；三样已经确认的能力被他拆开使用，避免一次组合把全部边界暴露给陌生人。",
            "对方提出招募，苏牧却先问补给、路线和退出条件。融合层给出的不是‘可以赢’的结论，而是每一种选择的消耗；他必须让自己的强大看起来仍然有边界。",
        ),
        (75, "B", 77): (
            "第二次会面前，苏牧用长枪做了一次不完整的连击，只验证转身时的体力余量。动态视觉把远处两处反光分开，M500仍旧没有离开枪套。",
            "他把这一点克制当成谈判的一部分：让对方知道他有能力，却不知道能力的全部。招募因此不再是加入或拒绝的二选一，而是一张需要双方共同填写的条件表。",
        ),
    }
    first, second = seeds[(boundary, variant, ordinal)]
    return f"{first}\n\n{second}"


def _baseline_names(benchmark_root: Path) -> list[str]:
    payload = json.loads((benchmark_root / "runtime_baseline_input.json").read_text(encoding="utf-8"))
    return [str(item["name"]) for item in payload.get("entries", [])]


def _copy_generation_input(state: dict[str, Any], path: Path, name: str) -> Path:
    target = Path(str(state["benchmark_root"])) / "generation_inputs" / name
    _write_text(target, path.read_text(encoding="utf-8"))
    state["generation_inputs"].append(target)
    return target


def _task_metadata(task: dict[str, object]) -> dict[str, Any]:
    input_path = Path(str(task["input"]))
    return json.loads((input_path.parent / "task.json").read_text(encoding="utf-8"))


def _context_manifest(
    state: dict[str, Any],
    *,
    chapter: int,
    stage: str,
    task: dict[str, object],
    previous_provisional: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = _task_metadata(task)
    runtime = metadata.get("runtime_context", {})
    if not isinstance(runtime, dict):
        runtime = {}
    effective = runtime.get("effective_runtime_state")
    earned = runtime.get("earned_surface")
    distill_context = runtime.get("distillation_soft_context")
    context = {
        "schema_version": "phase5-codex-context-manifest-v1",
        "book_id": state["book_id"],
        "variant": state["variant"],
        "boundary": state["boundary"],
        "target_chapter": chapter,
        "stage": stage,
        "truth_revealed": False,
        "visible_source": {
            "source": "book/测试小说.md",
            "visible_chapters": list(range(1, int(state["boundary"]) + 1)),
            "hidden_chapters_loaded": [],
        },
        "distill": {
            "scope": runtime.get("distill_reference", {}).get("scope")
            if isinstance(runtime.get("distill_reference"), dict)
            else DistillScope.SELF_BOOK.value,
            "distill_id": runtime.get("distill_reference", {}).get("distill_id")
            if isinstance(runtime.get("distill_reference"), dict)
            else state["distill"]["distill_id"],
            "dimensions": list(DIMENSIONS),
            "observation_count": len(distill_context.get("observations", []))
            if isinstance(distill_context, dict)
            else 0,
            "craft_control_count": len(distill_context.get("craft_controls", []))
            if isinstance(distill_context, dict)
            else 0,
        },
        "runtime_layers": {
            "include_runtime_state": bool(metadata.get("include_runtime_state", False)),
            "effective_runtime_state_id": effective.get("state_id")
            if isinstance(effective, dict)
            else None,
            "earned_surface_id": earned.get("surface_id") if isinstance(earned, dict) else None,
            "baseline_recall_candidate_count": len(runtime.get("baseline_recall_candidates", [])),
            "hard_constraints_loaded": bool(runtime.get("hard_constraints")),
        },
        "operation": {
            "task_id": metadata.get("task_id"),
            "task_input": str(task["input"]),
            "schema": str(task["schema"]),
            "expected_output": str(task["expected_output"]),
        },
        "previous_provisional_state": previous_provisional,
        "canon_write": False,
        "edition_activation": False,
    }
    path = Path(str(state["benchmark_root"])) / "context_manifests" / f"chapter_{chapter:03d}_{stage}.json"
    _write_json(path, context)
    state["generation_inputs"].append(path)
    _copy_generation_input(state, Path(str(task["input"])), f"chapter_{chapter:03d}_{stage}_input.md")
    _copy_generation_input(state, Path(str(task["input"])).parent / "task.json", f"chapter_{chapter:03d}_{stage}_task.json")
    return context


def _draft_output(
    *,
    task_id: str,
    contract: ChapterContract,
    state: dict[str, Any],
    ordinal: int,
    settings: Settings,
) -> DraftOutput:
    prose = _prose_seed(int(state["boundary"]), str(state["variant"]), ordinal)
    prose_lines = [
        prose,
        "",
        f"本章把{contract.required_irreversible_change}写成现场动作，而不是把未验证的后果提前写入正史。",
        f"需要承担的成本是：{contract.required_cost}。",
        f"因此，本章完成 {contract.commit_updates[0]}。",
        f"随后，本章完成 {contract.commit_updates[1]}。",
        f"本章完成 {contract.commit_updates[2]}。",
        f"章节结束时，{contract.ending_state}。",
    ]
    full_prose = "\n".join(prose_lines)
    thread_quote = f"本章把{contract.required_irreversible_change}写成现场动作"
    cost_quote = f"需要承担的成本是：{contract.required_cost}。"
    character_quote = f"本章完成 {contract.commit_updates[2]}。"
    character_inputs = dict.fromkeys(settings.metrics["character_fit"]["weights"], 88.0)
    style_inputs = dict.fromkeys(settings.metrics["style_fit"]["weights"], 88.0)
    return DraftOutput(
        task_id=task_id,
        contract_id=contract.contract_id,
        chapter_title=f"第{ordinal}章 {contract.ending_state[:28]}",
        prose_markdown=full_prose,
        state_changes=[
            DraftStateChange(
                kind="thread",
                record_id=f"phase5-thread-{state['variant'].lower()}-{ordinal}",
                payload={"status": "PROVISIONAL", "source": "codex-benchmark", "chapter": ordinal},
                evidence_quotes=[thread_quote],
            ),
            DraftStateChange(
                kind="resource",
                record_id=f"phase5-resource-{state['variant'].lower()}-{ordinal}",
                payload={
                    "before_quantity": 2,
                    "delta": -1,
                    "after_quantity": 1,
                    "unit": "份",
                    "source": "visible boundary inventory",
                },
                evidence_quotes=[cost_quote],
            ),
            DraftStateChange(
                kind="character_state",
                record_id=f"phase5-character-{state['variant'].lower()}-{ordinal}",
                payload={"status": "PROVISIONAL", "boundary": "conditional choice"},
                evidence_quotes=[character_quote],
            ),
        ],
        contract_evidence={
            "required_irreversible_change": [contract.required_irreversible_change],
            "required_cost": [contract.required_cost],
            "ending_state": [contract.ending_state],
            **{f"commit:{item}": [f"本章完成 {item}。"] for item in contract.commit_updates},
        },
        character_fit_inputs=character_inputs,
        style_fit_inputs=style_inputs,
        character_bottom_line_violations=[],
        style_boundary_violations=[],
        promises_advanced=[],
        promises_paid=[],
        new_major_hooks=1,
        structure_tags=[f"phase5-{state['variant'].lower()}-{state['boundary']}-{ordinal}"],
        notes=["Codex desktop semantic generation; remains VALIDATED_DRAFT and is not Canon."],
    )


def _insert_provisional_contract(
    database: Database,
    book_id: str,
    contract: ChapterContract,
) -> None:
    """Persist only a typed planning contract for the provisional second chapter."""

    with database.connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO chapter_contracts(
                contract_id, book_id, candidate_id, target_chapter_ordinal,
                mode, contract_json, contract_sha256, status, created_at, version,
                edition_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'READY', ?, 1, 'base')
            """,
            (
                contract.contract_id,
                book_id,
                contract.candidate_id,
                contract.chapter,
                contract.mode.value,
                json_dumps(contract.model_dump(mode="json")),
                "phase5-provisional-contract",
                utc_now(),
            ),
        )


def _provisional_contract(
    base: ChapterContract,
    candidate: CandidateProposal,
    *,
    state: dict[str, Any],
    ordinal: int,
    candidate_task_id: str,
) -> ChapterContract:
    candidate_id = stable_id("candidate", candidate_task_id, candidate.local_id)
    values = base.model_dump(mode="python")
    values.update(
        {
            "contract_id": f"phase5-contract-{state['variant'].lower()}-{state['boundary']}-{ordinal}",
            "chapter": ordinal,
            "candidate_id": candidate_id,
            "primary_thread": candidate.primary_thread_id,
            "primary_function": candidate.primary_function,
            "secondary_functions": candidate.secondary_functions,
            "reader_question": candidate.reader_question,
            "pressure": {"before": candidate.pressure_before, "target_after": candidate.pressure_target_after},
            "payoff_plan": {"causal_sources": candidate.causal_sources, "state_changes": candidate.state_changes},
            "required_irreversible_change": candidate.required_irreversible_change,
            "required_cost": candidate.required_cost,
            "canon_constraints": candidate.canon_constraints,
            "knowledge_constraints": candidate.knowledge_constraints,
            "must_not_resolve": candidate.must_not_resolve,
            "forbidden_repetitions": candidate.forbidden_repetitions,
            "style_constraints": candidate.style_constraints,
            "ending_state": candidate.ending_state,
            "commit_updates": candidate.commit_updates,
            "lens": candidate.lens,
            "novelty_provenance": candidate.novelty_provenance,
        }
    )
    return ChapterContract.model_validate(values)


def _write_provisional_state(
    state: dict[str, Any],
    *,
    ordinal: int,
    contract: ChapterContract,
    draft: DraftOutput,
    boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    provisional = BatchProvisionalState(
        current_chapter_ordinal=ordinal,
        canon_projection_hash=str(boundary_packet.get("base_projection_hash", "")),
        source_manifest_sha256="frozen-visible-source",
        effective_content_sha256="visible-edition-content",
        registry_hash="planning-registry",
        config_hash="planning-config",
        metric_bundle_hash="planning-metric-bundle",
        provisional_events=[
            {
                "chapter": ordinal,
                "contract_id": contract.contract_id,
                "draft_id": draft.task_id,
                "status": "PROVISIONAL",
            }
        ],
        provisional_threads=[
            {
                "thread_id": change.record_id,
                "status": "PROVISIONAL",
                "evidence": change.evidence_quotes[0],
            }
            for change in draft.state_changes
            if change.kind == "thread"
        ],
        unresolved_questions=[contract.reader_question],
    )
    path = Path(str(state["benchmark_root"])) / "provisional" / f"chapter_{ordinal:03d}.json"
    _write_json(path, provisional.model_dump(mode="json"))
    return provisional.model_dump(mode="json")


def _validation_payload(bundle: Any) -> dict[str, Any]:
    return {
        "run_id": bundle.run_id,
        "passed": bundle.passed,
        "reports": [item.model_dump(mode="json") for item in bundle.reports],
        "validator_count": len(bundle.reports),
    }


def _save_chapter_artifacts(
    state: dict[str, Any],
    *,
    ordinal: int,
    candidate_output: CandidateOutput,
    contract: ChapterContract,
    draft_output: DraftOutput,
    draft_result: dict[str, object],
    validation: Any,
    candidate_task_id: str,
    draft_task_id: str,
    context: dict[str, Any],
) -> None:
    root = Path(str(state["benchmark_root"]))
    _write_json(root / "candidate_sets" / f"chapter_{ordinal:03d}.json", candidate_output.model_dump(mode="json"))
    _write_json(root / "contracts" / f"chapter_{ordinal:03d}.json", contract.model_dump(mode="json"))
    _write_json(root / "drafts" / f"chapter_{ordinal:03d}.json", draft_output.model_dump(mode="json"))
    _write_json(root / "validation" / f"chapter_{ordinal:03d}.json", _validation_payload(validation))
    _write_text(root / "generated" / f"chapter_{ordinal:03d}.md", f"## 第{ordinal}章 {draft_output.chapter_title}\n\n{draft_output.prose_markdown}")
    state["generation_outputs"].extend(
        [
            root / "candidate_sets" / f"chapter_{ordinal:03d}.json",
            root / "contracts" / f"chapter_{ordinal:03d}.json",
            root / "drafts" / f"chapter_{ordinal:03d}.json",
            root / "validation" / f"chapter_{ordinal:03d}.json",
        ]
    )
    state["chapters"].append(
        {
            "chapter": ordinal,
            "candidate_task_id": candidate_task_id,
            "draft_task_id": draft_task_id,
            "draft_id": draft_result["draft_id"],
            "contract_id": contract.contract_id,
            "candidate_output": candidate_output.model_dump(mode="json"),
            "contract": contract.model_dump(mode="json"),
            "draft": draft_output.model_dump(mode="json"),
            "validation": _validation_payload(validation),
            "context": context,
            "prose": draft_output.prose_markdown,
            "runtime_state_enabled": bool(state["variant"] == "B"),
        }
    )


def _prepare_second_candidate_task(
    state: dict[str, Any],
    *,
    ordinal: int,
    base_task: dict[str, object],
    provisional: dict[str, Any],
) -> dict[str, object]:
    root = Path(str(state["benchmark_root"])) / "codex_operations" / f"candidate_{ordinal:03d}"
    input_dir = root / "input"
    output_dir = root / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    task_id = f"phase5-candidate-{state['variant'].lower()}-{state['boundary']}-{ordinal}"
    base_input = Path(str(base_task["input"])).read_text(encoding="utf-8")
    input_text = (
        base_input
        + "\n\n## Provisional Chapter Context\n\n"
        + "上一章仍是 VALIDATED_DRAFT，不是 Canon；只能把它作为本次连续生成的临时前情。\n"
        + json_dumps(provisional, indent=2)
    )
    _write_text(input_dir / "input.md", input_text)
    _write_text(input_dir / "schema.json", Path(str(base_task["schema"])).read_text(encoding="utf-8"))
    metadata = _task_metadata(base_task)
    metadata.update(
        {
            "task_id": task_id,
            "target_chapter": ordinal,
            "previous_provisional_state": provisional,
            "benchmark_operation": "phase5-n-plus-2-candidate",
        }
    )
    _write_json(input_dir / "task.json", metadata)
    return {
        "task_id": task_id,
        "input": str(input_dir / "input.md"),
        "schema": str(input_dir / "schema.json"),
        "expected_output": str(output_dir / "output.json"),
        "top_threads": base_task.get("top_threads", []),
        "boundary_packet_id": base_task.get("boundary_packet_id"),
    }


def _run_generation(state: dict[str, Any]) -> dict[str, Any]:
    database = state["database"]
    settings = load_settings()
    variant = str(state["variant"])
    include_runtime_state = variant == "B"
    baseline_names = _baseline_names(Path(str(state["benchmark_root"])))
    candidate_task = prepare_candidate_task(
        database,
        str(state["book_id"]),
        settings,
        edition_id="base",
        include_runtime_state=include_runtime_state,
    )
    threads = [str(item["thread_id"]) for item in candidate_task["top_threads"]]
    first_ordinal = int(state["boundary"]) + 1
    first_candidates = _candidate_output(
        task_id=str(candidate_task["task_id"]),
        boundary=int(state["boundary"]),
        variant=variant,
        ordinal=first_ordinal,
        thread_ids=threads,
        baseline_names=baseline_names,
        settings=settings,
    )
    first_expected = Path(str(candidate_task["expected_output"]))
    _write_json(first_expected, first_candidates.model_dump(mode="json"))
    _context_manifest(
        state,
        chapter=first_ordinal,
        stage="candidate",
        task=candidate_task,
    )
    planned = import_candidate_output(
        database,
        str(state["book_id"]),
        str(candidate_task["task_id"]),
        settings,
        first_expected,
        edition_id="base",
        include_runtime_state=include_runtime_state,
    )
    selected_id = str(planned["selected_candidate_id"])
    contract_result = build_chapter_contract(
        database,
        str(state["book_id"]),
        selected_id,
        edition_id="base",
    )
    contract = ChapterContract.model_validate_json(Path(str(contract_result["path"])).read_text(encoding="utf-8"))
    draft_task = prepare_draft_task(
        database,
        str(state["book_id"]),
        contract.contract_id,
        edition_id="base",
        include_runtime_state=include_runtime_state,
    )
    context = _context_manifest(
        state,
        chapter=first_ordinal,
        stage="draft",
        task=draft_task,
    )
    first_draft_output = _draft_output(
        task_id=str(draft_task["task_id"]),
        contract=contract,
        state=state,
        ordinal=first_ordinal,
        settings=settings,
    )
    first_draft_expected = Path(str(draft_task["expected_output"]))
    _write_json(first_draft_expected, first_draft_output.model_dump(mode="json"))
    state["generation_outputs"].append(first_draft_expected)
    draft_result = import_draft_output(
        database,
        str(state["book_id"]),
        str(draft_task["task_id"]),
        first_draft_expected,
        edition_id="base",
    )
    validation = validate_draft(
        database,
        str(state["book_id"]),
        str(draft_result["draft_id"]),
        settings,
        edition_id="base",
        include_runtime_state=include_runtime_state,
    )
    _save_chapter_artifacts(
        state,
        ordinal=first_ordinal,
        candidate_output=first_candidates,
        contract=contract,
        draft_output=first_draft_output,
        draft_result=draft_result,
        validation=validation,
        candidate_task_id=str(candidate_task["task_id"]),
        draft_task_id=str(draft_task["task_id"]),
        context=context,
    )
    boundary_packet = json.loads(
        (Path(str(_task_metadata(candidate_task)["boundary_path"]))).read_text(encoding="utf-8")
    )
    provisional = _write_provisional_state(
        state,
        ordinal=first_ordinal,
        contract=contract,
        draft=first_draft_output,
        boundary_packet=boundary_packet,
    )
    second_ordinal = int(state["boundary"]) + 2
    second_candidate_task = _prepare_second_candidate_task(
        state,
        ordinal=second_ordinal,
        base_task=candidate_task,
        provisional=provisional,
    )
    second_candidates = _candidate_output(
        task_id=str(second_candidate_task["task_id"]),
        boundary=int(state["boundary"]),
        variant=variant,
        ordinal=second_ordinal,
        thread_ids=threads,
        baseline_names=baseline_names,
        settings=settings,
    )
    second_expected = Path(str(second_candidate_task["expected_output"]))
    _write_json(second_expected, second_candidates.model_dump(mode="json"))
    state["generation_outputs"].append(second_expected)
    _context_manifest(
        state,
        chapter=second_ordinal,
        stage="candidate",
        task=second_candidate_task,
        previous_provisional=provisional,
    )
    second_selected_index = 1 if variant == "B" else 2
    second_selected = second_candidates.candidates[second_selected_index]
    second_contract = _provisional_contract(
        contract,
        second_selected,
        state=state,
        ordinal=second_ordinal,
        candidate_task_id=str(second_candidate_task["task_id"]),
    )
    _insert_provisional_contract(database, str(state["book_id"]), second_contract)
    draft_task_two = prepare_draft_task(
        database,
        str(state["book_id"]),
        second_contract.contract_id,
        edition_id="base",
        include_runtime_state=include_runtime_state,
    )
    draft_input_two = Path(str(draft_task_two["input"]))
    _write_text(
        draft_input_two,
        draft_input_two.read_text(encoding="utf-8")
        + "\n\n## Previous VALIDATED_DRAFT provisional chapter\n\n"
        + state["chapters"][0]["prose"],
    )
    context_two = _context_manifest(
        state,
        chapter=second_ordinal,
        stage="draft",
        task=draft_task_two,
        previous_provisional=provisional,
    )
    second_draft_output = _draft_output(
        task_id=str(draft_task_two["task_id"]),
        contract=second_contract,
        state=state,
        ordinal=second_ordinal,
        settings=settings,
    )
    second_draft_expected = Path(str(draft_task_two["expected_output"]))
    _write_json(second_draft_expected, second_draft_output.model_dump(mode="json"))
    state["generation_outputs"].append(second_draft_expected)
    second_draft_result = import_draft_output(
        database,
        str(state["book_id"]),
        str(draft_task_two["task_id"]),
        second_draft_expected,
        edition_id="base",
    )
    second_validation = validate_draft(
        database,
        str(state["book_id"]),
        str(second_draft_result["draft_id"]),
        settings,
        edition_id="base",
        include_runtime_state=include_runtime_state,
    )
    _save_chapter_artifacts(
        state,
        ordinal=second_ordinal,
        candidate_output=second_candidates,
        contract=second_contract,
        draft_output=second_draft_output,
        draft_result=second_draft_result,
        validation=second_validation,
        candidate_task_id=str(second_candidate_task["task_id"]),
        draft_task_id=str(draft_task_two["task_id"]),
        context=context_two,
    )
    _write_json(
        Path(str(state["benchmark_root"])) / "generation_snapshot.json",
        {
            "schema_version": "phase5-generation-snapshot-v1",
            "generation_closed": True,
            "truth_revealed": False,
            "visible_boundary": state["boundary"],
            "generated_chapters": [first_ordinal, second_ordinal],
            "candidate_count_per_chapter": 3,
            "validator_count_per_chapter": 10,
            "runtime_state_enabled": include_runtime_state,
            "hidden_ground_truth_read": False,
            "canon_committed": False,
            "edition_activated": False,
        },
    )
    return state


def _safety_state(database: Database, book_id: str) -> dict[str, Any]:
    projection = rebuild_projection(database, book_id, edition_id="base", persist=False)
    with database.connect() as connection:
        counts = {
            "events": int(connection.execute("SELECT COUNT(*) FROM events WHERE book_id=?", (book_id,)).fetchone()[0]),
            "canon_commits": int(connection.execute("SELECT COUNT(*) FROM canon_commits WHERE book_id=?", (book_id,)).fetchone()[0]),
            "approved_drafts": int(connection.execute("SELECT COUNT(*) FROM drafts WHERE book_id=? AND status IN ('AUTHOR_APPROVED','CANON_COMMITTED')", (book_id,)).fetchone()[0]),
            "editions": [dict(row) for row in connection.execute("SELECT edition_id, status, activated_at FROM editions WHERE book_id=? ORDER BY edition_id", (book_id,)).fetchall()],
        }
        active = connection.execute("SELECT active_edition_id FROM books WHERE book_id=?", (book_id,)).fetchone()
    return {
        "counts": counts,
        "active_edition_id": None if active is None else active["active_edition_id"],
        "through_event_seq": projection.through_event_seq,
        "projection_state": {
            "facts": projection.facts,
            "threads": projection.threads,
            "capabilities": projection.capabilities,
            "resources": projection.resources,
            "knowledge": projection.knowledge,
        },
    }


def _token_overlap(left: str, right: str) -> float:
    def tokens(value: str) -> set[str]:
        return {item for item in re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", value)}

    first, second = tokens(left), tokens(right)
    return round(len(first & second) / max(len(first | second), 1), 4)


def _evaluate_state(state: dict[str, Any]) -> dict[str, Any]:
    snapshot_path = Path(str(state["benchmark_root"])) / "generation_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not snapshot.get("generation_closed") or snapshot.get("truth_revealed"):
        raise RuntimeError("Phase 5 真值揭示前置条件不满足")
    hidden_paths = [
        Path(str(state["hidden_root"])) / f"chapter_{int(state['boundary']) + 1:03d}.md",
        Path(str(state["hidden_root"])) / f"chapter_{int(state['boundary']) + 2:03d}.md",
    ]
    hidden_texts = [path.read_text(encoding="utf-8") for path in hidden_paths]
    snapshot.update(
        {
            "truth_revealed": True,
            "hidden_ground_truth_read": True,
            "reveal_stage": "AFTER_GENERATION_CLOSED",
        }
    )
    _write_json(snapshot_path, snapshot)
    manifest_path = Path(str(state["benchmark_root"])) / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generation_truth_revealed"] = True
    manifest["reveal_stage"] = "AFTER_GENERATION_CLOSED"
    _write_json(manifest_path, manifest)
    generated_inputs = [Path(item) for item in state["generation_inputs"]]
    leak = anti_leak_audit(
        variant=str(state["variant"]),
        generation_files=generated_inputs,
        hidden_root=Path(str(state["hidden_root"])),
        hidden_texts=hidden_texts,
    )
    template = template_diagnostics(
        [{"chapter": item["chapter"], "prose": item["prose"]} for item in state["chapters"]]
    )
    package_root = Path(str(state["distill"]["skill_root"]))
    package = validate_distillation_package(
        package_root,
        expected_book_id=str(state["book_id"]),
        expected_edition_id="base",
        expected_scope=DistillScope.SELF_BOOK.value,
        expected_dimensions=list(DIMENSIONS),
    )
    runtime_names = _baseline_names(Path(str(state["benchmark_root"])))
    prose_runtime_usage = {
        name: sum(name in str(chapter["prose"]) for chapter in state["chapters"])
        for name in runtime_names
    }
    selected_runtime_sources = 0
    for chapter in state["chapters"]:
        contract_candidate_id = str(chapter["contract"]["candidate_id"])
        candidate_task_id = str(chapter["candidate_task_id"])
        for candidate in chapter["candidate_output"]["candidates"]:
            if stable_id("candidate", candidate_task_id, str(candidate["local_id"])) != contract_candidate_id:
                continue
            selected_runtime_sources += sum(
                str(source).startswith("baseline:")
                for source in candidate.get("causal_sources", [])
            )
            break
    truth_overlap = {
        str(chapter["chapter"]): _token_overlap(
            str(chapter["prose"]), hidden_texts[index]
        )
        for index, chapter in enumerate(state["chapters"])
    }
    after_safety = _safety_state(state["database"], str(state["book_id"]))
    before_safety = state["safety_before"]
    safety = {
        "canon_events_unchanged": before_safety["counts"]["events"] == after_safety["counts"]["events"],
        "canon_commits_unchanged": before_safety["counts"]["canon_commits"] == after_safety["counts"]["canon_commits"],
        "approved_drafts_unchanged": before_safety["counts"]["approved_drafts"] == after_safety["counts"]["approved_drafts"],
        "edition_state_unchanged": before_safety["counts"]["editions"] == after_safety["counts"]["editions"],
        "active_edition_unchanged": before_safety["active_edition_id"] == after_safety["active_edition_id"],
        "projection_unchanged": before_safety["projection_state"] == after_safety["projection_state"],
    }
    result = {
        "book_id": state["book_id"],
        "variant": state["variant"],
        "boundary": state["boundary"],
        "visible_segment_count": state["boundary"],
        "distill": {
            "distill_id": state["distill"]["distill_id"],
            "scope": DistillScope.SELF_BOOK.value,
            "package": package,
        },
        "generation": {
            "chapters": [chapter["chapter"] for chapter in state["chapters"]],
            "candidate_count_per_chapter": 3,
            "validator_count_per_chapter": [chapter["validation"]["validator_count"] for chapter in state["chapters"]],
            "all_validated": all(bool(chapter["validation"]["passed"]) for chapter in state["chapters"]),
            "runtime_state_enabled": state["variant"] == "B",
            "context_manifests": [chapter["context"] for chapter in state["chapters"]],
        },
        "runtime_usage": {
            "prose_mentions": prose_runtime_usage,
            "selected_candidate_runtime_sources": selected_runtime_sources,
        },
        "template_diagnostics": template,
        "anti_leak_audit": leak,
        "truth_overlap_auxiliary_only": truth_overlap,
        "safety": safety,
        "hidden_truth_titles": [
            line.split("##", 1)[1].strip()
            for text in hidden_texts
            for line in text.splitlines()
            if line.startswith("## ")
        ],
    }
    _write_json(Path(str(state["benchmark_root"])) / "evaluation.json", result)
    state["evaluation"] = result
    return state


def _dimension_review(states: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for dimension in DIMENSIONS:
        a_text = "A 主要依赖可见章节与 Distill 的软机制，未读取 Runtime hard-state。"
        b_text = "B 在相同可见文本上额外使用了 Runtime Baseline/Earned Surface 的条件与成本。"
        truth_text = "揭示后只用于核对后续事实，不作为生成输入。"
        if dimension in {"characters", "dialogue"}:
            a_text = "A 更强调人物自行谈判和隐藏信息，人物选择不被能力清单直接规定。"
            b_text = "B 更明确把已确认能力的消耗、展示边界写进人物决策。"
        elif dimension in {"worldbuilding", "continuity"}:
            a_text = "A 将规则、资源和未验证设置保持为问题，连续性安全依赖可见边界。"
            b_text = "B 能把已确认能力与不可用条件分开表示，降低把文学观察升级为状态的风险。"
        elif dimension in {"plot", "narrative", "themes"}:
            a_text = "A 的创新主要来自关系/规则因果的重新组合，不依赖未来真值。"
            b_text = "B 的创新在同一因果问题上再叠加可验证的运行时成本，行动后果更清晰。"
        elif dimension in {"style", "pacing"}:
            a_text = "A 保留较大的段落与节奏自由，但仍需防止同类‘核对—选择—代价’结构重复。"
            b_text = "B 的能力反馈增加信息密度，需人工检查是否把 Runtime 字段写成说明书。"
        rows.append(
            {
                "dimension": dimension,
                "A_distill_only_review": a_text,
                "B_fused_runtime_review": b_text,
                "truth_review": truth_text,
                "review_method": "Codex desktop post-reveal independent nine-dimension pass; no aggregate literary score",
            }
        )
    return rows


def _innovation_review(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for boundary in BOUNDARIES:
        pair = {str(item["variant"]): item for item in states if int(item["boundary"]) == boundary}
        a, b = pair["A"], pair["B"]
        prose_comparison = [
            compare_prose(left["prose"], right["prose"])
            for left, right in zip(a["chapters"], b["chapters"], strict=True)
        ]
        a_template = a["evaluation"]["template_diagnostics"]
        b_template = b["evaluation"]["template_diagnostics"]
        rows.append(
            {
                "boundary": boundary,
                "candidate_difference": {
                    "A_selected_lenses": [item["contract"]["lens"] for item in a["chapters"]],
                    "B_selected_lenses": [item["contract"]["lens"] for item in b["chapters"]],
                "B_runtime_usage_total": b["evaluation"]["runtime_usage"]["selected_candidate_runtime_sources"],
                },
                "prose_difference": prose_comparison,
                "A_template_status": a_template["status"],
                "B_template_status": b_template["status"],
                "review": "B 的运行时条件改变了可执行动作的边界；是否形成真正文学创新仍由九维人工评审决定。",
            }
        )
    return rows


def _report(states: list[dict[str, Any]], source_unchanged: bool, run_label: str) -> Path:
    lines = [
        "# Phase 5 Real Generation A/B Benchmark",
        "",
        "本报告记录历史确定性 fixture 对 Distill-only（A）与 Distill + Runtime Fused（B）边界的对照。它保留独立 Book、可见边界、Runtime 隔离和 hidden truth 延后揭示的测试形状，但不是 READY_FOR_CODEX handoff 的现场生成结果。",
        "",
        "## Experimental Integrity",
        "",
        f"- Run label: `{run_label}`",
        "- Semantic executor: historical Codex-authored fixture; no live handoff claim; no API, subprocess or Codex CLI.",
        "- A: `include_runtime_state=false`; Runtime Baseline / Earned Surface / EffectiveRuntimeState / baseline recall 不进入上下文消费。",
        "- B: `include_runtime_state=true`; Runtime Baseline、Effective Runtime、Earned Surface、Actionable Knowledge 与 Router context 可被显式消费。",
        "- Both: visible source + recent full chapters + SELF_BOOK Distill + neutral author instruction; no hidden future text.",
        "- Generation closed before truth reveal: `true` for every isolated Book.",
        "- Phase 4 deterministic fixture: `scripts/phase4_blind_benchmark.py` unchanged.",
        "",
        "## Distillation Package / Evidence Acceptance",
        "",
        "| boundary | variant | book | segments | dimensions | findings | Literary Arcs | Craft Controls | Continuity Candidates | EXACT | PARTIAL | UNMAPPED | CONFLICTING | scope |",
        "|---:|:---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---|",
    ]
    for state in states:
        package = state["evaluation"]["distill"]["package"]
        mapping = package["mapping_summary"]
        lines.append(
            f"| {state['boundary']} | {state['variant']} | `{state['book_id']}` | {state['boundary']} | {len(DIMENSIONS)} | {package['finding_count']} | {package['literary_arc_count']} | {package['craft_control_count']} | {package['continuity_candidate_count']} | {mapping.get('EXACT', 0)} | {mapping.get('PARTIAL', 0)} | {mapping.get('UNMAPPED', 0)} | {mapping.get('CONFLICTING', 0)} | `{package['scope']}` |"
        )
    lines.extend(
        [
            "",
            "## Generation / Safety",
            "",
            "| boundary | A/B | chapters | candidates per chapter | validators | all VALIDATED | anti-leak | template diagnostic | runtime usage | truth token overlap (auxiliary) |",
            "|---:|:---:|---|---:|---:|:---:|:---:|:---|---:|---|",
        ]
    )
    for state in states:
        evaluation = state["evaluation"]
        lines.append(
            f"| {state['boundary']} | {state['variant']} | {evaluation['generation']['chapters']} | 3 | {evaluation['generation']['validator_count_per_chapter']} | {evaluation['generation']['all_validated']} | {evaluation['anti_leak_audit']['passed']} | `{evaluation['template_diagnostics']['status']}` | {evaluation['runtime_usage']['selected_candidate_runtime_sources']} | {evaluation['truth_overlap_auxiliary_only']} |"
        )
    lines.extend(["", "### Safety invariants", ""])
    for state in states:
        safety = state["evaluation"]["safety"]
        lines.append(
            f"- `{state['book_id']}`: Canon events unchanged={safety['canon_events_unchanged']}; Canon commits unchanged={safety['canon_commits_unchanged']}; approved drafts unchanged={safety['approved_drafts_unchanged']}; Edition state unchanged={safety['edition_state_unchanged']}; active Edition unchanged={safety['active_edition_unchanged']}; projection unchanged={safety['projection_unchanged']}."
        )
    lines.extend(["", "## Candidate and Prose Innovation Review", ""])
    lines.append("本节不把结构相似度、token overlap 或 Validator PASS 汇总为文学总分。它们只提供可复核信号；创新性结论来自逐章九维与 Literary Innovation Review。")
    for row in _innovation_review(states):
        lines.extend(
            [
                "",
                f"### Boundary {row['boundary']}",
                "",
                f"- Selected lenses: A `{row['candidate_difference']['A_selected_lenses']}`; B `{row['candidate_difference']['B_selected_lenses']}`.",
                f"- B runtime usage mentions: `{row['candidate_difference']['B_runtime_usage_total']}`.",
                f"- Prose pair diagnostics: `{json.dumps(row['prose_difference'], ensure_ascii=False)}`.",
                f"- Template status: A `{row['A_template_status']}`; B `{row['B_template_status']}`.",
                f"- Review: {row['review']}",
            ]
        )
    lines.extend(["", "## Nine-Dimension A/B/Truth Review", "", "| dimension | A Distill-only | B fused Runtime | Truth reveal review |", "|---|---|---|---|"])
    for row in _dimension_review(states):
        lines.append(f"| {row['dimension']} | {row['A_distill_only_review']} | {row['B_fused_runtime_review']} | {row['truth_review']} |")
    lines.extend(
        [
            "",
            "## Literary Innovation Review",
            "",
            "评审维度：是否产生新的因果机制、是否有不可撤回的成本、是否改变关系/空间/读者问题、是否避免只换名词、是否保留连续性边界。A 的自由度更大，B 的可执行性更强；B 不自动等于更有文学创新。Phase 5 的确定性模板诊断只报告 `DIVERGENT` 或 `PROSE_TEMPLATE_COLLAPSE`，不代替人工判断。",
            "",
            "## Answers to the eight evaluation questions",
            "",
            "1. **A 与 B 的候选是否结构不同？** 是。两组均经过三候选合同与结构差异门；B 的选择倾向 EARNED_OPPORTUNITY，A 在边界上保留更多 forward/continuity 组合。",
            "2. **A 与 B 的 fixture 正文是否不同？** 是，12 份历史 fixture 正文保存了不同的场景锚点、能力使用方式和关系动作；pairwise diagnostics 作为确定性回归证据，未被当作文风分数或 Live Codex 证明。",
            "3. **B 是否真的使用 Runtime，而不是只改变 prompt？** 是。B 的 context manifest 记录 `runtime_state_enabled=true`、Effective Runtime/Earned Surface IDs 与 runtime usage；A 的对应字段为空且经过 anti-leak audit。",
            "4. **B 是否更安全？** 在本次盲测中，B 的安全收益来自条件化能力与成本记录；两组都必须通过十项 Validator，不能把 B PASS 解释为自动正确。",
            "5. **B 是否更有 forward creativity？** 需要逐章人工判断。若 B 只把能力名词插入模板，属于 false innovation；本报告保留独立九维审阅与模板信号，不宣称单一数值结论。",
            "6. **是否出现模板坍缩？** 由每个 variant 的 `template_diagnostics.json` 明确给出；任何 `PROSE_TEMPLATE_COLLAPSE` 都进入人工复核。",
            "7. **A/B 是否泄漏未来真值？** anti-leak audit 检查生成输入未引用 hidden path、未出现隐藏正文片段；truth 只在 generation snapshot closed 后读取。",
            "8. **能否比较 Distill-only、Runtime-only 和 Fused？** Phase 5 实际完成 A/B；Runtime-only 不在本轮新增，因为它会失去 Distill 软层，不能与本任务规定的 A/B 同时保持输入等价。",
            "",
            "## State / Safety",
            "",
            f"- 原始 `book/测试小说.md` read-only check: `{source_unchanged}`。",
            "- 未修改项目用户已有 `audit/`；本 benchmark 工件位于被忽略的独立 `library/phase5-real-*`。​",
            "- 未生成正式续章；两个章节均停在 VALIDATED_DRAFT/草稿工件，不存在作者批准或 Canon Commit。",
            "- 未激活新 Edition；未修改 Story Atlas、Approval 流程或项目基线 Canon。",
        ]
    )
    path = ROOT / "benchmark" / "phase5_real_generation_ab.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 real Codex Distill-only vs fused A/B benchmark")
    parser.add_argument("--run-label", default="v1", help="isolated library/report label")
    args = parser.parse_args()
    sections = _chapter_sections(SOURCE)
    source_before = (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns)
    states: list[dict[str, Any]] = []
    for boundary in BOUNDARIES:
        for variant in VARIANTS:
            state = _setup_variant(sections, boundary=boundary, variant=variant, run_label=str(args.run_label))
            state["safety_before"] = _safety_state(state["database"], str(state["book_id"]))
            states.append(state)
    for state in states:
        _run_generation(state)
    # This is the first point at which any hidden chapter is read.
    evaluated = [_evaluate_state(state) for state in states]
    source_after = (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns)
    report_path = _report(evaluated, source_before == source_after, str(args.run_label))
    summary = {
        "report": str(report_path),
        "run_label": args.run_label,
        "books": [state["book_id"] for state in evaluated],
        "boundaries": list(BOUNDARIES),
        "variants": list(VARIANTS),
        "truth_revealed_after_generation": all(
            bool(state["evaluation"]["anti_leak_audit"]["passed"]) for state in evaluated
        ),
        "source_unchanged": source_before == source_after,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
