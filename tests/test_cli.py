"""test_cli.py —— CLI 端到端测试（death-train 素材，标准库 unittest）。

验证项：
1. 四个子命令 --dry-run 均无异常且不落盘（对比 projects/ 全量文件哈希）；
2. init 幂等：重复 init 不破坏已有台账（book/hooks/history 字节级不变）；
3. plan 产出 contracts/chapter_NNN.json + prompts/chapter_NNN.md，
   合同 JSON engagement_plan 字段齐全（对照 CONSTITUTION.md 4.1 schema），
   提示词为可直接粘贴的自包含中文文档；
4. record 幂等：同一章重复 record 不重复计数；
5. 缓存失效：chapters_index.json 含 sha256，源文件篡改触发重切。

可写测试产物只使用一次性 slug（e2e-*），收尾整体删除；
对 projects/death-train 仅做幂等/只读性质的操作。
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
TEMPS = ROOT / "temps"
INSPIRATIONS = ROOT / "inspirations"
DEATH_TRAIN_SRC = INSPIRATIONS / "死亡列車：開局SSS級天賦！_正文全集.md"

E2E_SLUG = "e2e-death-train-test"
CACHE_SLUG = "e2e-cache-test"


def run_cli(*args):
    """以子进程方式运行 CLI，返回 CompletedProcess（utf-8 捕获输出）。"""
    return subprocess.run([sys.executable, "-m", "novelwriter", *args],
                          cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=300)


def run_cli_cwd(cwd, *args):
    """同 run_cli，但指定工作目录（跨 CWD 回归用，PYTHONPATH 指向根）。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, "-m", "novelwriter", *args],
                          cwd=str(cwd), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          timeout=300)


