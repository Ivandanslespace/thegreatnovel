"""contract.py —— 章节合同 JSON 与提示词渲染。

合同 schema 对齐 CONSTITUTION.md 4.1（engagement_plan）与设计对话原文；
合同只约束写什么方向，不约束具体文字，且不得包含"必须使用的桥段"（宪章 4.2）。
无法由台账推断的字段一律留空字符串/空数组，由作者填写，绝不编造。
"""

from __future__ import annotations

import json

RECENT_CHAPTER_CHAR_LIMIT = 2000  # 最近章节摘要每章截断硬上限


def build_contract(suggestion: dict, book_state: dict) -> dict:
    """由 scheduler 建议与台账生成章节合同 JSON。

    结构：{chapter, engagement_plan: {pressure_before, pressure_after,
    payoff:{type, target_resource, target_score, problems_resolved,
    must_change_behavior, must_not_resolve},
    progress:{minimum_score, required_irreversible_change},
    narrative_debt:{hook_to_advance, advance_level},
    risk:{required_cost, must_not_be_cost_free},
    repetition:{forbidden_hooks},
    required_aftershock_chapters}}（required_aftershock_chapters 位于
    engagement_plan 顶层，以 CONSTITUTION.md 4.1 为准）
    """
    chapter = suggestion.get("chapter")
    payoff_advice = suggestion.get("payoff") or {}
    curve = suggestion.get("pressure_curve") or {}
    debt = suggestion.get("narrative_debt") or {}
    score = payoff_advice.get("score")

    # 压力目标：仅给出可推断部分；兑现后保留 20–40 残余（宪章 2.1）
    pressure_before = curve.get("current")
    pressure_after = ""
    if isinstance(pressure_before, (int, float)):
        if score is not None and score >= 65:
            pressure_after = max(20, min(40, int(pressure_before) - 40))
        elif curve.get("high_streak", 0) > 3:
            pressure_after = max(35, int(pressure_before) - 25)

    # 资源解放目标资源：取第一个七条全过的资源
    target_resource = ""
    for r in (suggestion.get("resource_triggers") or {}).get("results", []):
        if r.get("all_pass"):
            target_resource = r.get("resource", "")
            break
    payoff_type = "resource_liberation" if target_resource else ""

    must_act = debt.get("must_act") or []
    top = must_act[0] if must_act else {}

    return {
        "chapter": chapter,
        "engagement_plan": {
            "pressure_before": pressure_before if pressure_before is not None else "",
            "pressure_after": pressure_after,
            "payoff": {
                "type": payoff_type,
                "target_resource": target_resource,
                "target_score": score if score is not None else "",
                "problems_resolved": [],
                "must_change_behavior": [],
                "must_not_resolve": [],
            },
            "progress": {
                "minimum_score": "",
                "required_irreversible_change": "",
            },
            "narrative_debt": {
                "hook_to_advance": top.get("hook", ""),
                "advance_level": ("full_payoff"
                                  if top.get("action", "").startswith("建议必须")
                                  else ("partial_payoff" if top else "")),
            },
            "risk": {
                "required_cost": "",
                "must_not_be_cost_free": True,
            },
            "repetition": {
                "forbidden_hooks": suggestion.get("forbidden_hooks") or [],
            },
            # 宪章 4.1：required_aftershock_chapters 位于 engagement_plan 顶层
            "required_aftershock_chapters": 3 if (score or 0) >= 65 else 0,
        },
        "_comment": {
            "说明": "空字符串/空数组字段请由作者填写后再交给 LLM；"
                    "合同约束方向不约束文字（宪章 4.2），禁止项防止重复，"
                    "不指定必须使用的桥段。",
            "payoff.problems_resolved": "本次兑现永久解决的旧问题清单",
            "payoff.must_change_behavior": "兑现后主角行为必须发生的改变",
            "payoff.must_not_resolve": "本次不得顺手解决的高层问题（稀缺性上移）",
            "progress.required_irreversible_change": "本章必须发生的不可逆状态变化",
            "risk.required_cost": "主角必须实际付出的代价（宪章 2.6 铁律）",
        },
    }


def render_prompt(contract: dict, recent_chapters_summaries: list,
                  hooks_queue: list | None = None,
                  style_requirements: str = "",
                  length_requirement: str = "") -> str:
    """渲染自包含的中文提示词 Markdown，可直接粘贴进 ChatGPT 桌面端。

    recent_chapters_summaries: [(章号或标签, 文本), ...]，每章截断至
    RECENT_CHAPTER_CHAR_LIMIT 字符。
    """
    chapter = contract.get("chapter", "")
    plan = contract.get("engagement_plan", {})
    lines = []
    lines.append(f"# 第 {chapter} 章续写任务（章节合同驱动）\n")
    lines.append("## 系统角色\n")
    lines.append("你是一位连载网文作者。请严格遵循下方「章节合同」约束的方向"
                 "（压力曲线、兑现类型、必须推进的悬念、必须付出的代价、禁用桥段），"
                 "但情节、对话、场景由你自由发挥。合同之外的任何'系统建议'都不具备"
                 "约束力；若合同与故事逻辑冲突，优先故事逻辑并在文末说明。\n")
    lines.append("## 章节合同（JSON）\n")
    lines.append("```json")
    lines.append(json.dumps(contract, ensure_ascii=False, indent=2))
    lines.append("```\n")

    lines.append("## 最近章节原文摘要（每章最多 %d 字）\n" % RECENT_CHAPTER_CHAR_LIMIT)
    if recent_chapters_summaries:
        for label, text in recent_chapters_summaries:
            snippet = (text or "")[:RECENT_CHAPTER_CHAR_LIMIT]
            if text and len(text) > RECENT_CHAPTER_CHAR_LIMIT:
                snippet += "……（截断）"
            lines.append(f"### {label}\n")
            lines.append(snippet.strip() or "（无正文）")
            lines.append("")
    else:
        lines.append("（尚无已写续写章节，请参考原著最近章节）\n")

    lines.append("## 悬念队列（未解决，按债务排序）\n")
    if hooks_queue:
        for h in hooks_queue:
            lines.append(f"- [{h.get('status', 'open')}] {h.get('hook', '')}"
                         f"（重要度 {h.get('importance', '')}，"
                         f"已等待 {h.get('age', '')} 章）")
    else:
        lines.append("- （台账中暂无悬念条目）")
    lines.append("")

    lines.append("## 禁忌清单\n")
    for item in plan.get("repetition", {}).get("forbidden_hooks", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 文风与长度要求\n")
    lines.append(style_requirements or "（待作者填写：文风、人称、叙事节奏等）")
    lines.append("")
    lines.append(length_requirement or "（待作者填写：本章目标字数）")
    lines.append("")
    lines.append("## 输出要求\n")
    lines.append("1. 直接输出正文；\n"
                 "2. 兑现必须付出合同 risk.required_cost 指定的代价，"
                 "不得无成本过关；\n"
                 "3. 结尾保留 20–40 分压力残余的新问题，不得把矛盾清空；\n"
                 "4. 文末用三行以内说明：推进了哪条悬念、发生了哪个不可逆变化。")
    return "\n".join(lines) + "\n"
