"""cli.py —— 入口：init / analyze / plan / record 四个子命令。

用法：``python -m novelwriter <子命令>``。
- 所有子命令幂等；支持 --dry-run（打印将要做的事，不落盘）。
- 报告类内容写 UTF-8 文件；stdout 仅输出简短进度，规避 GBK 代码页问题。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import contract as contract_mod
from . import loader, llm, scheduler, state
from . import metrics as M

PRESSURE_ORDER = list(M.PRESSURE_WEIGHTS.keys())


def _print(msg: str) -> None:
    """安全打印：控制台编码不支持时降级为 ascii 转义。"""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, errors="backslashreplace").decode(enc,
                                                                 errors="replace"))


def _fail(msg: str) -> None:
    _print(f"[error] {msg}")
    sys.exit(2)


def _load_project(slug: str):
    book = state.load_book(slug)
    if not book:
        _fail(f"project not found: projects/{slug} (run init first)")
    hooks = state.load_hooks(slug)
    history = state.load_history(slug)
    return book, hooks, history


# ---------------------------------------------------------------------------
# 指标汇总（analyze 与 plan 共用）
# ---------------------------------------------------------------------------


def _consume_income_ratio(res: dict):
    cost, income = res.get("daily_cost"), res.get("daily_income")
    if cost is None:
        return None
    if income is None or income <= 0:
        return 100.0 if cost and cost > 0 else 0.0
    return max(0.0, min(100.0, (cost / income) * 50.0))


def _blocked_score(res: dict):
    blocked = res.get("blocked_count")
    if blocked is None:
        return None
    return max(0.0, min(100.0, int(blocked) * 20.0))


def _payoff_from_draft(draft: dict, fatigue, fatigue_ev: dict) -> tuple:
    """按作者 payoff_draft 汇总爽点净分 S（宪章 2.2）。

    M/I/C/A 子项与 D 来自 book.json 的 payoff_draft（metrics 不猜事实）；
    N/F 由爽点历史自动计算。任一子项缺失即视为未填，返回 (None, ...)，
    报告保持「待作者填写」措辞。
    """
    m = M.maturity_score(draft.get("M") or {})
    i = M.impact_score(draft.get("I") or {})
    c = M.plausibility_score(draft.get("C") or {})
    a = M.aftermath_value_score(draft.get("A") or {})
    d_raw = draft.get("D")
    d = float(d_raw) if isinstance(d_raw, (int, float)) and \
        not isinstance(d_raw, bool) else None
    n = fatigue_ev.get("novelty")
    score, ev = M.payoff_score(m, i, n, c, a, fatigue, d)
    if score is None:
        return None, {"note": "payoff_draft 未填齐，S 待作者填写",
                      "missing": ev.get("missing", []),
                      "novelty_N": n, "fatigue_F": fatigue}
    return score, {"score": score, "M": m, "I": i, "N": n, "C": c,
                   "A": a, "F": fatigue, "D": d,
                   "novelty_N": n, "fatigue_F": fatigue}


def compute_metrics(book: dict, hooks: list, history: dict,
                    chapter_no: int) -> dict:
    """汇总六指标；台账缺失的维度返回 None，报告标注「待作者填写」。"""
    results: dict = {}

    p_total, p_ev = M.pressure_score(book.get("pressure") or {})
    results["pressure_total"], results["pressure_evidence"] = p_total, p_ev

    rp = {}
    for res in book.get("resources") or []:
        comps = {
            "gap": res.get("gap"),
            "consume_income_ratio": _consume_income_ratio(res),
            "blocked_count": _blocked_score(res),
            "next_tier_demand": res.get("next_tier_demand"),
            "perceptibility": res.get("perceptibility"),
        }
        score, _ev = M.resource_pressure(comps)
        rp[res.get("name", "")] = score
    results["resource_pressures"] = rp

    events = history.get("payoff_events") or []
    fatigue, f_ev = M.repetition_fatigue(events)
    results["repetition"] = (fatigue, f_ev)

    # payoff 净分：M/I/C/A/D 来自作者 payoff_draft；N/F 自动计算（宪章 2.2）
    results["payoff"] = _payoff_from_draft(book.get("payoff_draft") or {},
                                           fatigue, f_ev)

    results["narrative_debts"] = M.narrative_debt(hooks, chapter_no)
    balanced, b_ev = M.hook_balance_check(history.get("hook_events") or [])
    results["hook_balance"] = (balanced, b_ev)

    prog, prog_ev = M.progress_score(book.get("progress_components") or {})
    results["progress"], results["progress_evidence"] = prog, prog_ev

    risk, risk_ev = M.risk_credibility(book.get("risk_factors") or {})
    results["risk"], results["risk_evidence"] = risk, risk_ev
    return results


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def cmd_init(args) -> int:
    source = Path(args.source)
    if not source.exists():
        _fail(f"source file not found: {source}")
    if source.suffix.lower() not in (".md", ".txt"):
        _fail(f"unsupported source type: {source.suffix} (need .md/.txt)")

    sha = state.file_sha256(source)
    text, encoding = loader.read_text(source)
    idx = loader.build_chapter_index(source, text)
    entries, warning = idx["entries"], idx["warning"]
    fm = idx["frontmatter"]
    title = fm.get("title") or source.stem
    slug = args.slug or state.resolve_slug(source.stem, sha)

    if args.dry_run:
        _print(f"[dry-run] init: slug={slug} encoding={encoding} "
               f"chapters={len(entries)}")
        if warning:
            _print(f"[dry-run] warning: {warning}")
        _print(f"[dry-run] would create projects/{slug}/ "
               "(book.json hooks.json history.json chapters_index.json "
               "contracts/ prompts/ chapters/ reports/)")
        return 0

    project = state.project_dir(slug)
    for sub in ("contracts", "prompts", "chapters", "reports"):
        (project / sub).mkdir(parents=True, exist_ok=True)

    index_doc = {
        "source_path": state.normalize_source_path(source),
        "source_sha256": sha,
        "mtime": source.stat().st_mtime,
        "encoding": encoding,
        "warning": warning,
        "frontmatter": fm,
        "entries": entries,
    }
    state.save_index(slug, index_doc)

    book_path = state.project_path(slug, state.BOOK_FILE)
    if book_path.exists():
        _print(f"[init] book.json exists, keep ledger: {book_path}")
    else:
        book = state.default_book_state(slug, source, encoding, sha,
                                        len(entries), title, source.name)
        state.save_book(slug, book)
        state.save_hooks(slug, state.default_hooks_state())
        state.save_history(slug, state.default_history_state())

    _print(f"[init] slug={slug} encoding={encoding} chapters={len(entries)}")
    if warning:
        _print(f"[init] warning: {warning}")
    _print(f"[init] project ready: {project}")
    _print(f"[init] next: fill projects/{slug}/book.json, "
           f"then: python -m novelwriter analyze {slug}")
    return 0


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


def _fmt_score(value) -> str:
    return "待作者填写" if value is None else f"{value}"


def _fmt_missing(evidence: dict) -> str:
    missing = evidence.get("missing") if isinstance(evidence, dict) else None
    if not missing:
        return ""
    return "（缺失维度：" + ", ".join(missing) + "）"


def build_analyze_report(book: dict, hooks: list, history: dict,
                         chapter_no: int, results: dict) -> str:
    lines = []
    lines.append(f"# {book.get('title') or book.get('slug')} 六指标分析报告")
    lines.append("")
    lines.append(f"- 书号 slug：`{book.get('slug')}`")
    lines.append(f"- 原著章数：{book.get('total_chapters')}，当前续写至："
                 f"第 {book.get('current_chapter')} 章，下一章建议针对："
                 f"第 {chapter_no} 章")
    lines.append("- 公式与阈值依据 CONSTITUTION.md；分数只用于提醒、排序与评审，"
                 "不用于自动改写剧情（宪章 1.2、2 总述）。")
    lines.append("- 台账未填写的维度标注「待作者填写」，不按 0 计分。")
    lines.append("")

    # 1. Pressure
    p_total, p_ev = results["pressure_total"], results["pressure_evidence"]
    lines.append("## 1. Pressure 读者压力（宪章 2.1）")
    lines.append("")
    lines.append(f"**总分：{_fmt_score(p_total)}**{_fmt_missing(p_ev)}")
    lines.append("")
    pressure = book.get("pressure") or {}
    lines.append("| 分项 | 分数 |")
    lines.append("| --- | --- |")
    for key, label in M.PRESSURE_LABELS.items():
        value = pressure.get(key)
        lines.append(f"| {label}（{key}） | {_fmt_score(value)} |")
    lines.append("")
    lines.append("曲线纪律：连续 >80 不宜超 3–5 章；连续 <35 不宜超 5–8 章；"
                 "大爽点通常在压力 70–90 时兑现；兑现后保留 20–40 分残余。")
    lines.append("")

    # 2. 资源压力
    lines.append("## 2. 资源压力（宪章 3.3）")
    lines.append("")
    resources = book.get("resources") or []
    if not resources:
        lines.append("资源台账为空：待作者填写 `resources[]`"
                     "（name/stock/daily_income/daily_cost/blocked_count/"
                     "next_tier_goal/gap/next_tier_demand/perceptibility/"
                     "setup_chapters/causal_source/post_gameplay）。")
    else:
        lines.append("| 资源 | 压力 P | 备注 |")
        lines.append("| --- | --- | --- |")
        for res in resources:
            score = results["resource_pressures"].get(res.get("name", ""))
            note = "" if score is not None else "子项不全，待作者填写"
            lines.append(f"| {res.get('name', '')} | {_fmt_score(score)} | {note} |")
    lines.append("")

    # 3. Payoff
    score3, p_ev2 = results["payoff"]
    lines.append("## 3. Payoff 爽点净分（宪章 2.2）")
    lines.append("")
    lines.append("S = 0.25M + 0.25I + 0.15N + 0.15C + 0.20A − 0.10F − 0.10D")
    lines.append("")
    lines.append(f"- 自动计算：新奇度 N = {p_ev2.get('novelty_N')}，"
                 f"同类疲劳 F = {p_ev2.get('fatigue_F')}（基于爽点历史，宪章 2.5）")
    if score3 is None:
        lines.append("- 净分 S：待作者填写。请在 book.json 的 `payoff_draft` 中"
                     "填齐 M/I/C/A 全部子项与 D，analyze/plan 即自动汇总并分档"
                     "（metrics 不猜事实）。")
    else:
        lines.append(f"- **净分 S = {score3}**，分档：{M.classify_payoff(score3)}"
                     f"（M={p_ev2.get('M')} I={p_ev2.get('I')} C={p_ev2.get('C')} "
                     f"A={p_ev2.get('A')} D={p_ev2.get('D')}）")
    lines.append("- 五档阈值：<50 继续铺垫 / <65 小型奖励 / <80 中型爽点 / "
                 "<91 阶段性大爆发 / 其余篇章高潮。")
    lines.append("")

    # 4. Narrative Debt
    debts = results["narrative_debts"]
    balanced, b_ev = results["hook_balance"]
    lines.append("## 4. Narrative Debt 悬念债务（宪章 2.3）")
    lines.append("")
    if debts:
        lines.append("| 悬念 | 债务分 | 等待 | 推进度 | 状态 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for d in debts[:10]:
            lines.append(f"| {d['hook']} | {d['debt']} | {d['age']} 章 | "
                         f"{d['progress']} | {d['status']} |")
    else:
        lines.append("悬念清单为空：待作者填写 `hooks.json`。")
    lines.append("")
    lines.append(f"每 10 章平衡检查：{'通过' if balanced else '失衡'}"
                 f"（新增 {b_ev['new']} ≤ 兑现容量 {b_ev['capacity']}；"
                 f"完全兑现 {b_ev['resolved']} + 部分兑现 {b_ev['advanced']}×1.5）。")
    lines.append("")

    # 5. Progress
    prog, prog_ev = results["progress"], results["progress_evidence"]
    lines.append("## 5. Progress 进展与停滞（宪章 2.4）")
    lines.append("")
    lines.append(f"**进展值：{_fmt_score(prog)}**{_fmt_missing(prog_ev)}")
    lines.append("")
    comps = book.get("progress_components") or {}
    lines.append("| 维度 | 分数 |")
    lines.append("| --- | --- |")
    for key, label in M.PROGRESS_LABELS.items():
        lines.append(f"| {label}（{key}） | {_fmt_score(comps.get(key))} |")
    lines.append("")
    registered = history.get("effective_change_chapters") or []
    if registered:
        cur = int(book.get("current_chapter") or 0)
        window = 10
        effective = [c for c in registered if cur - window < int(c) <= cur]
        s_index, s_ev = M.stagnation_index(window, len(effective))
        lines.append(f"停滞指数（最近 {window} 章）：**{s_index}**"
                     f"（登记有效不可逆变化 {len(effective)} 章，"
                     f"停滞率 {s_ev['stagnation_rate']}；宪章 2.4，"
                     "由 record --effective-change / --no-effective-change 登记）")
    else:
        lines.append("停滞指数：待登记。请在 record 时用 --effective-change / "
                     "--no-effective-change 按章登记是否发生有效不可逆变化"
                     "（停滞指数 = 最近章节数 − 有效变化章节数，宪章 2.4）。")
    lines.append("")

    # 6. Repetition Fatigue
    fatigue, f_ev = results["repetition"]
    lines.append("## 6. Repetition Fatigue 重复疲劳（宪章 2.5）")
    lines.append("")
    lines.append(f"**疲劳度：{fatigue}**（新奇度 N = {f_ev.get('novelty')}；"
                 f"最近 20 章同类 {f_ev.get('same_type_20')} 次 × 15，"
                 f"最近 50 章相似结构 {f_ev.get('similar_50')} 次 × 8）")
    lines.append("")

    # 7. Risk Credibility
    risk, risk_ev = results["risk"], results["risk_evidence"]
    lines.append("## 7. Risk Credibility 风险可信度（宪章 2.6）")
    lines.append("")
    lines.append(f"**可信度：{_fmt_score(risk)}**{_fmt_missing(risk_ev)}")
    lines.append("")
    factors = book.get("risk_factors") or {}
    lines.append("| 因子 | 值（0-1） |")
    lines.append("| --- | --- |")
    for key in M.RISK_FACTOR_KEYS:
        lines.append(f"| {key} | {_fmt_score(factors.get(key))} |")
    lines.append("")
    lines.append("铁律：危险必须在故事中偶尔真实兑现，不能只存在于说明里。")
    lines.append("")
    return "\n".join(lines)


def cmd_analyze(args) -> int:
    book, hooks, history = _load_project(args.slug)
    chapter_no = args.chapter or book.get("next_write_chapter") or \
        int(book.get("current_chapter") or 0) + 1
    results = compute_metrics(book, hooks, history, chapter_no)
    report = build_analyze_report(book, hooks, history, chapter_no, results)

    report_path = state.project_path(args.slug, "reports", "analyze.md")
    if args.dry_run:
        _print(f"[dry-run] would write {report_path}")
    else:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        _print(f"[analyze] report written: {report_path}")

    p = results["pressure_total"]
    _print(f"[analyze] chapter={chapter_no} "
           f"pressure={'n/a' if p is None else p} "
           f"fatigue={results['repetition'][0]} "
           f"open_hooks={len(results['narrative_debts'])} "
           f"risk={'n/a' if results['risk'] is None else results['risk']}")
    return 0


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def _recent_chapter_summaries(slug: str, book: dict, chapter_no: int):
    """最近 1–2 章摘要：优先续写稿 chapters/，否则取原著最后章节。"""
    summaries = []
    project = state.project_dir(slug)
    for ch in (chapter_no - 2, chapter_no - 1):
        if ch < 1:
            continue
        candidate = project / "chapters" / f"chapter_{ch:03d}.md"
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            summaries.append((f"续写第 {ch} 章", text))
    if summaries:
        return summaries
    index = state.load_index(slug)
    if not index or not index.get("entries"):
        return []
    source = state.resolve_source(book.get("source_path"))
    if source is None:
        return []
    entries = index["entries"][-2:]
    try:
        text, _enc = loader.read_text(source)
    except (OSError, ValueError):
        return []
    for e in entries:
        summaries.append((f"原著第 {e['no']} 章 {e['title']}".strip(),
                          loader.read_chapter_text(source, e, text)))
    return summaries


def cmd_plan(args) -> int:
    book, hooks, history = _load_project(args.slug)
    chapter_no = args.chapter or book.get("next_write_chapter") or \
        int(book.get("current_chapter") or 0) + 1
    results = compute_metrics(book, hooks, history, chapter_no)
    suggestion = scheduler.build_suggestion(chapter_no, book, hooks, history,
                                            results)
    c = contract_mod.build_contract(suggestion, book)

    contract_path = state.project_path(args.slug, "contracts",
                                       f"chapter_{chapter_no:03d}.json")
    if args.dry_run:
        _print(f"[dry-run] would write {contract_path} and "
               f"prompts/chapter_{chapter_no:03d}.md")
        _print(f"[dry-run] payoff_tier={suggestion['payoff']['tier']}")
        return 0

    contract_path.parent.mkdir(parents=True, exist_ok=True)
    state.atomic_write_json(contract_path, c)
    _print(f"[plan] contract written: {contract_path}")

    summaries = _recent_chapter_summaries(args.slug, book, chapter_no)
    prompt = contract_mod.render_prompt(c, summaries,
                                        hooks_queue=results["narrative_debts"])
    adapter = llm.create_adapter(book)
    prompt_path = state.project_path(args.slug, "prompts",
                                     f"chapter_{chapter_no:03d}.md")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    _print(f"[plan] prompt written: {prompt_path} (adapter={adapter.name})")

    # ApiAdapter：提示词已先行落盘（保证可回退），再尝试调 API 生成正文；
    # 任何异常（含 json.JSONDecodeError，已在 llm 层并入 RuntimeError）
    # 均降级为 ManualAdapter 行为。api_key 不落入日志。
    if isinstance(adapter, llm.ApiAdapter):
        try:
            draft = adapter.complete(prompt)
            chapter_path = state.project_path(
                args.slug, "chapters", f"chapter_{chapter_no:03d}.md")
            chapter_path.parent.mkdir(parents=True, exist_ok=True)
            chapter_path.write_text(draft, encoding="utf-8")
            _print(f"[plan] api draft written: {chapter_path} "
                   "(review before record)")
        except Exception as exc:
            _print(f"[plan] api call failed, fallback to manual paste: {exc}")

    _print(f"[plan] payoff_tier={suggestion['payoff']['tier']} "
           f"budget_left={suggestion['budget']['remaining']}")
    _print(f"[plan] next: paste prompt to LLM, then run: "
           f"python -m novelwriter record {args.slug} "
           f"--chapter {chapter_no} --file <chapter-file>")
    return 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


def cmd_record(args) -> int:
    book, hooks, history = _load_project(args.slug)
    chapter_no = args.chapter
    src = Path(args.file)
    if not src.exists():
        _fail(f"chapter file not found: {src}")
    # 范围校验（先于任何台账改动，越界直接报错退出）
    if args.payoff_intensity is not None and \
            not (0 <= args.payoff_intensity <= 100):
        _fail(f"--payoff-intensity out of range 0-100: {args.payoff_intensity}")
    if args.pressure:
        for raw in args.pressure.split(","):
            try:
                v = float(raw.strip())
            except ValueError:
                _fail(f"--pressure value not a number: {raw}")
            if not (0 <= v <= 100):
                _fail(f"--pressure value out of range 0-100: {raw}")
    text, encoding = loader.read_text(src)

    target = state.project_path(args.slug, "chapters",
                                f"chapter_{chapter_no:03d}.md")
    actions = [f"copy {src} -> {target}"]

    history.setdefault("payoff_events", [])
    history.setdefault("pressure_history", [])
    history.setdefault("recent_structures", [])
    history.setdefault("hook_events", [])

    # 爽点事件（幂等：同一章重复 record 时先移除旧记录再追加）
    if args.payoff_group or args.payoff_intensity is not None:
        history["payoff_events"] = [
            e for e in history["payoff_events"]
            if e.get("chapter") != chapter_no]
        book["budget_10ch"] = [
            b for b in book.get("budget_10ch", [])
            if b.get("chapter") != chapter_no]
        intensity = args.payoff_intensity or 0
        event = {"chapter": chapter_no, "group": args.payoff_group or "",
                 "subtype": args.payoff_subtype or "",
                 "intensity": intensity, "score": intensity}
        history["payoff_events"].append(event)
        label = args.payoff_subtype or args.payoff_group or ""
        if label:
            # 结构化 {chapter,label}：先清除本章旧标签再重建，
            # 防交错重录产生重复（旧版纯字符串遗留条目保留）
            history["recent_structures"] = [
                s for s in history["recent_structures"]
                if not (isinstance(s, dict)
                        and s.get("chapter") == chapter_no)]
            history["recent_structures"].append(
                {"chapter": chapter_no, "label": label})
        book.setdefault("budget_10ch", []).append(
            {"chapter": chapter_no, "score": intensity,
             "group": args.payoff_group or ""})
        # 冷却组 last_major_chapter 由数据推导回写（重录低强度爽点后
        # 自动回滚到该组最后一次 intensity>=30 事件的章号）
        if args.payoff_group:
            major = [int(e.get("chapter") or 0)
                     for e in history["payoff_events"]
                     if e.get("group") == args.payoff_group
                     and int(e.get("intensity") or 0) >= 30]
            for g in book.get("payoff_cooldowns") or []:
                if g.get("group") == args.payoff_group:
                    g["last_major_chapter"] = max(major, default=0)
        actions.append(f"payoff_event group={args.payoff_group} "
                       f"intensity={intensity}")

    # 压力读数
    if args.pressure:
        values = [v.strip() for v in args.pressure.split(",")]
        if len(values) != len(PRESSURE_ORDER):
            _fail("--pressure needs 6 comma-separated values in order: "
                  + ",".join(PRESSURE_ORDER))
        components = {}
        for key, raw in zip(PRESSURE_ORDER, values):
            try:
                components[key] = float(raw)
            except ValueError:
                _fail(f"--pressure value not a number: {raw}")
        total, _ev = M.pressure_score(components)
        history["pressure_history"] = [
            p for p in history["pressure_history"]
            if p.get("chapter") != chapter_no]
        history["pressure_history"].append(
            {"chapter": chapter_no, "total": total, "components": components})
        actions.append(f"pressure_total={total}")

    # 悬念：新增 / 推进 / 解决（幂等：本章事件先清除再按当前参数重建）
    real_hooks = [h for h in hooks if isinstance(h, dict) and not h.get("_comment")]
    if args.new_hook or args.advance_hook or args.resolved_hook:
        history["hook_events"] = [
            e for e in history["hook_events"]
            if e.get("chapter") != chapter_no]
    if args.new_hook:
        existing = next((h for h in real_hooks
                         if h.get("hook") == args.new_hook), None)
        if existing is not None:
            # 幂等对称：该悬念就是本章首次记录的（born_chapter == 本章），
            # 重建时应恢复 new 事件；否则仅跳过，不重复计数
            if int(existing.get("born_chapter") or 0) == chapter_no:
                history["hook_events"].append(
                    {"chapter": chapter_no, "action": "new"})
                actions.append(f"new_hook event restored "
                               f"id={existing.get('id')}")
            else:
                actions.append("new_hook skipped (same text already exists)")
        else:
            new_id = f"h{len(real_hooks) + 1:03d}"
            hooks.append({"id": new_id, "hook": args.new_hook,
                          "importance": 0.5, "born_chapter": chapter_no,
                          "reminder_count": 1, "visibility": 1.0,
                          "progress": 0.0, "status": "open"})
            history["hook_events"].append(
                {"chapter": chapter_no, "action": "new"})
            actions.append(f"new_hook id={new_id}")
    if args.advance_hook:
        for h in real_hooks:
            if (h.get("id") == args.advance_hook
                    and h.get("status") != "resolved"):
                if int(h.get("last_advanced_chapter") or 0) == chapter_no:
                    # 幂等对称：本章已推进过（守卫命中），事件记录与
                    # 状态防重放分离——恢复 advance 事件，状态不二次推进
                    history["hook_events"].append(
                        {"chapter": chapter_no, "action": "advance"})
                    actions.append(f"advance_hook event restored "
                                   f"id={args.advance_hook}")
                else:
                    h["status"] = "advanced"
                    h["progress"] = min(1.0, float(h.get("progress") or 0) + 0.2)
                    h["reminder_count"] = int(h.get("reminder_count") or 0) + 1
                    h["last_advanced_chapter"] = chapter_no
                    history["hook_events"].append(
                        {"chapter": chapter_no, "action": "advance"})
                    actions.append(f"advance_hook id={args.advance_hook}")
                break
    if args.resolved_hook:
        for h in real_hooks:
            if h.get("id") == args.resolved_hook:
                h["status"] = "resolved"
                h["progress"] = 1.0
                history["hook_events"].append(
                    {"chapter": chapter_no, "action": "resolve"})
                actions.append(f"resolved_hook id={args.resolved_hook}")
                break

    # 停滞登记（宪章 2.4）：本章是否发生有效不可逆变化，按章累计
    history.setdefault("effective_change_chapters", [])
    if args.effective_change or args.no_effective_change:
        registered = [int(c) for c in history["effective_change_chapters"]
                      if int(c) != chapter_no]
        if args.effective_change:
            registered.append(chapter_no)
        history["effective_change_chapters"] = sorted(registered)
        actions.append(
            "effective_change=" + ("yes" if args.effective_change else "no"))

    book["current_chapter"] = max(int(book.get("current_chapter") or 0),
                                  chapter_no)
    book["next_write_chapter"] = book["current_chapter"] + 1
    actions.append(f"current_chapter -> {book['current_chapter']}")

    if args.dry_run:
        for a in actions:
            _print(f"[dry-run] would: {a}")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    state.save_book(args.slug, book)
    state.save_hooks(args.slug, hooks)
    state.save_history(args.slug, history)
    for a in actions:
        _print(f"[record] {a}")
    _print(f"[record] chapter {chapter_no} recorded ({encoding}); "
           f"next_write_chapter={book['next_write_chapter']}")
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="novelwriter",
        description="novel continuation assistant "
                    "(constitution-driven, author decides)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize a project from a source file")
    p_init.add_argument("source", help="path to inspiration file (.md/.txt)")
    p_init.add_argument("--slug", help="override auto slug")
    p_init.add_argument("--dry-run", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_analyze = sub.add_parser("analyze", help="compute six metrics, write report")
    p_analyze.add_argument("slug")
    p_analyze.add_argument("--chapter", type=int,
                           help="chapter the analysis targets")
    p_analyze.add_argument("--dry-run", action="store_true")
    p_analyze.set_defaults(func=cmd_analyze)

    p_plan = sub.add_parser("plan", help="scheduler + chapter contract + prompt")
    p_plan.add_argument("slug")
    p_plan.add_argument("--chapter", type=int,
                        help="target chapter (default: next write chapter)")
    p_plan.add_argument("--dry-run", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_record = sub.add_parser("record", help="record a finished chapter")
    p_record.add_argument("slug")
    p_record.add_argument("--chapter", type=int, required=True)
    p_record.add_argument("--file", required=True, help="chapter text file")
    p_record.add_argument("--payoff-group",
                          help="resource/combat/cognition/social/world/emotion")
    p_record.add_argument("--payoff-subtype", default="")
    p_record.add_argument("--payoff-intensity", type=int, default=None,
                          help="0-100")
    p_record.add_argument("--pressure",
                          help="6 comma-separated 0-100 values: "
                               + ",".join(PRESSURE_ORDER))
    p_record.add_argument("--new-hook", help="new suspense hook text")
    p_record.add_argument("--advance-hook", help="hook id to advance")
    p_record.add_argument("--resolved-hook", help="hook id to resolve")
    change_group = p_record.add_mutually_exclusive_group()
    change_group.add_argument(
        "--effective-change", action="store_true",
        help="register: this chapter produced an effective irreversible change")
    change_group.add_argument(
        "--no-effective-change", action="store_true",
        help="register: this chapter produced no effective irreversible change")
    p_record.add_argument("--dry-run", action="store_true")
    p_record.set_defaults(func=cmd_record)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