def hash_projects_tree():
    """projects/ 全量文件哈希快照 {相对路径: sha256}。"""
    snapshot = {}
    for p in sorted(PROJECTS.rglob("*")):
        if p.is_file():
            snapshot[str(p.relative_to(PROJECTS))] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return snapshot


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TestDryRunNoSideEffects(unittest.TestCase):
    """四个子命令 --dry-run：无异常且不落盘。"""

    @classmethod
    def setUpClass(cls):
        TEMPS.mkdir(exist_ok=True)
        cls.chapter_file = TEMPS / "e2e_dryrun_chapter.md"
        cls.chapter_file.write_text(
            "## 第999章 测试章\n\n主角深吸一口气。\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.chapter_file.unlink(missing_ok=True)

    def test_all_four_subcommands_dry_run_write_nothing(self):
        before = hash_projects_tree()

        r1 = run_cli("init", str(DEATH_TRAIN_SRC), "--dry-run")
        self.assertEqual(r1.returncode, 0,
                         f"init --dry-run 失败:\n{r1.stdout}\n{r1.stderr}")
        self.assertIn("[dry-run]", r1.stdout)

        r2 = run_cli("analyze", "death-train", "--dry-run")
        self.assertEqual(r2.returncode, 0,
                         f"analyze --dry-run 失败:\n{r2.stdout}\n{r2.stderr}")

        r3 = run_cli("plan", "death-train", "--dry-run")
        self.assertEqual(r3.returncode, 0,
                         f"plan --dry-run 失败:\n{r3.stdout}\n{r3.stderr}")

        r4 = run_cli("record", "death-train", "--chapter", "999",
                     "--file", str(self.chapter_file),
                     "--payoff-group", "resource",
                     "--payoff-intensity", "20",
                     "--pressure", "80,70,60,50,40,30", "--dry-run")
        self.assertEqual(r4.returncode, 0,
                         f"record --dry-run 失败:\n{r4.stdout}\n{r4.stderr}")

        after = hash_projects_tree()
        self.assertEqual(before, after,
                         "dry-run 改变了 projects/ 下的文件（哈希不一致）")


class TestInitIdempotent(unittest.TestCase):
    """init 幂等：重复 init 不破坏已有台账。"""

    def test_reinit_keeps_ledger(self):
        book = PROJECTS / "death-train" / "book.json"
        hooks = PROJECTS / "death-train" / "hooks.json"
        history = PROJECTS / "death-train" / "history.json"
        index_p = PROJECTS / "death-train" / "chapters_index.json"
        before = {p.name: sha256_file(p)
                  for p in (book, hooks, history, index_p)}
        index_content_before = json.loads(
            index_p.read_text(encoding="utf-8"))

        # 与首次 init 相同的路径形态（相对工作区根），保证
        # chapters_index.json 中 source_path 字段可比
        rel_src = str(DEATH_TRAIN_SRC.relative_to(ROOT))
        for i in (1, 2):
            r = run_cli("init", rel_src)
            self.assertEqual(r.returncode, 0,
                             f"第 {i} 次 init 失败:\n{r.stdout}\n{r.stderr}")
            self.assertIn("keep ledger", r.stdout,
                          "重复 init 应输出 keep ledger（保留台账）")

        after = {p.name: sha256_file(p)
                 for p in (book, hooks, history, index_p)}
        self.assertEqual(before["book.json"], after["book.json"],
                         "重复 init 破坏了 book.json")
        self.assertEqual(before["hooks.json"], after["hooks.json"],
                         "重复 init 破坏了 hooks.json")
        self.assertEqual(before["history.json"], after["history.json"],
                         "重复 init 破坏了 history.json")
        index_content_after = json.loads(
            index_p.read_text(encoding="utf-8"))
        self.assertEqual(index_content_before, index_content_after,
                         "重复 init 导致 chapters_index.json 内容漂移")


class TestPlanContractAndPrompt(unittest.TestCase):
    """plan 产出合同与提示词（一次性 slug，收尾删除）。"""

    @classmethod
    def setUpClass(cls):
        r = run_cli("init", str(DEATH_TRAIN_SRC), "--slug", E2E_SLUG)
        if r.returncode != 0:
            raise RuntimeError(f"init {E2E_SLUG} 失败:\n{r.stdout}\n{r.stderr}")
        r = run_cli("plan", E2E_SLUG)
        cls.plan_result = r

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / E2E_SLUG, ignore_errors=True)

    def test_plan_exit_ok(self):
        self.assertEqual(self.plan_result.returncode, 0,
                         f"plan 失败:\n{self.plan_result.stdout}\n"
                         f"{self.plan_result.stderr}")

    def test_contract_file_and_fields(self):
        # death-train 原著 230 章 → 续写第 231 章
        cpath = PROJECTS / E2E_SLUG / "contracts" / "chapter_231.json"
        self.assertTrue(cpath.exists(), f"缺少合同文件 {cpath}")
        c = json.loads(cpath.read_text(encoding="utf-8"))
        self.assertEqual(c.get("chapter"), 231)
        plan = c.get("engagement_plan")
        self.assertIsInstance(plan, dict)
        for key in ("pressure_before", "pressure_after", "payoff",
                    "progress", "narrative_debt", "risk", "repetition"):
            self.assertIn(key, plan, f"engagement_plan 缺少字段 {key}")
        for key in ("type", "target_score"):
            self.assertIn(key, plan["payoff"], f"payoff 缺少字段 {key}")
        for key in ("minimum_score", "required_irreversible_change"):
            self.assertIn(key, plan["progress"], f"progress 缺少字段 {key}")
        for key in ("hook_to_advance", "advance_level"):
            self.assertIn(key, plan["narrative_debt"],
                          f"narrative_debt 缺少字段 {key}")
        for key in ("required_cost", "must_not_be_cost_free"):
            self.assertIn(key, plan["risk"], f"risk 缺少字段 {key}")
        self.assertIn("forbidden_hooks", plan["repetition"])
        self.assertIsInstance(plan["repetition"]["forbidden_hooks"], list)
        self.assertTrue(plan["risk"]["must_not_be_cost_free"])

    def test_required_aftershock_chapters_per_constitution_4_1(self):
        """CONSTITUTION.md 4.1 的合同 schema 将 required_aftershock_chapters
        置于 engagement_plan 顶层；实现放在 payoff 内，此处按宪章断言。"""
        cpath = PROJECTS / E2E_SLUG / "contracts" / "chapter_231.json"
        c = json.loads(cpath.read_text(encoding="utf-8"))
        plan = c["engagement_plan"]
        self.assertIn("required_aftershock_chapters", plan,
                      "宪章 4.1：required_aftershock_chapters 应在 "
                      "engagement_plan 顶层（实际实现嵌套在 payoff 内）")

    def test_prompt_is_self_contained_chinese_doc(self):
        ppath = PROJECTS / E2E_SLUG / "prompts" / "chapter_231.md"
        self.assertTrue(ppath.exists(), f"缺少提示词文件 {ppath}")
        text = ppath.read_text(encoding="utf-8")
        plan = json.loads((PROJECTS / E2E_SLUG / "contracts" /
                           "chapter_231.json").read_text(encoding="utf-8"))
        plan = plan["engagement_plan"]
        self.assertGreater(len(text), 1500, "提示词过短，疑似不自包含")
        self.assertIn("第 231 章续写任务", text)
        self.assertIn("章节合同（JSON）", text)
        self.assertIn("engagement_plan", text)
        self.assertIn("最近章节原文摘要", text)
        self.assertIn("输出要求", text)
        # 宪章 4.2：合同只含禁令（forbidden_hooks），不得含"必须使用的桥段"类字段
        self.assertNotIn("required_hooks", plan["repetition"],
                         "合同不得指定必须使用的桥段")
        self.assertNotIn("must_use_hooks", plan,
                         "合同不得指定必须使用的桥段")


