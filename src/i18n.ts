/**
 * i18n（V1.1：开局选择语言）——四语文本表。
 *
 * 语言是**表现层元数据**：只影响 novel/chapter 固定文案与引擎结算产生的
 * history 文案呈现，不参与任何结算数值与确定性（引擎保持世界无关）。
 * 键缺失/语言未知时回退 zh。阿拉伯语直接输出 RTL 文本的纯 markdown。
 *
 * 两张表：
 * - NovelStrings：novel.md 合成的固定文案（书名页/目录/终章/大事记等）。
 * - EngineStrings：引擎结算写入 history.jsonl 的模板文案（开局/终局/跃迁/
 *   成本/维护/得知等），按存档语言在新结算时生成；已入库的旧条目不回溯
 *   改写（保持历史真实）。世界数据（资产名/行动名/描述等）仍按 Blueprint
 *   原文呈现，不属于引擎模板。
 */
import type { GameState, Language } from './types.ts';

export const SUPPORTED_LANGUAGES: readonly Language[] = ['zh', 'en', 'fr', 'ar'];
export const DEFAULT_LANGUAGE: Language = 'zh';

/** 类型守卫：值是否为受支持的语言代码。 */
export function isLanguage(value: unknown): value is Language {
  return typeof value === 'string' && (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}

/** 从存档读取语言；旧存档无 language 字段时按默认中文处理（向后兼容）。 */
export function languageOf(state: GameState): Language {
  return isLanguage(state.language) ? state.language : DEFAULT_LANGUAGE;
}

/** novel.md 合成的全部固定文案（书名页标签、目录、终章/大事记标题、章节标题等）。 */
export interface NovelStrings {
  worldFromPrompt(prompt: string): string;
  metaWorld(name: string): string;
  metaControlAxis(axis: string): string;
  metaSeed(seed: number): string;
  metaTurns(turns: number): string;
  metaFinalTier(tier: number): string;
  metaLeverage(name: string, uses: number): string;
  tocTitle: string;
  tocChapter(index: number, title: string, start: number, end: number): string;
  /** 目录中的终章行；index 为目录序号（章节数 + 1），保持 "N. 终章…" 旧格式。 */
  tocFinal(index: number, reason: string): string;
  chapterHeading(index: number, title: string): string;
  finalHeading(reason: string): string;
  keyMomentsTitle: string;
  chronicleTitle: string;
  historyLine(turn: number, text: string): string;
  footer: string;
}

/** 引擎结算写入 history 的模板文案（世界数据按 Blueprint 原文，不在此表）。 */
export interface EngineStrings {
  openingEntry(world: string, controlAxis: string): string;
  endingEntry(reason: string): string;
  winReason(description: string): string;
  loseReason(description: string): string;
  tierUp(name: string, description: string): string;
  regionUnlocked(name: string): string;
  paidTime(turns: number): string;
  paidAsset(name: string, cost: number): string;
  /** signedDelta 形如 "+2" / "-1"。 */
  assetDelta(name: string, signedDelta: string, now: number): string;
  learnedFact(description: string): string;
  flagSet(flag: string): string;
  flagCleared(flag: string): string;
  maintenance(assetName: string, payAssetName: string, cost: number): string;
  leverageApplied(leverageName: string): string;
  outcome(actionName: string, outcomeDescription: string): string;
  irreversible: string;
  expansionTriggered(ruleId: string, description: string): string;
  expansionMaterialized(ruleId: string, factId: string, description: string): string;
}

export const novelStrings: Record<Language, NovelStrings> = {
  zh: {
    worldFromPrompt: (p) => `> 世界由一句话开始：「${p}」`,
    metaWorld: (v) => `- 世界：${v}`,
    metaControlAxis: (v) => `- 控制轴：${v}`,
    metaSeed: (v) => `- 种子：${v}`,
    metaTurns: (v) => `- 回合数：${v}`,
    metaFinalTier: (v) => `- 最终阶层：${v}`,
    metaLeverage: (name, uses) => `- 杠杆：${name}（使用 ${uses} 次）`,
    tocTitle: '## 目录',
    tocChapter: (i, t, s, e) => `${i}. ${t}（回合 ${s}–${e}）`,
    tocFinal: (i, reason) => `${i}. 终章：${reason}`,
    chapterHeading: (i, t) => `## 第${i}章 ${t}`,
    finalHeading: (reason) => `## 终章 ${reason}`,
    keyMomentsTitle: '### 关键时刻',
    chronicleTitle: '### 大事记',
    historyLine: (turn, text) => `- 回合 ${turn}：${text}`,
    footer: '*本作由确定性引擎结算、由叙事者书写；删除文字不能删除因果。*',
  },
  en: {
    worldFromPrompt: (p) => `> This world began with a single sentence: "${p}"`,
    metaWorld: (v) => `- World: ${v}`,
    metaControlAxis: (v) => `- Control axis: ${v}`,
    metaSeed: (v) => `- Seed: ${v}`,
    metaTurns: (v) => `- Turns: ${v}`,
    metaFinalTier: (v) => `- Final tier: ${v}`,
    metaLeverage: (name, uses) => `- Leverage: ${name} (used ${uses} time${uses === 1 ? '' : 's'})`,
    tocTitle: '## Contents',
    tocChapter: (i, t, s, e) => `${i}. ${t} (turns ${s}–${e})`,
    tocFinal: (i, reason) => `${i}. Final Chapter: ${reason}`,
    chapterHeading: (i, t) => `## Chapter ${i}: ${t}`,
    finalHeading: (reason) => `## Final Chapter: ${reason}`,
    keyMomentsTitle: '### Key Moments',
    chronicleTitle: '### Chronicle',
    historyLine: (turn, text) => `- Turn ${turn}: ${text}`,
    footer: '*Settled by a deterministic engine, written by the narrator; deleting words cannot delete causality.*',
  },
  fr: {
    worldFromPrompt: (p) => `> Le monde a commencé par une seule phrase : « ${p} »`,
    metaWorld: (v) => `- Monde : ${v}`,
    metaControlAxis: (v) => `- Axe de contrôle : ${v}`,
    metaSeed: (v) => `- Graine : ${v}`,
    metaTurns: (v) => `- Tours : ${v}`,
    metaFinalTier: (v) => `- Palier final : ${v}`,
    metaLeverage: (name, uses) => `- Levier : ${name} (utilisé ${uses} fois)`,
    tocTitle: '## Sommaire',
    tocChapter: (i, t, s, e) => `${i}. ${t} (tours ${s}–${e})`,
    tocFinal: (i, reason) => `${i}. Chapitre final : ${reason}`,
    chapterHeading: (i, t) => `## Chapitre ${i} : ${t}`,
    finalHeading: (reason) => `## Chapitre final : ${reason}`,
    keyMomentsTitle: '### Moments clés',
    chronicleTitle: '### Chronique',
    historyLine: (turn, text) => `- Tour ${turn} : ${text}`,
    footer: '*Résolu par un moteur déterministe, écrit par le narrateur ; effacer les mots n\u2019efface pas la causalité.*',
  },
  ar: {
    worldFromPrompt: (p) => `> بدأ العالم بجملة واحدة: «${p}»`,
    metaWorld: (v) => `- العالم: ${v}`,
    metaControlAxis: (v) => `- محور التحكم: ${v}`,
    metaSeed: (v) => `- البذرة: ${v}`,
    metaTurns: (v) => `- عدد الأدوار: ${v}`,
    metaFinalTier: (v) => `- الطبقة النهائية: ${v}`,
    metaLeverage: (name, uses) => `- الرافعة: ${name} (استُخدمت ${uses} مرة)`,
    tocTitle: '## الفهرس',
    tocChapter: (i, t, s, e) => `${i}. ${t} (الأدوار ${s}–${e})`,
    tocFinal: (i, reason) => `${i}. الفصل الختامي: ${reason}`,
    chapterHeading: (i, t) => `## الفصل ${i}: ${t}`,
    finalHeading: (reason) => `## الفصل الختامي: ${reason}`,
    keyMomentsTitle: '### لحظات فارقة',
    chronicleTitle: '### سجل الأحداث',
    historyLine: (turn, text) => `- الدور ${turn}: ${text}`,
    footer: '*حُسمت الأحداث بواسطة محرك حتمي، وكتبها الراوي؛ حذف الكلمات لا يحذف السببية.*',
  },
};

export const engineStrings: Record<Language, EngineStrings> = {
  zh: {
    openingEntry: (w, a) => `世界「${w}」开局。控制轴：${a}。`,
    endingEntry: (r) => `终局：${r}`,
    winReason: (d) => `胜利：${d}`,
    loseReason: (d) => `失败：${d}`,
    tierUp: (n, d) => `阶层跃迁：${n}——${d}`,
    regionUnlocked: (n) => `新区域可达：${n}`,
    paidTime: (n) => `付出时间 ${n} 回合`,
    paidAsset: (n, c) => `付出 ${n} -${c}`,
    assetDelta: (n, s, now) => `${n} ${s}（现 ${now}）`,
    learnedFact: (d) => `你得知：${d}`,
    flagSet: (f) => `世界状态变化：${f}`,
    flagCleared: (f) => `世界状态变化：${f} 结束`,
    maintenance: (n, p, c) => `维护「${n}」消耗 ${p} -${c}`,
    leverageApplied: (n) => `杠杆「${n}」改变了本次抽签的权重分布`,
    outcome: (a, o) => `${a}：${o}`,
    irreversible: '此结果不可逆（永久后果，可追溯）',
    expansionTriggered: (r, d) => `扩张门槛已触发（${r}）：${d}——候选内容须经校验后方可物化`,
    expansionMaterialized: (r, id, d) => `Lazy Expansion 物化（规则 ${r}）：新事实「${id}」成为世界事实——${d}`,
  },
  en: {
    openingEntry: (w, a) => `World "${w}" begins. Control axis: ${a}.`,
    endingEntry: (r) => `Ending: ${r}`,
    winReason: (d) => `Victory: ${d}`,
    loseReason: (d) => `Defeat: ${d}`,
    tierUp: (n, d) => `Tier ascension: ${n} — ${d}`,
    regionUnlocked: (n) => `New region reachable: ${n}`,
    paidTime: (n) => `Spent ${n} turn${n === 1 ? '' : 's'} of time`,
    paidAsset: (n, c) => `Paid ${n} -${c}`,
    assetDelta: (n, s, now) => `${n} ${s} (now ${now})`,
    learnedFact: (d) => `You learned: ${d}`,
    flagSet: (f) => `World state changed: ${f}`,
    flagCleared: (f) => `World state changed: ${f} ended`,
    maintenance: (n, p, c) => `Maintaining "${n}" costs ${p} -${c}`,
    leverageApplied: (n) => `Leverage "${n}" altered the weight distribution of this draw`,
    outcome: (a, o) => `${a}: ${o}`,
    irreversible: 'This outcome is irreversible (permanent and traceable)',
    expansionTriggered: (r, d) => `Expansion threshold triggered (${r}): ${d} — candidates must pass validation before materializing`,
    expansionMaterialized: (r, id, d) => `Lazy Expansion materialized (rule ${r}): new fact "${id}" became a world fact — ${d}`,
  },
  fr: {
    openingEntry: (w, a) => `Le monde « ${w} » commence. Axe de contrôle : ${a}.`,
    endingEntry: (r) => `Fin : ${r}`,
    winReason: (d) => `Victoire : ${d}`,
    loseReason: (d) => `Défaite : ${d}`,
    tierUp: (n, d) => `Ascension de palier : ${n} — ${d}`,
    regionUnlocked: (n) => `Nouvelle région accessible : ${n}`,
    paidTime: (n) => `Temps dépensé : ${n} tour${n === 1 ? '' : 's'}`,
    paidAsset: (n, c) => `${n} payé -${c}`,
    assetDelta: (n, s, now) => `${n} ${s} (maintenant ${now})`,
    learnedFact: (d) => `Vous apprenez : ${d}`,
    flagSet: (f) => `L'état du monde change : ${f}`,
    flagCleared: (f) => `L'état du monde change : ${f} prend fin`,
    maintenance: (n, p, c) => `Entretien de « ${n} » : ${p} -${c}`,
    leverageApplied: (n) => `Le levier « ${n} » a modifié la distribution des poids de ce tirage`,
    outcome: (a, o) => `${a} : ${o}`,
    irreversible: 'Ce résultat est irréversible (conséquence permanente et traçable)',
    expansionTriggered: (r, d) => `Seuil d'expansion atteint (${r}) : ${d} — les candidats doivent être validés avant matérialisation`,
    expansionMaterialized: (r, id, d) => `Lazy Expansion matérialisée (règle ${r}) : le fait « ${id} » est devenu un fait du monde — ${d}`,
  },
  ar: {
    openingEntry: (w, a) => `بدأ العالم «${w}». محور التحكم: ${a}.`,
    endingEntry: (r) => `النهاية: ${r}`,
    winReason: (d) => `النصر: ${d}`,
    loseReason: (d) => `الهزيمة: ${d}`,
    tierUp: (n, d) => `صعود الطبقة: ${n} — ${d}`,
    regionUnlocked: (n) => `منطقة جديدة يمكن بلوغها: ${n}`,
    paidTime: (n) => `أنفقت ${n} من الأدوار`,
    paidAsset: (n, c) => `دفعت ${n} -${c}`,
    assetDelta: (n, s, now) => `${n} ${s} (الآن ${now})`,
    learnedFact: (d) => `علمتَ أن: ${d}`,
    flagSet: (f) => `تغيّرت حالة العالم: ${f}`,
    flagCleared: (f) => `تغيّرت حالة العالم: انتهى ${f}`,
    maintenance: (n, p, c) => `صيانة «${n}» تستهلك ${p} -${c}`,
    leverageApplied: (n) => `غيّرت الرافعة «${n}» توزيع أوزان هذه القرعة`,
    outcome: (a, o) => `${a}: ${o}`,
    irreversible: 'هذه النتيجة لا رجعة فيها (عاقبة دائمة وقابلة للتتبع)',
    expansionTriggered: (r, d) => `تفعّل عتبة التوسع (${r}): ${d} — يجب التحقق من المرشحين قبل تجسيدهم`,
    expansionMaterialized: (r, id, d) => `تجسيد التوسع الكسول (القاعدة ${r}): أصبحت الحقيقة «${id}» حقيقة عالمية — ${d}`,
  },
};

/** 取某语言的 novel 文案表；未知语言回退 zh（键缺失回退策略）。 */
export function getNovelStrings(language: unknown): NovelStrings {
  return novelStrings[isLanguage(language) ? language : DEFAULT_LANGUAGE];
}

/** 取某语言的引擎文案表；未知语言回退 zh（键缺失回退策略）。 */
export function getEngineStrings(language: unknown): EngineStrings {
  return engineStrings[isLanguage(language) ? language : DEFAULT_LANGUAGE];
}
