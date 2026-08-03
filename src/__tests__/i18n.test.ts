/**
 * i18n（V1.1：开局选择语言）——四语文本表（novel + engine）、缺键回退 zh、
 * 语言校验、slugify ASCII/NFKD、旧存档向后兼容（无 language 字段按 zh）、
 * 引擎结算文案按存档语言生成（C1：非中文局大事记不得出现中文引擎模板）。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { validateBlueprint } from '../blueprint.ts';
import {
  DEFAULT_LANGUAGE,
  engineStrings,
  getEngineStrings,
  getNovelStrings,
  isLanguage,
  languageOf,
  novelStrings,
  SUPPORTED_LANGUAGES,
} from '../i18n.ts';
import type { EngineStrings, NovelStrings } from '../i18n.ts';
import { initState, sha256, slugify } from '../save.ts';
import type { Blueprint, GameState, Language } from '../types.ts';
import { cliScript, echoBlueprintPath, GOLDEN_SEED, GOLDEN_SEQUENCE, loadEchoBlueprint } from './helpers.ts';

function tmpBase(): string {
  return mkdtempSync(path.join(tmpdir(), 'tgn-lang-'));
}

interface CliResult {
  ok: boolean;
  data?: any;
  error?: { code: string; message: string; details?: string[] };
}

function cli(base: string, ...args: string[]): CliResult {
  let out: string;
  try {
    out = execFileSync(process.execPath, [cliScript, ...args], { cwd: base, encoding: 'utf8' });
  } catch (err) {
    const e = err as { stdout?: Buffer | string };
    out = typeof e.stdout === 'string' ? e.stdout : (e.stdout?.toString('utf8') ?? '');
    if (!out.trim()) throw err;
  }
  const lines = out.trim().split('\n');
  return JSON.parse(lines[lines.length - 1]!) as CliResult;
}

function clone(): Blueprint {
  return JSON.parse(JSON.stringify(loadEchoBlueprint())) as Blueprint;
}

/** novel 文案键 → 样例参数渲染（新增键必须在此登记，否则测试失败）。 */
const novelSamples: Record<keyof NovelStrings, (t: NovelStrings) => string> = {
  worldFromPrompt: (t) => t.worldFromPrompt('一句话'),
  metaWorld: (t) => t.metaWorld('世界名'),
  metaControlAxis: (t) => t.metaControlAxis('知识'),
  metaSeed: (t) => t.metaSeed(44),
  metaTurns: (t) => t.metaTurns(20),
  metaFinalTier: (t) => t.metaFinalTier(2),
  metaLeverage: (t) => t.metaLeverage('杠杆', 3),
  tocTitle: (t) => t.tocTitle,
  tocChapter: (t) => t.tocChapter(1, '章名', 1, 10),
  tocFinal: (t) => t.tocFinal(2, '胜利'),
  chapterHeading: (t) => t.chapterHeading(1, '章名'),
  finalHeading: (t) => t.finalHeading('胜利'),
  keyMomentsTitle: (t) => t.keyMomentsTitle,
  chronicleTitle: (t) => t.chronicleTitle,
  historyLine: (t) => t.historyLine(1, '事件'),
  footer: (t) => t.footer,
};

/** engine 文案键 → 样例参数渲染（新增键必须在此登记，否则测试失败）。 */
const engineSamples: Record<keyof EngineStrings, (t: EngineStrings) => string> = {
  openingEntry: (t) => t.openingEntry('世界名', '知识'),
  endingEntry: (t) => t.endingEntry('原因'),
  winReason: (t) => t.winReason('描述'),
  loseReason: (t) => t.loseReason('描述'),
  tierUp: (t) => t.tierUp('阶名', '描述'),
  regionUnlocked: (t) => t.regionUnlocked('区域名'),
  paidTime: (t) => t.paidTime(2),
  paidAsset: (t) => t.paidAsset('资产名', 1),
  assetDelta: (t) => t.assetDelta('资产名', '+1', 5),
  learnedFact: (t) => t.learnedFact('事实描述'),
  flagSet: (t) => t.flagSet('flag-id'),
  flagCleared: (t) => t.flagCleared('flag-id'),
  maintenance: (t) => t.maintenance('资产名', '支付资产', 1),
  leverageApplied: (t) => t.leverageApplied('杠杆名'),
  outcome: (t) => t.outcome('行动名', '结果描述'),
  irreversible: (t) => t.irreversible,
  expansionTriggered: (t) => t.expansionTriggered('rule-id', '规则描述'),
  expansionMaterialized: (t) => t.expansionMaterialized('rule-id', 'fact-id', '事实描述'),
};

