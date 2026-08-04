"""state.py —— 唯一碰磁盘的状态读写模块。

所有 JSON 状态原子写入：先写 temps/ 下临时文件再 ``os.replace`` 落盘；
UTF-8、ensure_ascii=False、indent=2。其余模块不得直接写状态文件。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPS_DIR = ROOT / "temps"
PROJECTS_DIR = ROOT / "projects"

BOOK_FILE = "book.json"
HOOKS_FILE = "hooks.json"
HISTORY_FILE = "history.json"
INDEX_FILE = "chapters_index.json"


# ---------------------------------------------------------------------------
# 原子读写
# ---------------------------------------------------------------------------


def atomic_write_json(path, data) -> None:
    """原子写 JSON：temps/ 临时文件 + os.replace。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    TEMPS_DIR.mkdir(exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(TEMPS_DIR), suffix=".tmp.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_json(path, default=None):
    """读 JSON；文件不存在返回 default。"""
    p = Path(path)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 路径辅助
# ---------------------------------------------------------------------------


def project_dir(slug: str) -> Path:
    return PROJECTS_DIR / slug


def project_path(slug: str, *parts) -> Path:
    return PROJECTS_DIR.joinpath(slug, *parts)


def normalize_source_path(source) -> str:
    """落盘用源路径归一化（跨平台、跨 CWD）。

    resolve 后尽量存为相对工作区根（ROOT）的 POSIX 相对路径；
    源在 ROOT 之外（或 Windows 不同盘符无法相对化）时存绝对 POSIX 路径。
    """
    p = Path(source).resolve()
    try:
        rel = p.relative_to(ROOT)
    except ValueError:
        return p.as_posix()
    return rel.as_posix()


def resolve_source(stored) -> Path | None:
    """读取端：以 ROOT 为基准拼接落盘的源路径；ROOT 下不存在时
    回退按 CWD 相对解析。文件不存在返回 None。"""
    if not stored:
        return None
    p = Path(str(stored).replace("\\", "/"))
    for cand in ((ROOT / p), Path(p), Path.cwd() / p):
        if cand.is_file():
            return cand
    return None


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 四件套模板
# ---------------------------------------------------------------------------

# 六类冷却组（CONSTITUTION.md 3.1），recommended_cooldown 为建议间隔章数
DEFAULT_COOLDOWN_GROUPS = [
    {"group": "resource", "last_major_chapter": 0, "recommended_cooldown": 40},
    {"group": "combat", "last_major_chapter": 0, "recommended_cooldown": 12},
    {"group": "cognition", "last_major_chapter": 0, "recommended_cooldown": 10},
    {"group": "social", "last_major_chapter": 0, "recommended_cooldown": 15},
    {"group": "world", "last_major_chapter": 0, "recommended_cooldown": 45},
    {"group": "emotion", "last_major_chapter": 0, "recommended_cooldown": 15},
]


def default_book_state(slug: str, source_path, encoding: str, sha256: str,
                       total_chapters: int, title: str = "",
                       source_name: str = "") -> dict:
    """book.json 初始模板（含 _comment 填写指引）。"""
    return {
        "_comment": {
            "说明": "作者台账。analyze/plan 只依据这里填写的事实计算，不会猜测。",
            "pressure": "读者压力六分项，各 0-100（CONSTITUTION.md 2.1）："
                        "survival_threat 生存威胁 / resource_scarcity 资源匮乏 / "
                        "time_pressure 时间压力 / uncertainty 信息不确定性 / "
                        "social_conflict 人际冲突 / recent_failure 失败累积。",
            "resources": "核心资源台账。gap=当前缺口 0-100；blocked_count=因缺它"
                         "而被阻塞的决策次数；next_tier_goal=下一阶段资源目标；"
                         "perceptibility=读者可感知程度 0-100；setup_chapters=已铺垫章数。",
            "progress_components": "最近一章的进展六维 0-100（2.4）：permanent_growth /"
                                   " world_change / relationship_change / intel_change /"
                                   " goal_advance / new_gameplay。",
            "risk_factors": "风险可信度五维 0-1（2.6）：cost_realized_rate 实际代价兑现率 /"
                            " failure_clarity 失败后果清晰度 / enemy_effectiveness 敌人有效性 /"
                            " info_incompleteness 主角信息不完整度 / protection_limitedness 保护机制有限度。",
            "payoff_draft": "对下一章计划爽点的作者评分（2.2）。把 M/I/C/A 的全部子项"
                            "（各 0-100）与 D（剧情破坏扣分项，0-100）填齐后，"
                            "analyze/plan 自动汇总 S = 0.25M+0.25I+0.15N+0.15C+0.20A"
                            "−0.10F−0.10D（N/F 由爽点历史自动计算）并据此分档、"
                            "生成合同 target_score 与 required_aftershock_chapters；"
                            "任一子项缺失即视为未填，保持「待作者填写」。",
            "payoff_cooldowns": "六冷却组（3.1）：last_major_chapter 为该组最近一次大爽点章号。",
            "budget_10ch": "最近 10 章爽点消费记录（3.2），由 record 命令自动追加。",
            "llm_api": "可选。填写 {base_url, api_key, model} 启用 API 适配层，否则手动粘贴提示词。",
        },
        "title": title,
        "slug": slug,
        "source_path": normalize_source_path(source_path),
        "source_name": source_name,
        "encoding": encoding,
        "sha256": sha256,
        "total_chapters": total_chapters,
        "current_chapter": total_chapters,
        "next_write_chapter": total_chapters + 1,
        "pressure": {},
        "resources": [],
        "progress_components": {},
        "risk_factors": {},
        "payoff_draft": {"M": {}, "I": {}, "C": {}, "A": {}, "D": None},
        "payoff_cooldowns": [dict(g) for g in DEFAULT_COOLDOWN_GROUPS],
        "budget_10ch": [],
        "llm_api": None,
    }


def default_hooks_state() -> list:
    """hooks.json 初始模板：空悬念清单。"""
    return [
        {
            "_comment": "悬念清单。每条：{id, hook 问题描述, importance 重要度 0-1, "
                        "born_chapter 埋设章, reminder_count 被提醒次数, "
                        "visibility 读者可见度 0-1, progress 推进度 0-1, "
                        "status open/advanced/resolved}。公式见 CONSTITUTION.md 2.3。",
        }
    ]


def default_history_state() -> dict:
    """history.json 初始模板。"""
    return {
        "_comment": "由 record 命令自动维护：payoff_events 爽点事件"
                    "（chapter/group/subtype/intensity/score）；"
                    "pressure_history 每章压力总分；"
                    "recent_structures 结构标签 {chapter,label}"
                    "（用于重复疲劳 2.5）；"
                    "hook_events 悬念新增/推进/兑现事件（用于 2.3 平衡检查）；"
                    "effective_change_chapters 登记了有效不可逆变化的章号清单"
                    "（record --effective-change / --no-effective-change，"
                    "用于 2.4 停滞指数）。",
        "payoff_events": [],
        "pressure_history": [],
        "recent_structures": [],
        "hook_events": [],
        "effective_change_chapters": [],
    }


# ---------------------------------------------------------------------------
# 四件套读写
# ---------------------------------------------------------------------------


def load_book(slug: str) -> dict:
    return load_json(project_path(slug, BOOK_FILE), default=None)


def save_book(slug: str, book: dict) -> None:
    atomic_write_json(project_path(slug, BOOK_FILE), book)


def load_hooks(slug: str) -> list:
    return load_json(project_path(slug, HOOKS_FILE), default=[])


def save_hooks(slug: str, hooks: list) -> None:
    atomic_write_json(project_path(slug, HOOKS_FILE), hooks)


def load_history(slug: str) -> dict:
    return load_json(project_path(slug, HISTORY_FILE),
                     default={"payoff_events": [], "pressure_history": [],
                              "recent_structures": [], "hook_events": [],
                              "effective_change_chapters": []})


def save_history(slug: str, history: dict) -> None:
    atomic_write_json(project_path(slug, HISTORY_FILE), history)


def load_index(slug: str) -> dict:
    return load_json(project_path(slug, INDEX_FILE), default=None)


def save_index(slug: str, index: dict) -> None:
    atomic_write_json(project_path(slug, INDEX_FILE), index)


# ---------------------------------------------------------------------------
# 切章索引缓存（sha256 未变则复用）
# ---------------------------------------------------------------------------


def get_or_build_index(slug: str, source_path, dry_run: bool = False) -> dict:
    """读取 chapters_index.json；源文件 sha256 未变则复用，否则重切并保存。

    返回 ``{source_sha256, encoding, entries, warning, frontmatter}``。
    dry_run 时不落盘。
    """
    from . import loader  # 延迟导入，避免循环

    source_path = Path(source_path)
    sha = file_sha256(source_path)
    cached = load_index(slug)
    if cached and cached.get("source_sha256") == sha and cached.get("entries"):
        return cached
    text, encoding = loader.read_text(source_path)
    result = loader.build_chapter_index(source_path, text)
    index = {
        "source_path": normalize_source_path(source_path),
        "source_sha256": sha,
        "mtime": source_path.stat().st_mtime,
        "encoding": encoding,
        "warning": result["warning"],
        "frontmatter": result["frontmatter"],
        "entries": result["entries"],
    }
    if not dry_run:
        save_index(slug, index)
    return index


# ---------------------------------------------------------------------------
# slug 映射
# ---------------------------------------------------------------------------

# 常见书名 → ASCII 短横线 slug（含繁简两种写法）。
# 键统一 NFKC 归一：与 resolve_slug 的输入归一保持一致
# （NFKC 会把全角冒号「：」变为半角 ":"，表键不归一会永远查不中）。
SLUG_MAP = {
    unicodedata.normalize("NFKC", k): v for k, v in {
        "死亡列車": "death-train",
        "死亡列车": "death-train",
        "全民纜車求生，我一級一個三選一": "cablecar-three-choice",
        "全民缆车求生，我一级一个三选一": "cablecar-three-choice",
        "全民求生，我能夠自選寶箱獎勵": "box-reward-choice",
        "全民求生，我能够自选宝箱奖励": "box-reward-choice",
        "全民海上求生：我的載具是玄武": "sea-survival-xuanwu",
        "全民海上求生：我的载具是玄武": "sea-survival-xuanwu",
        "我合成了全世界": "synthesized-world",
        "斗罗大陆": "douluo-dalu",
        "鬥羅大陸": "douluo-dalu",
    }.items()
}


def resolve_slug(name: str, sha256: str = "") -> str:
    """书名 → slug：查映射表（NFKC 归一，支持前缀匹配副标题），
    未知书名用 sha256 前 8 位兜底。"""
    normalized = unicodedata.normalize("NFKC", name).strip()
    candidates = [normalized]
    # 去掉常见后缀再试
    for suffix in ("_正文全集", "正文全集"):
        if normalized.endswith(suffix):
            candidates.append(normalized[: -len(suffix)].strip())
    for candidate in candidates:
        if candidate in SLUG_MAP:
            return SLUG_MAP[candidate]
    # 前缀匹配（文件名常带冒号副标题，如「死亡列車：開局SSS級天賦！」）
    for candidate in candidates:
        for key in sorted(SLUG_MAP, key=len, reverse=True):
            if candidate.startswith(key):
                return SLUG_MAP[key]
    digest = sha256 or hashlib.sha256(name.encode("utf-8")).hexdigest()
    return f"book-{digest[:8]}"