class TestRecordIdempotent(unittest.TestCase):
    """record 幂等：同一章重复 record 不重复计数。"""

    @classmethod
    def setUpClass(cls):
        TEMPS.mkdir(exist_ok=True)
        cls.chapter_file = TEMPS / "e2e_record_chapter.md"
        cls.chapter_file.write_text(
            "## 第231章 续写测试\n\n列车驶入浓雾。\n", encoding="utf-8")
        r = run_cli("init", str(DEATH_TRAIN_SRC), "--slug", E2E_SLUG)
        if r.returncode != 0:
            raise RuntimeError(f"init 失败:\n{r.stdout}\n{r.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / E2E_SLUG, ignore_errors=True)
        cls.chapter_file.unlink(missing_ok=True)

    def _record(self):
        return run_cli("record", E2E_SLUG, "--chapter", "231",
                       "--file", str(self.chapter_file),
                       "--payoff-group", "resource",
                       "--payoff-subtype", "资源阶段毕业",
                       "--payoff-intensity", "35",
                       "--pressure", "85,72,66,55,30,42",
                       "--new-hook", "浓雾中的第二列车从何而来")

    def _read_state(self):
        base = PROJECTS / E2E_SLUG
        return {
            "history": json.loads((base / "history.json")
                                  .read_text(encoding="utf-8")),
            "book": json.loads((base / "book.json").read_text(encoding="utf-8")),
            "hooks": json.loads((base / "hooks.json").read_text(encoding="utf-8")),
        }

    def test_duplicate_record_not_double_counted(self):
        r = self._record()
        self.assertEqual(r.returncode, 0,
                         f"第 1 次 record 失败:\n{r.stdout}\n{r.stderr}")
        state_after_first = self._read_state()

        r = self._record()
        self.assertEqual(r.returncode, 0,
                         f"第 2 次 record 失败:\n{r.stdout}\n{r.stderr}")
        state_after_second = self._read_state()

        history, book, hooks = (state_after_second["history"],
                                state_after_second["book"],
                                state_after_second["hooks"])

        payoff_231 = [e for e in history.get("payoff_events", [])
                      if e.get("chapter") == 231]
        self.assertEqual(len(payoff_231), 1,
                         f"payoff_events 重复计数: {payoff_231}")
        pressure_231 = [p for p in history.get("pressure_history", [])
                        if p.get("chapter") == 231]
        self.assertEqual(len(pressure_231), 1,
                         f"pressure_history 重复计数: {pressure_231}")
        budget_231 = [b for b in book.get("budget_10ch", [])
                      if b.get("chapter") == 231]
        self.assertEqual(len(budget_231), 1,
                         f"budget_10ch 重复计数: {budget_231}")
        real_hooks = [h for h in hooks
                      if isinstance(h, dict) and not h.get("_comment")]
        self.assertEqual(len(real_hooks), 1, "hooks.json 重复追加了悬念")
        self.assertEqual(book.get("current_chapter"), 231)
        self.assertEqual(book.get("next_write_chapter"), 232)
        # 大爽点（>=30）应更新 resource 组冷却
        cds = {c["group"]: c for c in book.get("payoff_cooldowns", [])}
        self.assertEqual(cds["resource"]["last_major_chapter"], 231)
        # 成稿落盘
        self.assertTrue((PROJECTS / E2E_SLUG / "chapters" /
                         "chapter_231.md").exists())

        # 幂等性：重复 record 后整体台账状态应与第一次完全一致
        self.assertEqual(
            state_after_first, state_after_second,
            "重复 record 后台账状态漂移（期望完全幂等）；"
            "差异详见验证报告")


class TestCacheInvalidation(unittest.TestCase):
    """缓存失效：chapters_index.json 含 sha256，源文件变化触发重切。"""

    @classmethod
    def setUpClass(cls):
        TEMPS.mkdir(exist_ok=True)
        cls.source = TEMPS / "e2e_cache_source.md"
        cls.source.write_text(
            "---\ntitle: \"缓存测试\"\nchapter_count: 3\n---\n\n"
            "## 第1章 起点\n\n内容一。\n\n"
            "## 第2章 转折\n\n内容二。\n\n"
            "## 第3章 高潮\n\n内容三。\n\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / CACHE_SLUG, ignore_errors=True)
        cls.source.unlink(missing_ok=True)

    def test_sha256_change_triggers_resplit(self):
        r = run_cli("init", str(self.source), "--slug", CACHE_SLUG)
        self.assertEqual(r.returncode, 0,
                         f"init 失败:\n{r.stdout}\n{r.stderr}")
        index_p = PROJECTS / CACHE_SLUG / "chapters_index.json"
        idx1 = json.loads(index_p.read_text(encoding="utf-8"))
        self.assertEqual(idx1["source_sha256"], sha256_file(self.source),
                         "chapters_index.json 未记录源文件 sha256")
        self.assertEqual(len(idx1["entries"]), 3)

        # 篡改前：get_or_build_index 应命中缓存（哨兵标记仍在）
        sys.path.insert(0, str(ROOT))
        from novelwriter import state
        idx1["__sentinel__"] = "cached"
        state.save_index(CACHE_SLUG, idx1)
        cached = state.get_or_build_index(CACHE_SLUG, self.source)
        self.assertEqual(cached.get("__sentinel__"), "cached",
                         "sha256 未变时应复用缓存索引")

        # 篡改源文件（temps 中的小副本）：新增第 4 章
        with self.source.open("a", encoding="utf-8") as f:
            f.write("## 第4章 新增\n\n内容四。\n\n")

        # 篡改后：应检测到 sha256 变化并重切（哨兵消失、章数更新）
        rebuilt = state.get_or_build_index(CACHE_SLUG, self.source)
        self.assertNotIn("__sentinel__", rebuilt,
                         "源文件已变化但仍返回旧缓存")
        self.assertEqual(rebuilt["source_sha256"], sha256_file(self.source))
        self.assertEqual(len(rebuilt["entries"]), 4, "篡改后未触发重切")
        idx2 = json.loads(index_p.read_text(encoding="utf-8"))
        self.assertEqual(len(idx2["entries"]), 4, "重切结果未落盘")


class TestPayoffDraftEndToEnd(unittest.TestCase):
    """M1：payoff_draft 端到端。填分 → S 分 → 五档 → aftershock 生效；
    未填 → 合同 target_score 为空、aftershock 为 0、报告标注待填写。"""

    SLUG = "e2e-payoff-draft"

    @classmethod
    def setUpClass(cls):
        r = run_cli("init", str(DEATH_TRAIN_SRC), "--slug", cls.SLUG)
        if r.returncode != 0:
            raise RuntimeError(f"init 失败:\n{r.stdout}\n{r.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / cls.SLUG, ignore_errors=True)

    def _contract(self):
        cpath = PROJECTS / self.SLUG / "contracts" / "chapter_231.json"
        return json.loads(cpath.read_text(encoding="utf-8"))

    def _fill_draft(self):
        book_path = PROJECTS / self.SLUG / "book.json"
        book = json.loads(book_path.read_text(encoding="utf-8"))
        book["payoff_draft"] = {
            "M": {"scarcity_pressure": 80, "setup_depth": 80,
                  "wait_time": 80, "paid_cost": 80, "arc_fit": 80},
            "I": {"relative_gain": 70, "restriction_lifted": 70,
                  "behavior_change": 70, "future_growth": 70,
                  "social_feedback": 70},
            "C": {"causal_chain": 90, "rule_consistency": 90,
                  "price_paid": 90, "source_foreshadowed": 90},
            "A": {"new_gameplay": 60, "decision_change": 60,
                  "higher_tier_demand": 60, "group_impact": 60},
            "D": 10,
        }
        book_path.write_text(json.dumps(book, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def test_1_unfilled_marks_pending(self):
        r = run_cli("plan", self.SLUG)
        self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
        plan = self._contract()["engagement_plan"]
        self.assertEqual(plan["payoff"]["target_score"], "")
        self.assertEqual(plan["required_aftershock_chapters"], 0)
        r2 = run_cli("analyze", self.SLUG)
        self.assertEqual(r2.returncode, 0)
        report = (PROJECTS / self.SLUG / "reports" / "analyze.md").read_text(
            encoding="utf-8")
        self.assertIn("待作者填写", report)

    def test_2_filled_produces_score_and_aftershock(self):
        # M=80 I=70 N=100（无历史）C=90 A=60 F=0 D=10
        # S = 20 + 17.5 + 15 + 13.5 + 12 − 0 − 1 = 77.0（中型爽点档）
        self._fill_draft()
        r = run_cli("plan", self.SLUG)
        self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
        self.assertIn("适合中型爽点", r.stdout)
        plan = self._contract()["engagement_plan"]
        self.assertEqual(plan["payoff"]["target_score"], 77.0)
        self.assertEqual(plan["required_aftershock_chapters"], 3)
        r2 = run_cli("analyze", self.SLUG)
        self.assertEqual(r2.returncode, 0)
        report = (PROJECTS / self.SLUG / "reports" / "analyze.md").read_text(
            encoding="utf-8")
        self.assertIn("净分 S = 77.0", report)
        self.assertIn("适合中型爽点", report)


class TestAdvanceHookIdempotent(unittest.TestCase):
    """M4：--advance-hook 重复 record 同章，advance 事件不丢失，
    状态（progress/reminder_count）不二次推进。"""

    SLUG = "e2e-advance-hook"

    @classmethod
    def setUpClass(cls):
        TEMPS.mkdir(exist_ok=True)
        cls.ch231 = TEMPS / "e2e_advance_ch231.md"
        cls.ch232 = TEMPS / "e2e_advance_ch232.md"
        cls.ch231.write_text("## 第231章 埋设\n\n浓雾出现。\n",
                             encoding="utf-8")
        cls.ch232.write_text("## 第232章 推进\n\n第二列车露出轮廓。\n",
                             encoding="utf-8")
        r = run_cli("init", str(DEATH_TRAIN_SRC), "--slug", cls.SLUG)
        if r.returncode != 0:
            raise RuntimeError(f"init 失败:\n{r.stdout}\n{r.stderr}")
        r = run_cli("record", cls.SLUG, "--chapter", "231",
                    "--file", str(cls.ch231),
                    "--new-hook", "浓雾中的第二列车从何而来")
        if r.returncode != 0:
            raise RuntimeError(f"record 231 失败:\n{r.stdout}\n{r.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / cls.SLUG, ignore_errors=True)
        cls.ch231.unlink(missing_ok=True)
        cls.ch232.unlink(missing_ok=True)

    def _record_advance(self):
        return run_cli("record", self.SLUG, "--chapter", "232",
                       "--file", str(self.ch232),
                       "--advance-hook", "h001")

    def _state(self):
        base = PROJECTS / self.SLUG
        return {
            "history": json.loads((base / "history.json")
                                  .read_text(encoding="utf-8")),
            "hooks": json.loads((base / "hooks.json")
                                .read_text(encoding="utf-8")),
        }

    def test_advance_event_survives_duplicate_record(self):
        r = self._record_advance()
        self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
        first = self._state()
        adv = [e for e in first["history"]["hook_events"]
               if e.get("chapter") == 232 and e.get("action") == "advance"]
        self.assertEqual(len(adv), 1, f"首次 advance 事件缺失: {first}")

        r = self._record_advance()
        self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
        second = self._state()
        adv = [e for e in second["history"]["hook_events"]
               if e.get("chapter") == 232 and e.get("action") == "advance"]
        self.assertEqual(len(adv), 1, "重复 record 后 advance 事件丢失")
        self.assertEqual(first, second, "重复 record 后台账漂移（期望幂等）")
        h001 = next(h for h in second["hooks"] if h.get("id") == "h001")
        self.assertEqual(h001["progress"], 0.2)
        self.assertEqual(h001["reminder_count"], 2)


class TestCooldownRollback(unittest.TestCase):
    """M5：重录低强度爽点后，冷却组 last_major_chapter 由数据推导回滚。"""

    SLUG = "e2e-cooldown-rollback"

    @classmethod
    def setUpClass(cls):
        TEMPS.mkdir(exist_ok=True)
        cls.chapter_file = TEMPS / "e2e_cooldown_chapter.md"
        cls.chapter_file.write_text("## 第231章 冷却测试\n\n正文。\n",
                                    encoding="utf-8")
        r = run_cli("init", str(DEATH_TRAIN_SRC), "--slug", cls.SLUG)
        if r.returncode != 0:
            raise RuntimeError(f"init 失败:\n{r.stdout}\n{r.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / cls.SLUG, ignore_errors=True)
        cls.chapter_file.unlink(missing_ok=True)

    def _record(self, intensity):
        return run_cli("record", self.SLUG, "--chapter", "231",
                       "--file", str(self.chapter_file),
                       "--payoff-group", "resource",
                       "--payoff-intensity", str(intensity))

    def _cooldown(self):
        book = json.loads((PROJECTS / self.SLUG / "book.json")
                          .read_text(encoding="utf-8"))
        return {c["group"]: c for c in book["payoff_cooldowns"]}

    def test_re_record_low_intensity_rolls_back_cooldown(self):
        r = self._record(40)
        self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
        self.assertEqual(self._cooldown()["resource"]["last_major_chapter"],
                         231)
        # 重录为低强度（<30）：该章不再是 resource 组大爽点 → 回滚为 0
        r = self._record(15)
        self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
        self.assertEqual(self._cooldown()["resource"]["last_major_chapter"],
                         0, "重录低强度爽点后 last_major_chapter 未回滚")


class TestSourcePathPosix(unittest.TestCase):
    """M6：source_path 落盘为 POSIX 相对路径；跨 CWD 运行 plan 仍能
    以 ROOT 为基准解析源文件并取到最近章节摘要。"""

    SLUG = "e2e-source-path"

    @classmethod
    def setUpClass(cls):
        cls.rel_src = str(DEATH_TRAIN_SRC.relative_to(ROOT))
        r = run_cli("init", cls.rel_src, "--slug", cls.SLUG)
        if r.returncode != 0:
            raise RuntimeError(f"init 失败:\n{r.stdout}\n{r.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / cls.SLUG, ignore_errors=True)

    def test_source_path_is_posix_relative(self):
        expected = DEATH_TRAIN_SRC.relative_to(ROOT).as_posix()
        book = json.loads((PROJECTS / self.SLUG / "book.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(book["source_path"], expected)
        self.assertNotIn("\\", book["source_path"])
        idx = json.loads((PROJECTS / self.SLUG / "chapters_index.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(idx["source_path"], expected)

    def test_plan_from_other_cwd_still_resolves_summaries(self):
        TEMPS.mkdir(exist_ok=True)
        r = run_cli_cwd(TEMPS, "plan", self.SLUG)
        self.assertEqual(r.returncode, 0, f"{r.stdout}\n{r.stderr}")
        prompt = (PROJECTS / self.SLUG / "prompts" /
                  "chapter_231.md").read_text(encoding="utf-8")
        self.assertIn("最近章节原文摘要", prompt)
        self.assertIn("原著第 230 章", prompt,
                      "跨 CWD plan 未取到原著最近章节摘要")


class TestRangeValidation(unittest.TestCase):
    """Minor5：--pressure 分项与 --payoff-intensity 越界（0-100）拒绝。"""

    SLUG = "e2e-range-check"

    @classmethod
    def setUpClass(cls):
        TEMPS.mkdir(exist_ok=True)
        cls.chapter_file = TEMPS / "e2e_range_chapter.md"
        cls.chapter_file.write_text("## 第231章 校验测试\n\n正文。\n",
                                    encoding="utf-8")
        r = run_cli("init", str(DEATH_TRAIN_SRC), "--slug", cls.SLUG)
        if r.returncode != 0:
            raise RuntimeError(f"init 失败:\n{r.stdout}\n{r.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(PROJECTS / cls.SLUG, ignore_errors=True)
        cls.chapter_file.unlink(missing_ok=True)

    def test_pressure_component_out_of_range_rejected(self):
        r = run_cli("record", self.SLUG, "--chapter", "231",
                    "--file", str(self.chapter_file),
                    "--pressure", "85,72,66,55,30,150")
        self.assertEqual(r.returncode, 2)
        self.assertIn("out of range", r.stdout + r.stderr)

    def test_payoff_intensity_out_of_range_rejected(self):
        r = run_cli("record", self.SLUG, "--chapter", "231",
                    "--file", str(self.chapter_file),
                    "--payoff-group", "resource",
                    "--payoff-intensity", "120")
        self.assertEqual(r.returncode, 2)
        self.assertIn("out of range", r.stdout + r.stderr)

    def test_rejected_records_leave_ledger_untouched(self):
        history = json.loads((PROJECTS / self.SLUG / "history.json")
                             .read_text(encoding="utf-8"))
        self.assertEqual(history.get("payoff_events"), [])
        self.assertEqual(history.get("pressure_history"), [])


if __name__ == "__main__":
    unittest.main()