test('支持的语言集合与默认值', () => {
  assert.deepEqual([...SUPPORTED_LANGUAGES], ['zh', 'en', 'fr', 'ar']);
  assert.equal(DEFAULT_LANGUAGE, 'zh');
  assert.ok(isLanguage('zh') && isLanguage('en') && isLanguage('fr') && isLanguage('ar'));
  assert.ok(!isLanguage('de'));
  assert.ok(!isLanguage(''));
  assert.ok(!isLanguage(42));
});

test('结构化：novelStrings 覆盖全部受支持语言，键集一致且每键非空', () => {
  const zhKeys = Object.keys(novelSamples).sort() as (keyof NovelStrings)[];
  for (const lang of SUPPORTED_LANGUAGES) {
    assert.ok(lang in novelStrings, `novelStrings 缺少语言 ${lang}`);
    const t = getNovelStrings(lang);
    assert.deepEqual(Object.keys(t).sort(), Object.keys(novelStrings.zh).sort(), `${lang} 键集必须与 zh 一致`);
    for (const key of zhKeys) {
      const rendered = novelSamples[key](t);
      assert.ok(typeof rendered === 'string' && rendered.trim().length > 0, `${lang}/${key} 渲染为空`);
    }
  }
});

test('结构化：engineStrings 覆盖全部受支持语言，键集一致且每键非空', () => {
  const keys = Object.keys(engineSamples).sort() as (keyof EngineStrings)[];
  for (const lang of SUPPORTED_LANGUAGES) {
    assert.ok(lang in engineStrings, `engineStrings 缺少语言 ${lang}`);
    const t = getEngineStrings(lang);
    assert.deepEqual(Object.keys(t).sort(), Object.keys(engineStrings.zh).sort(), `${lang} 键集必须与 zh 一致`);
    for (const key of keys) {
      const rendered = engineSamples[key](t);
      assert.ok(typeof rendered === 'string' && rendered.trim().length > 0, `${lang}/${key} 渲染为空`);
    }
  }
});

test('四种语言的 novel 文案互不相同，engine 文案互不相同', () => {
  const novelRenders = SUPPORTED_LANGUAGES.map((l) => ({
    lang: l,
    rows: ((Object.keys(novelSamples) as (keyof NovelStrings)[])).map((k) => novelSamples[k](getNovelStrings(l))),
  }));
  const engineRenders = SUPPORTED_LANGUAGES.map((l) => ({
    lang: l,
    rows: ((Object.keys(engineSamples) as (keyof EngineStrings)[])).map((k) => engineSamples[k](getEngineStrings(l))),
  }));
  for (const renders of [novelRenders, engineRenders]) {
    for (let i = 0; i < renders.length; i++) {
      for (let j = i + 1; j < renders.length; j++) {
        assert.notDeepEqual(renders[i]!.rows, renders[j]!.rows, `${renders[i]!.lang} 与 ${renders[j]!.lang} 文案不得相同`);
      }
    }
  }
});

test('关键标签快照（书名页/目录/大事记/终局）', () => {
  assert.equal(getNovelStrings('zh').tocTitle, '## 目录');
  assert.equal(getNovelStrings('zh').chronicleTitle, '### 大事记');
  assert.equal(getNovelStrings('en').tocTitle, '## Contents');
  assert.equal(getNovelStrings('en').chronicleTitle, '### Chronicle');
  assert.equal(getNovelStrings('fr').tocTitle, '## Sommaire');
  assert.equal(getNovelStrings('fr').chronicleTitle, '### Chronique');
  assert.equal(getNovelStrings('ar').tocTitle, '## الفهرس');
  assert.equal(getNovelStrings('ar').chronicleTitle, '### سجل الأحداث');
  // 阿拉伯语直接输出 RTL 文本（含阿拉伯字符）
  assert.match(getNovelStrings('ar').footer, /[\u0600-\u06FF]/);
  // 引擎文案快照：终局/跃迁/时间成本
  assert.equal(getEngineStrings('zh').endingEntry('r'), '终局：r');
  assert.equal(getEngineStrings('en').endingEntry('r'), 'Ending: r');
  assert.equal(getEngineStrings('fr').endingEntry('r'), 'Fin : r');
  assert.equal(getEngineStrings('en').paidTime(1), 'Spent 1 turn of time');
  assert.equal(getEngineStrings('en').paidTime(2), 'Spent 2 turns of time');
  // tocFinal 保持 "N. 终章…" 目录序号格式（四语等价）
  assert.equal(getNovelStrings('zh').tocFinal(3, '胜利'), '3. 终章：胜利');
  assert.equal(getNovelStrings('en').tocFinal(3, 'win'), '3. Final Chapter: win');
  assert.equal(getNovelStrings('fr').tocFinal(3, 'fin'), '3. Chapitre final : fin');
  assert.equal(getNovelStrings('ar').tocFinal(3, 'نهاية'), '3. الفصل الختامي: نهاية');
});

