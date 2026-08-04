"""test_loader.py —— 素材读取与切章测试（标准库 unittest）。

验证项：
1. 5 个 UTF-8 md 素材：切章数 == frontmatter chapter_count，编码探测为 utf-8；
2. 斗罗大陆.txt：编码回退 gb18030，切章数 332±2（源文件本身缺 4 个章头）；
3. 中文数字转换；
4. 大文件（我合成了全世界，9MB/1200章）切章性能抽查（只记录，不设硬断言）。
"""

import time
import unittest
from pathlib import Path

from novelwriter import loader

ROOT = Path(__file__).resolve().parent.parent
INSPIRATIONS = ROOT / "inspirations"
TEMPS = ROOT / "temps"

# 文件名 → frontmatter chapter_count（任务书给定黄金值）
MD_SOURCES = {
    "全民纜車求生，我一級一個三選一_正文全集.md": 294,
    "全民求生，我能夠自選寶箱獎勵_正文全集.md": 516,
    "全民海上求生：我的載具是玄武_正文全集.md": 301,
    "死亡列車：開局SSS級天賦！_正文全集.md": 230,
    "我合成了全世界_正文全集.md": 1200,
}


class TestMarkdownSources(unittest.TestCase):
    """5 个 UTF-8 md 素材：编码探测 + 切章数对齐 frontmatter。"""

    def test_md_chapter_count_matches_frontmatter(self):
        for name, expected_count in MD_SOURCES.items():
            with self.subTest(file=name):
                path = INSPIRATIONS / name
                self.assertTrue(path.exists(), f"素材缺失: {path}")
                text, encoding = loader.read_text(path)
                # 编码探测必须落在 utf-8 路径，不得回退 gb18030
                self.assertTrue(encoding.startswith("utf-8"),
                                f"{name} 编码探测为 {encoding}，落入 gb18030 路径")
                index = loader.build_chapter_index(path, text)
                entries = index["entries"]
                fm_count = index["frontmatter"].get("chapter_count")
                self.assertEqual(fm_count, expected_count,
                                 f"{name} frontmatter chapter_count={fm_count}")
                self.assertEqual(len(entries), fm_count,
                                 f"{name} 切出 {len(entries)} 章 != {fm_count}")
                self.assertIsNone(index["warning"],
                                  f"{name} 切章出现警告: {index['warning']}")
                # 注：源数据存在章号重复/跳号（如纜車 224-233 重复、
                # 寶箱缺 382、全世界多处重号），属素材数据质量问题，
                # 不影响切章总数对齐，故此处不断言章号连续性。


class TestTxtSourceGb18030(unittest.TestCase):
    """斗罗大陆.txt：编码回退 gb18030，切章数 332±2（源文件缺 4 个章头）。"""

    def test_douluo_encoding_fallback_and_chapter_count(self):
        path = INSPIRATIONS / "斗罗大陆.txt"
        self.assertTrue(path.exists(), f"素材缺失: {path}")
        text, encoding = loader.read_text(path)
        self.assertEqual(encoding, "gb18030",
                         f"期望 gb18030 回退，实际 {encoding}")
        index = loader.build_chapter_index(path, text)
        entries = index["entries"]
        n = len(entries)
        self.assertGreaterEqual(n, 330, f"切章数 {n} 低于 332-2 容差")
        self.assertLessEqual(n, 334, f"切章数 {n} 高于 332+2 容差")
        self.assertIsNone(index["warning"])
        # 抽一章正文可读（含汉字）
        sample = loader.read_chapter_text(path, entries[0], text)
        self.assertIn("第", sample[:40])

    def test_invalid_encoding_raises_valueerror(self):
        bad = TEMPS / "bad_encoding.bin"
        TEMPS.mkdir(exist_ok=True)
        # 0xFF 在 utf-8 与 gb18030（合法首字节 0x81-0xFE）下均非法
        bad.write_bytes(b"\xff\xfe\xff\xfe")
        try:
            with self.assertRaises(ValueError):
                loader.read_text(bad)
        finally:
            bad.unlink(missing_ok=True)


class TestChineseNumerals(unittest.TestCase):
    """中文数字转换（loader.chinese_numeral_to_int）。"""

    CASES = {
        "三百三十六": 336,
        "五十二": 52,
        "十五": 15,
        "二十": 20,
        "两百零三": 203,
        "一千二百": 1200,
        "一": 1,
        "十": 10,
        "九百九十九": 999,
        "42": 42,
    }

    def test_numeral_cases(self):
        for cn, value in self.CASES.items():
            with self.subTest(cn=cn):
                self.assertEqual(loader.chinese_numeral_to_int(cn), value)

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            loader.chinese_numeral_to_int("三万")  # 不支持万位
        with self.assertRaises(ValueError):
            loader.chinese_numeral_to_int("")


class TestLargeFilePerformance(unittest.TestCase):
    """大文件性能抽查：我合成了全世界（9MB/1200章）。只记录，不设硬断言。"""

    def test_perf_synthesized_world(self):
        path = INSPIRATIONS / "我合成了全世界_正文全集.md"
        t0 = time.perf_counter()
        text, encoding = loader.read_text(path)
        t_read = time.perf_counter() - t0
        t1 = time.perf_counter()
        index = loader.build_chapter_index(path, text)
        t_split = time.perf_counter() - t1
        n = len(index["entries"])
        size_mb = path.stat().st_size / 1024 / 1024
        line = (f"[perf] 我合成了全世界: {size_mb:.1f}MB {n}章 "
                f"编码={encoding} 读取={t_read:.3f}s 切章={t_split:.3f}s "
                f"合计={t_read + t_split:.3f}s")
        print(line)
        TEMPS.mkdir(exist_ok=True)
        with (TEMPS / "perf_report.txt").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        # 只做记录，不设硬性阈值断言；仅防御性确认切章结果合理
        self.assertEqual(n, 1200)


if __name__ == "__main__":
    unittest.main()