test('未知语言回退 zh（键缺失/非法值的回退策略）', () => {
  assert.equal(getNovelStrings('de'), novelStrings.zh);
  assert.equal(getNovelStrings(undefined), novelStrings.zh);
  assert.equal(getNovelStrings(null), novelStrings.zh);
  assert.equal(getNovelStrings('ZH'), novelStrings.zh);
  assert.equal(getEngineStrings('de'), engineStrings.zh);
  assert.equal(getEngineStrings(undefined), engineStrings.zh);
});

test('languageOf：旧存档无 language 字段按 zh 处理', () => {
  assert.equal(languageOf({ language: undefined } as GameState), 'zh');
  assert.equal(languageOf({ language: 'fr' } as GameState), 'fr');
  assert.equal(languageOf({ language: 'xx' } as unknown as GameState), 'zh');
});

test('校验器：language 非法值被拒（INVALID_LANGUAGE）', () => {
  const bp = clone();
  bp.meta.language = 'de' as Language;
  const issues = validateBlueprint(bp).issues;
  assert.ok(issues.some((i) => i.code === 'INVALID_LANGUAGE' && i.path === 'meta.language'), JSON.stringify(issues));
});

test('校验器：language 缺省视为 zh，合法值通过', () => {
  const bare = clone();
  assert.equal(bare.meta.language, undefined, '演示 Blueprint 本身无 language（旧格式 fixture）');
  assert.equal(validateBlueprint(bare).ok, true);
  for (const lang of SUPPORTED_LANGUAGES) {
    const bp = clone();
    bp.meta.language = lang;
    const result = validateBlueprint(bp);
    assert.equal(result.ok, true, `${lang} 应通过校验：${JSON.stringify(result.issues)}`);
  }
});

test('initState：语言优先级为显式参数 > blueprint.meta.language > zh', () => {
  const bp = clone();
  assert.equal(initState(bp, 'w', 1).language, 'zh', '无 language 缺省 zh');
  bp.meta.language = 'fr';
  assert.equal(initState(bp, 'w', 1).language, 'fr', '取 blueprint 值');
  assert.equal(initState(bp, 'w', 1, 'ar').language, 'ar', '显式参数优先');
});

test('slugify：非拉丁标题回退数字编号，保持 ASCII 文件名', () => {
  assert.equal(slugify('潮声初闻', '001'), '001', '中文标题回退编号');
  assert.equal(slugify('الفصل الأول', '002'), '002', '阿拉伯文标题回退编号');
  assert.equal(slugify('Echo Tide'), 'echo-tide', '拉丁标题保留');
  assert.equal(slugify('Echo 潮声港', '003'), 'echo', '混排保留拉丁部分');
  assert.equal(slugify(''), 'untitled', '空串用默认 fallback');
});

test('slugify：NFKD 去音标（法语带音标与撇号标题）', () => {
  assert.equal(slugify("La Marée d'Écho"), 'la-maree-decho', '音标剥离、撇号省略');
  assert.equal(slugify('Été à Paris'), 'ete-a-paris');
  assert.equal(slugify('Ça va très bien'), 'ca-va-tres-bien');
});

test('CLI：默认开局语言为 zh，status/list 输出 language', () => {
  const base = tmpBase();
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'w-zh', '--seed', '1');
  assert.equal(n.ok, true, JSON.stringify(n.error));
  assert.equal(n.data.language, 'zh');
  const st = cli(base, 'status', '--world', 'w-zh');
  assert.equal(st.ok, true);
  assert.equal(st.data.language, 'zh');
  const list = cli(base, 'list');
  assert.equal(list.ok, true);
  assert.ok(list.data.saves.some((s: { world: string; language: string }) => s.world === 'w-zh' && s.language === 'zh'));
});

test('CLI：--language 优先于 blueprint 值并回写冻结 blueprint（M1）', () => {
  const base = tmpBase();
  // blueprint 声明 fr，CLI 覆盖为 en
  const bp = clone();
  bp.meta.language = 'fr';
  const bpFile = path.join(base, 'bp.blueprint.json');
  writeFileSync(bpFile, JSON.stringify(bp), 'utf8');
  const n = cli(base, 'new', '--blueprint', bpFile, '--world', 'w-en', '--seed', '1', '--language', 'en');
  assert.equal(n.ok, true, JSON.stringify(n.error));
  assert.equal(n.data.language, 'en', '--language 优先于 blueprint.meta.language');
  // M1：冻结副本必须与 state 语言一致（单一事实源）
  const frozen = JSON.parse(readFileSync(path.join(base, 'saves', 'w-en', 'blueprint.json'), 'utf8'));
  assert.equal(frozen.meta.language, 'en', '冻结 blueprint 回写最终 language');
  const state = JSON.parse(readFileSync(path.join(base, 'saves', 'w-en', 'state.json'), 'utf8'));
  assert.equal(state.language, 'en');
  const end = cli(base, 'end', '--reason', 'early end');
  assert.equal(end.ok, true, JSON.stringify(end.error));
  const novel = readFileSync(path.join(base, end.data.novel), 'utf8');
  assert.ok(novel.includes('## Contents'), 'en 局 novel 含英文目录标签');
  assert.ok(novel.includes('### Chronicle'), 'en 局 novel 含英文大事记标签');
  assert.ok(!novel.includes('## 目录'), 'en 局 novel 不含中文标签');
  assert.match(novel, /^1\. Final Chapter: early end$/m, '目录终章行带序号前缀');
});

test('CLI：blueprint 无 language 时 end 合成的 novel 为 zh', () => {
  const base = tmpBase();
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'w-default', '--seed', '1');
  assert.equal(n.ok, true, JSON.stringify(n.error));
  const end = cli(base, 'end', '--reason', 'early end');
  assert.equal(end.ok, true, JSON.stringify(end.error));
  const novel = readFileSync(path.join(base, end.data.novel), 'utf8');
  assert.ok(novel.includes('## 目录'), '缺省 zh 局 novel 含中文目录标签');
  assert.match(novel, /^1\. 终章：early end$/m, 'zh 目录终章行带序号前缀');
});

test('CLI：非法 --language 被拒（BAD_LANGUAGE）', () => {
  const base = tmpBase();
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'w-bad', '--seed', '1', '--language', 'de');
  assert.equal(n.ok, false);
  assert.equal(n.error!.code, 'BAD_LANGUAGE');
});

test('CLI：--language 无值被拒（不再静默回落 zh）', () => {
  const base = tmpBase();
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'w-noval', '--seed', '1', '--language');
  assert.equal(n.ok, false);
  assert.equal(n.error!.code, 'BAD_LANGUAGE');
  assert.match(n.error!.message, /缺少值/);
});

test('向后兼容：剥离 state.json 的 language 字段后照常 status/verify，语言按 zh', () => {
  const base = tmpBase();
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'w-old', '--seed', '1', '--language', 'fr');
  assert.equal(n.ok, true, JSON.stringify(n.error));
  // 模拟旧存档：删除 language 字段并重算校验和
  const stateFile = path.join(base, 'saves', 'w-old', 'state.json');
  const raw = JSON.parse(readFileSync(stateFile, 'utf8'));
  delete raw.language;
  const content = JSON.stringify(raw, null, 2);
  writeFileSync(stateFile, content, 'utf8');
  writeFileSync(`${stateFile}.sha256`, sha256(content), 'utf8');

  const st = cli(base, 'status', '--world', 'w-old');
  assert.equal(st.ok, true, JSON.stringify(st.error));
  assert.equal(st.data.language, 'zh', '旧存档按默认中文处理');
  const v = cli(base, 'verify', '--world', 'w-old');
  assert.equal(v.ok, true, JSON.stringify(v.error));
});

test('CLI：中文/阿拉伯文/法文章节标题生成 ASCII 文件名', () => {
  const base = tmpBase();
  const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', 'w-slug', '--seed', '1');
  assert.equal(n.ok, true, JSON.stringify(n.error));
  const act = cli(base, 'act', '--id', 'rest');
  assert.equal(act.ok, true, JSON.stringify(act.error));

  const f1 = path.join(base, 'c1.md');
  writeFileSync(f1, '正文一。\n', 'utf8');
  const ch1 = cli(base, 'chapter-add', '--title', '潮声初闻', '--file', f1);
  assert.equal(ch1.ok, true, JSON.stringify(ch1.error));
  assert.match(ch1.data.chapter.file, /^001-[a-z0-9-]+\.md$/, '中文标题文件名为纯 ASCII');

  const f2 = path.join(base, 'c2.md');
  writeFileSync(f2, '正文二。\n', 'utf8');
  const ch2 = cli(base, 'chapter-add', '--title', 'الفصل الأول', '--file', f2);
  assert.equal(ch2.ok, true, JSON.stringify(ch2.error));
  assert.match(ch2.data.chapter.file, /^002-[a-z0-9-]+\.md$/, '阿拉伯文标题文件名为纯 ASCII');

  const f3 = path.join(base, 'c3.md');
  writeFileSync(f3, '正文三。\n', 'utf8');
  const ch3 = cli(base, 'chapter-add', '--title', "La Marée d'Écho", '--file', f3);
  assert.equal(ch3.ok, true, JSON.stringify(ch3.error));
  assert.equal(ch3.data.chapter.file, '003-la-maree-decho.md', '法语标题去音标后为纯 ASCII');

  const v = cli(base, 'verify', '--world', 'w-slug');
  assert.equal(v.ok, true, JSON.stringify(v.error));
});

// ---------------------------------------------------------------------------
// C1：引擎结算文案 i18n——en/fr/ar 完整一局后 novel.md 不得出现中文引擎模板
// ---------------------------------------------------------------------------

/** zh 引擎模板片段：非中文局 novel 中绝不允许出现。
 * 注意：echo-harbor 的 winLose.description 原文自带"胜利："字样，属于世界数据，
 * 故黑名单不含 '胜利：'/'失败：'。 */
const ZH_ENGINE_TEMPLATES = [
  '世界「', '开局。控制轴', '付出时间', '付出 ', '阶层跃迁', '新区域可达', '你得知',
  '世界状态变化', '维护「', '杠杆「', '改变了本次抽签的权重分布', '此结果不可逆',
  '扩张门槛已触发', '终局：', '现 ',
];
const CJK = /[\u4e00-\u9fff]/;

const LANG_NOVEL_MARKERS: Record<string, { paidTime: RegExp; tierUp: string }> = {
  en: { paidTime: /^- Turn \d+: Spent \d+ turns? of time$/m, tierUp: 'Tier ascension: ' },
  fr: { paidTime: /^- Tour \d+ : Temps dépensé : \d+ tours?$/m, tierUp: 'Ascension de palier : ' },
  ar: { paidTime: /^- الدور \d+: أنفقت \d+ من الأدوار$/m, tierUp: 'صعود الطبقة: ' },
};

for (const lang of ['en', 'fr', 'ar'] as const) {
  test(`C1：${lang} 完整一局，大事记引擎模板全为 ${lang}（无中文模板）`, () => {
    const base = tmpBase();
    const world = `w-${lang}`;
    const n = cli(base, 'new', '--blueprint', echoBlueprintPath, '--world', world, '--seed', String(GOLDEN_SEED), '--language', lang);
    assert.equal(n.ok, true, JSON.stringify(n.error));
    assert.equal(n.data.language, lang);

    let ended = false;
    for (const id of GOLDEN_SEQUENCE) {
      const res = cli(base, 'act', '--id', id);
      assert.equal(res.ok, true, `${id} 失败：${JSON.stringify(res.error)}`);
      if (res.data.ended) ended = true;
    }
    assert.ok(ended, '黄金序列必须达成胜利终局');

    const end = cli(base, 'end', '--reason', 'engine victory');
    assert.equal(end.ok, true, JSON.stringify(end.error));
    const novel = readFileSync(path.join(base, end.data.novel), 'utf8');

    // 1. 任何中文引擎模板片段都不得出现（世界数据里的中文专名不在此列）
    for (const frag of ZH_ENGINE_TEMPLATES) {
      assert.ok(!novel.includes(frag), `${lang} 局 novel 出现中文引擎模板片段 "${frag}"`);
    }

    // 2. 纯引擎文案行（不含世界数据）逐行断言无中文字符
    const marker = LANG_NOVEL_MARKERS[lang]!;
    const lines = novel.split('\n');
    const paidTimeLines = lines.filter((l) => /Spent \d+ turns? of time|Temps dépensé : \d+ tours?|أنفقت \d+ من الأدوار/.test(l));
    assert.ok(paidTimeLines.length > 0, '大事记必含时间成本行');
    for (const l of paidTimeLines) {
      assert.ok(!CJK.test(l), `时间成本行含中文字符：${l}`);
      assert.match(l, marker.paidTime, `时间成本行格式不符：${l}`);
    }

    // 3. 跃迁/胜利判定等引擎行存在且使用所选语言
    assert.ok(novel.includes(marker.tierUp), '大事记含本语言阶层跃迁行');

    // 4. 存档完整
    const v = cli(base, 'verify', '--world', world);
    assert.equal(v.ok, true, JSON.stringify(v.error));
  });
}
