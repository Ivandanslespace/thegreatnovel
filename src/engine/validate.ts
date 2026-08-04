// WorldProposal 手写校验（零运行时依赖，不引 zod）。宪法 §3.1：杠杆四要素缺一即错；
// §1.1：失败可学习——每条错误都是给 Agent 的修复指南（哪个字段、违反什么、建议修法）。
// 错误文案按 proposal.language 本地化，缺失/非法语言回退 zh。
import type { ActionDef, Language, RiskLevel, WindowKind } from './types.ts';
import { MAINTENANCE_RESOURCE, MAX_TIER, TIER_GATES } from './balance.ts';

export const LANGUAGES: readonly Language[] = ['zh', 'en', 'fr', 'ar'];

/** 主角非对称杠杆（宪法 §3.1）：causalChain/cost/whyUnreplicable/failureMode 四要素 + 名称。 */
export interface LeverageSpec {
  name: string;
  causalChain: string;
  cost: string;
  whyUnreplicable: string;
  failureMode: string;
}

export interface NpcSpec {
  id: string;
  name: string;
  goal: string;
  resources: Record<string, number>;
  power: number;
  personality: string;
}

export interface TierGateSpec {
  minAssetLevel: number;
  minKnowledge: number;
  minStanding: number;
}

/** Tier 2/3 宏观锚点：仅存锚点描述与约束，不预展开（宪法 §7）。 */
export interface ExpansionAnchorSpec {
  id: string;
  tier: number;
  description: string;
  constraint: string;
}

export interface WorldProposal {
  worldName: string;
  language: Language;
  /** 失控背景：控制缺口的来源（核心循环起点）。 */
  background: string;
  rulesExplicit: string[];
  rulesHidden: string[];
  resources: string[];
  actions: ActionDef[];
  leverage: LeverageSpec;
  npcs: NpcSpec[];
  tierGates: TierGateSpec[];
  expansionAnchors: ExpansionAnchorSpec[];
}

export interface ProposalIssue {
  /** JSON 字段路径，如 'leverage.failureMode' 或 'actions[2].effects[0].verb' */
  field: string;
  /** 机器可读错误类别 */
  code: string;
  /** 违反了什么（本地化） */
  message: string;
  /** 建议修法（本地化） */
  fix: string;
}

export type ValidateResult =
  | { ok: true; proposal: WorldProposal }
  | { ok: false; issues: ProposalIssue[] };

// ---- 本地化修复指南文案（四语） ----

interface Kit {
  notObject: { message: string; fix: string };
  required: (f: string) => { message: string; fix: string };
  wrongType: (f: string, exp: string) => { message: string; fix: string };
  empty: (f: string) => { message: string; fix: string };
  tooFew: (f: string, min: number, actual: number) => { message: string; fix: string };
  tooMany: (f: string, max: number, actual: number) => { message: string; fix: string };
  enumValue: (f: string, allowed: string) => { message: string; fix: string };
  duplicate: (f: string, v: string) => { message: string; fix: string };
  ref: (f: string, v: string, target: string) => { message: string; fix: string };
  range: (f: string, lo: number, hi: number) => { message: string; fix: string };
  leverage: (f: string, desc: string) => { message: string; fix: string };
  gateMismatch: (i: number, expected: string) => { message: string; fix: string };
  anchorMissing: (tier: number) => { message: string; fix: string };
  noEffects: (f: string) => { message: string; fix: string };
}

const KITS: Record<Language, Kit> = {
  zh: {
    notObject: {
      message: 'proposal 不是 JSON 对象',
      fix: '按 worlds/_template/proposal.template.json 的结构提交完整 JSON 对象',
    },
    required: (f) => ({ message: `缺少必填字段 ${f}`, fix: `在 proposal 中补充字段 "${f}"` }),
    wrongType: (f, exp) => ({ message: `${f} 类型错误`, fix: `将 ${f} 改为 ${exp} 类型` }),
    empty: (f) => ({ message: `${f} 为空`, fix: `为 ${f} 填写非空内容` }),
    tooFew: (f, min, actual) => ({
      message: `${f} 数量不足（最少 ${min}，当前 ${actual}）`,
      fix: `为 ${f} 再补充至少 ${min - actual} 项`,
    }),
    tooMany: (f, max, actual) => ({
      message: `${f} 数量超限（最多 ${max}，当前 ${actual}）`,
      fix: `精简 ${f} 至多 ${max} 项；稀缺来自约束而非数量（宪法 §6）`,
    }),
    enumValue: (f, allowed) => ({ message: `${f} 取值非法`, fix: `${f} 只能是以下之一：${allowed}` }),
    duplicate: (f, v) => ({ message: `${f} 存在重复值 "${v}"`, fix: `修改重复项，保证 ${f} 唯一` }),
    ref: (f, v, target) => ({
      message: `${f} 引用了未声明的 "${v}"`,
      fix: `先在 ${target} 中声明 "${v}"，或修正 ${f} 的引用`,
    }),
    range: (f, lo, hi) => ({ message: `${f} 超出允许范围`, fix: `${f} 应在 ${lo} 到 ${hi} 之间` }),
    leverage: (f, desc) => ({
      message: `杠杆缺少宪法 §3.1 要素 "${f}"`,
      fix: `说明 ${desc}；一段“主角很特殊”的旁白不算充分证明`,
    }),
    gateMismatch: (i, expected) => ({
      message: `tierGates[${i}] 与引擎固定门槛不一致`,
      fix: `引擎跃迁门槛由 balance.ts 的 TIER_GATES 决定，请把 tierGates[${i}] 改为 ${expected}`,
    }),
    anchorMissing: (tier) => ({
      message: `缺少 tier ${tier} 的宏观锚点`,
      fix: `在 expansionAnchors 中补充一项 {"tier": ${tier}, "id", "description", "constraint"}；只存锚点与约束，不预展开（宪法 §7）`,
    }),
    noEffects: (f) => ({
      message: `${f} 没有任何效果`,
      fix: `为 ${f} 至少添加一个固定动词效果（resource/knowledge/assetInvest/relation/windowOpen/unlock）`,
    }),
  },
  en: {
    notObject: {
      message: 'proposal is not a JSON object',
      fix: 'Submit a full JSON object following worlds/_template/proposal.template.json',
    },
    required: (f) => ({ message: `missing required field ${f}`, fix: `Add field "${f}" to the proposal` }),
    wrongType: (f, exp) => ({ message: `${f} has wrong type`, fix: `Change ${f} to type ${exp}` }),
    empty: (f) => ({ message: `${f} is empty`, fix: `Fill ${f} with non-empty content` }),
    tooFew: (f, min, actual) => ({
      message: `${f} has too few items (min ${min}, got ${actual})`,
      fix: `Add at least ${min - actual} more item(s) to ${f}`,
    }),
    tooMany: (f, max, actual) => ({
      message: `${f} has too many items (max ${max}, got ${actual})`,
      fix: `Trim ${f} to at most ${max}; scarcity comes from constraints, not volume (Constitution §6)`,
    }),
    enumValue: (f, allowed) => ({ message: `${f} has invalid value`, fix: `${f} must be one of: ${allowed}` }),
    duplicate: (f, v) => ({ message: `${f} contains duplicate "${v}"`, fix: `Rename the duplicate so ${f} stays unique` }),
    ref: (f, v, target) => ({
      message: `${f} references undeclared "${v}"`,
      fix: `Declare "${v}" in ${target} first, or fix the reference in ${f}`,
    }),
    range: (f, lo, hi) => ({ message: `${f} out of range`, fix: `${f} must be between ${lo} and ${hi}` }),
    leverage: (f, desc) => ({
      message: `leverage misses Constitution §3.1 element "${f}"`,
      fix: `Explain ${desc}; a "the protagonist is special" narration is not sufficient proof`,
    }),
    gateMismatch: (i, expected) => ({
      message: `tierGates[${i}] does not match the engine-fixed gate`,
      fix: `Tier gates are fixed by balance.ts TIER_GATES; set tierGates[${i}] to ${expected}`,
    }),
    anchorMissing: (tier) => ({
      message: `missing macro anchor for tier ${tier}`,
      fix: `Add an entry {"tier": ${tier}, "id", "description", "constraint"} to expansionAnchors; store anchors and constraints only, never pre-expand (Constitution §7)`,
    }),
    noEffects: (f) => ({
      message: `${f} has no effects`,
      fix: `Add at least one fixed-verb effect to ${f} (resource/knowledge/assetInvest/relation/windowOpen/unlock)`,
    }),
  },
  fr: {
    notObject: {
      message: 'le proposal n’est pas un objet JSON',
      fix: 'Soumettez un objet JSON complet selon worlds/_template/proposal.template.json',
    },
    required: (f) => ({ message: `champ requis ${f} manquant`, fix: `Ajoutez le champ "${f}" au proposal` }),
    wrongType: (f, exp) => ({ message: `${f} a un type incorrect`, fix: `Changez ${f} en type ${exp}` }),
    empty: (f) => ({ message: `${f} est vide`, fix: `Remplissez ${f} avec un contenu non vide` }),
    tooFew: (f, min, actual) => ({
      message: `${f} : pas assez d’éléments (min ${min}, actuel ${actual})`,
      fix: `Ajoutez au moins ${min - actual} élément(s) à ${f}`,
    }),
    tooMany: (f, max, actual) => ({
      message: `${f} : trop d’éléments (max ${max}, actuel ${actual})`,
      fix: `Réduisez ${f} à au plus ${max} ; la rareté vient des contraintes (Constitution §6)`,
    }),
    enumValue: (f, allowed) => ({ message: `${f} a une valeur invalide`, fix: `${f} doit être l’un de : ${allowed}` }),
    duplicate: (f, v) => ({ message: `${f} contient un doublon "${v}"`, fix: `Renommez le doublon pour garder ${f} unique` }),
    ref: (f, v, target) => ({
      message: `${f} référence "${v}" non déclaré`,
      fix: `Déclarez d’abord "${v}" dans ${target}, ou corrigez la référence dans ${f}`,
    }),
    range: (f, lo, hi) => ({ message: `${f} hors limites`, fix: `${f} doit être entre ${lo} et ${hi}` }),
    leverage: (f, desc) => ({
      message: `le levier omet l’élément §3.1 "${f}"`,
      fix: `Expliquez ${desc} ; une narration « le héros est spécial » ne suffit pas`,
    }),
    gateMismatch: (i, expected) => ({
      message: `tierGates[${i}] ne correspond pas au seuil fixe du moteur`,
      fix: `Les seuils sont fixés par balance.ts TIER_GATES ; mettez tierGates[${i}] à ${expected}`,
    }),
    anchorMissing: (tier) => ({
      message: `ancre macro manquante pour le rang ${tier}`,
      fix: `Ajoutez {"tier": ${tier}, "id", "description", "constraint"} à expansionAnchors ; ancres et contraintes seulement (Constitution §7)`,
    }),
    noEffects: (f) => ({
      message: `${f} n’a aucun effet`,
      fix: `Ajoutez au moins un effet à verbe fixe dans ${f} (resource/knowledge/assetInvest/relation/windowOpen/unlock)`,
    }),
  },
  ar: {
    notObject: {
      message: 'الاقتراح ليس كائن JSON',
      fix: 'قدّم كائن JSON كاملاً وفق worlds/_template/proposal.template.json',
    },
    required: (f) => ({ message: `الحقل الإلزامي ${f} مفقود`, fix: `أضف الحقل "${f}" إلى الاقتراح` }),
    wrongType: (f, exp) => ({ message: `نوع ${f} خاطئ`, fix: `غيّر ${f} إلى النوع ${exp}` }),
    empty: (f) => ({ message: `${f} فارغ`, fix: `املأ ${f} بمحتوى غير فارغ` }),
    tooFew: (f, min, actual) => ({
      message: `${f} قليل العناصر (الحد ${min}، الحالي ${actual})`,
      fix: `أضف ما لا يقل عن ${min - actual} عنصرًا إلى ${f}`,
    }),
    tooMany: (f, max, actual) => ({
      message: `${f} كثير العناصر (الحد الأقصى ${max}، الحالي ${actual})`,
      fix: `قلّص ${f} إلى ${max} كحد أقصى؛ الندرة تأتي من القيود (الدستور §6)`,
    }),
    enumValue: (f, allowed) => ({ message: `قيمة ${f} غير صالحة`, fix: `يجب أن يكون ${f} أحد: ${allowed}` }),
    duplicate: (f, v) => ({ message: `${f} يحتوي تكرارًا "${v}"`, fix: `عدّل المكرر ليبقى ${f} فريدًا` }),
    ref: (f, v, target) => ({
      message: `${f} يشير إلى "${v}" غير المعلن`,
      fix: `أعلن "${v}" في ${target} أولاً، أو صحّح المرجع في ${f}`,
    }),
    range: (f, lo, hi) => ({ message: `${f} خارج النطاق`, fix: `يجب أن يكون ${f} بين ${lo} و ${hi}` }),
    leverage: (f, desc) => ({
      message: `الرافعة تفتقد عنصر الدستور §3.1 "${f}"`,
      fix: `اشرح ${desc}؛ سردية "البطل مميز" ليست دليلاً كافيًا`,
    }),
    gateMismatch: (i, expected) => ({
      message: `tierGates[${i}] لا يطابق عتبة المحرك الثابتة`,
      fix: `العتبات يحددها balance.ts TIER_GATES؛ اجعل tierGates[${i}] يساوي ${expected}`,
    }),
    anchorMissing: (tier) => ({
      message: `مرساة كلية مفقودة للطبقة ${tier}`,
      fix: `أضف {"tier": ${tier}, "id", "description", "constraint"} إلى expansionAnchors؛ مراسٍ وقيود فقط دون توسيع مسبق (الدستور §7)`,
    }),
    noEffects: (f) => ({
      message: `${f} بلا تأثيرات`,
      fix: `أضف تأثيرًا واحدًا على الأقل بأفعال ثابتة في ${f} (resource/knowledge/assetInvest/relation/windowOpen/unlock)`,
    }),
  },
};

/** 杠杆四要素的补充说明（按语言）。 */
const LEVERAGE_DESC: Record<Language, Record<string, string>> = {
  zh: {
    name: '杠杆的名称',
    causalChain: '它改变了哪条因果链',
    cost: '主角需要付出什么',
    whyUnreplicable: '普通人为什么难以复制',
    failureMode: '失败怎样发生、玩家怎样学会更好地使用它',
  },
  en: {
    name: 'the leverage name',
    causalChain: 'which causal chain it changes',
    cost: 'what the protagonist must pay',
    whyUnreplicable: 'why ordinary people cannot replicate it',
    failureMode: 'how it fails and how the player learns to use it better',
  },
  fr: {
    name: 'le nom du levier',
    causalChain: 'quelle chaîne causale il modifie',
    cost: 'ce que le protagoniste doit payer',
    whyUnreplicable: 'pourquoi les autres ne peuvent pas le reproduire',
    failureMode: 'comment il échoue et comment le joueur apprend à mieux s’en servir',
  },
  ar: {
    name: 'اسم الرافعة',
    causalChain: 'أي سلسلة سببية تغيّر',
    cost: 'ما الذي يدفعه البطل',
    whyUnreplicable: 'لماذا يصعب على الآخرين تكرارها',
    failureMode: 'كيف تفشل وكيف يتعلم اللاعب استخدامها أفضل',
  },
};

// ---- 类型守卫 ----

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function isNonEmptyString(v: unknown): v is string {
  return typeof v === 'string' && v.trim().length > 0;
}

function isInt(v: unknown): v is number {
  return typeof v === 'number' && Number.isInteger(v);
}

function isLang(v: unknown): v is Language {
  return typeof v === 'string' && (LANGUAGES as readonly string[]).includes(v);
}

const ACTION_ID_RE = /^[a-z][a-z0-9_-]*$/;
/** worldName 字符集：禁止路径分隔符与控制字符（防路径穿越，落盘文件名安全）。 */
const WORLD_NAME_RE = /^[^\u0000-\u001f/\\]+$/;
const WORLD_NAME_MAX = 60;
const RISK_LEVELS: readonly RiskLevel[] = ['low', 'medium', 'high'];
const WINDOW_KINDS: readonly WindowKind[] = ['supply', 'threat', 'opportunity'];
const VERBS = ['resource', 'knowledge', 'assetInvest', 'relation', 'windowOpen', 'unlock'] as const;

/**
 * 校验 WorldProposal。返回结构化错误列表；每条 message/fix 已按 proposal.language 本地化。
 * 以 '_' 开头的键（如模板里的 _comment）一律忽略。
 */
export function validateProposal(raw: unknown): ValidateResult {
  const issues: ProposalIssue[] = [];
  const lang: Language = isObj(raw) && isLang(raw.language) ? raw.language : 'zh';
  const kit = KITS[lang];
  const push = (field: string, code: string, text: { message: string; fix: string }) => {
    issues.push({ field, code, message: text.message, fix: text.fix });
  };

  if (!isObj(raw)) {
    return { ok: false, issues: [{ field: '(root)', code: 'notObject', ...kit.notObject }] };
  }

  // worldName / language / background
  if (!isNonEmptyString(raw.worldName)) {
    push('worldName', raw.worldName === undefined ? 'required' : 'empty', raw.worldName === undefined ? kit.required('worldName') : kit.empty('worldName'));
  } else if (raw.worldName.length > WORLD_NAME_MAX || raw.worldName.includes('..') || !WORLD_NAME_RE.test(raw.worldName)) {
    // 防路径穿越：worldName 直接参与小说/导出文件名（宪法 §12 存档完整性）
    push('worldName', 'format', kit.enumValue('worldName', `≤${WORLD_NAME_MAX} chars, no "/" "\\" ".." or control chars`));
  }
  if (!isLang(raw.language)) {
    push('language', 'enum', kit.enumValue('language', LANGUAGES.join(' | ')));
  }
  if (!isNonEmptyString(raw.background)) {
    push('background', raw.background === undefined ? 'required' : 'empty', raw.background === undefined ? kit.required('background') : kit.empty('background'));
  }

  // rulesExplicit ≥3 / rulesHidden ≥1
  const rulesExplicitOk = checkStringArray(raw.rulesExplicit, 'rulesExplicit', 3, Infinity);
  const rulesHiddenOk = checkStringArray(raw.rulesHidden, 'rulesHidden', 1, Infinity);

  // resources ≤5，含维护资源
  const resources: string[] = [];
  if (!Array.isArray(raw.resources)) {
    push('resources', 'required', kit.required('resources'));
  } else {
    if (raw.resources.length < 1) push('resources', 'tooFew', kit.tooFew('resources', 1, raw.resources.length));
    if (raw.resources.length > 5) push('resources', 'tooMany', kit.tooMany('resources', 5, raw.resources.length));
    for (let i = 0; i < raw.resources.length; i++) {
      const r = raw.resources[i];
      if (!isNonEmptyString(r)) {
        push(`resources[${i}]`, 'type', kit.wrongType(`resources[${i}]`, 'string'));
        continue;
      }
      if (resources.includes(r)) push(`resources[${i}]`, 'duplicate', kit.duplicate('resources', r));
      else resources.push(r);
    }
    if (!resources.includes(MAINTENANCE_RESOURCE)) {
      push('resources', 'reference', kit.ref('resources', MAINTENANCE_RESOURCE, `"${MAINTENANCE_RESOURCE}" (${lang === 'zh' ? '引擎维护成本固定资源' : 'engine maintenance resource'})`));
    }
  }

  // npcs 5–8
  const npcIds: string[] = [];
  if (!Array.isArray(raw.npcs)) {
    push('npcs', 'required', kit.required('npcs'));
  } else {
    if (raw.npcs.length < 5) push('npcs', 'tooFew', kit.tooFew('npcs', 5, raw.npcs.length));
    if (raw.npcs.length > 8) push('npcs', 'tooMany', kit.tooMany('npcs', 8, raw.npcs.length));
    for (let i = 0; i < raw.npcs.length; i++) {
      const n = raw.npcs[i];
      const f = `npcs[${i}]`;
      if (!isObj(n)) {
        push(f, 'type', kit.wrongType(f, 'object'));
        continue;
      }
      if (!isNonEmptyString(n.id)) push(`${f}.id`, 'required', kit.required(`${f}.id`));
      else if (npcIds.includes(n.id)) push(`${f}.id`, 'duplicate', kit.duplicate('npcs[].id', n.id));
      else npcIds.push(n.id);
      if (!isNonEmptyString(n.name)) push(`${f}.name`, 'required', kit.required(`${f}.name`));
      if (!isNonEmptyString(n.personality)) push(`${f}.personality`, 'required', kit.required(`${f}.personality`));
      if (!isNonEmptyString(n.goal)) push(`${f}.goal`, 'required', kit.required(`${f}.goal`));
      else if (resources.length > 0 && !resources.includes(n.goal)) push(`${f}.goal`, 'reference', kit.ref(`${f}.goal`, n.goal, 'resources'));
      if (!isInt(n.power) || n.power < 1) push(`${f}.power`, 'range', kit.range(`${f}.power`, 1, 99));
      if (n.resources !== undefined) {
        if (!isObj(n.resources)) push(`${f}.resources`, 'type', kit.wrongType(`${f}.resources`, 'object'));
        else {
          for (const [k, v] of Object.entries(n.resources)) {
            if (resources.length > 0 && !resources.includes(k)) push(`${f}.resources.${k}`, 'reference', kit.ref(`${f}.resources`, k, 'resources'));
            if (typeof v !== 'number' || v < 0) push(`${f}.resources.${k}`, 'range', kit.range(`${f}.resources.${k}`, 0, 9999));
          }
        }
      }
    }
  }

  // actions ≤10，effects 限固定动词表
  if (!Array.isArray(raw.actions)) {
    push('actions', 'required', kit.required('actions'));
  } else {
    if (raw.actions.length < 1) push('actions', 'tooFew', kit.tooFew('actions', 1, raw.actions.length));
    if (raw.actions.length > 10) push('actions', 'tooMany', kit.tooMany('actions', 10, raw.actions.length));
    const actionIds: string[] = [];
    for (let i = 0; i < raw.actions.length; i++) {
      const a = raw.actions[i];
      const f = `actions[${i}]`;
      if (!isObj(a)) {
        push(f, 'type', kit.wrongType(f, 'object'));
        continue;
      }
      if (!isNonEmptyString(a.id)) push(`${f}.id`, 'required', kit.required(`${f}.id`));
      else {
        if (!ACTION_ID_RE.test(a.id) || a.id.includes(':')) push(`${f}.id`, 'format', kit.enumValue(`${f}.id`, '^[a-z][a-z0-9_-]*$'));
        if (actionIds.includes(a.id)) push(`${f}.id`, 'duplicate', kit.duplicate('actions[].id', a.id));
        else actionIds.push(a.id);
      }
      if (!isNonEmptyString(a.label)) push(`${f}.label`, 'required', kit.required(`${f}.label`));
      if (!isInt(a.timeCost) || a.timeCost < 1) push(`${f}.timeCost`, 'range', kit.range(`${f}.timeCost`, 1, 99));

      // requires
      if (a.requires !== undefined) {
        if (!isObj(a.requires)) push(`${f}.requires`, 'type', kit.wrongType(`${f}.requires`, 'object'));
        else {
          const req = a.requires;
          if (req.knowledge !== undefined && !Array.isArray(req.knowledge)) push(`${f}.requires.knowledge`, 'type', kit.wrongType(`${f}.requires.knowledge`, 'string[]'));
          if (req.unlocks !== undefined) {
            if (!Array.isArray(req.unlocks)) push(`${f}.requires.unlocks`, 'type', kit.wrongType(`${f}.requires.unlocks`, 'string[]'));
            else req.unlocks.forEach((u: unknown, i: number) => {
              if (!isNonEmptyString(u)) push(`${f}.requires.unlocks[${i}]`, 'type', kit.wrongType(`${f}.requires.unlocks[${i}]`, 'string'));
            });
          }
          if (req.tier !== undefined && (!isInt(req.tier) || req.tier < 0 || req.tier > MAX_TIER)) push(`${f}.requires.tier`, 'range', kit.range(`${f}.requires.tier`, 0, MAX_TIER));
          if (req.assetLevel !== undefined && (!isInt(req.assetLevel) || req.assetLevel < 0)) push(`${f}.requires.assetLevel`, 'range', kit.range(`${f}.requires.assetLevel`, 0, 99));
          if (req.resources !== undefined) {
            if (!isObj(req.resources)) push(`${f}.requires.resources`, 'type', kit.wrongType(`${f}.requires.resources`, 'object'));
            else {
              for (const [k, v] of Object.entries(req.resources)) {
                if (resources.length > 0 && !resources.includes(k)) push(`${f}.requires.resources.${k}`, 'reference', kit.ref(`${f}.requires.resources`, k, 'resources'));
                if (typeof v !== 'number' || v < 0) push(`${f}.requires.resources.${k}`, 'range', kit.range(`${f}.requires.resources.${k}`, 0, 9999));
              }
            }
          }
        }
      }

      // costs
      if (a.costs !== undefined) {
        if (!isObj(a.costs)) push(`${f}.costs`, 'type', kit.wrongType(`${f}.costs`, 'object'));
        else {
          const costs = a.costs;
          if (costs.focus !== undefined && (!isInt(costs.focus) || costs.focus < 0)) push(`${f}.costs.focus`, 'range', kit.range(`${f}.costs.focus`, 0, 99));
          if (costs.resources !== undefined) {
            if (!isObj(costs.resources)) push(`${f}.costs.resources`, 'type', kit.wrongType(`${f}.costs.resources`, 'object'));
            else {
              for (const [k, v] of Object.entries(costs.resources)) {
                if (resources.length > 0 && !resources.includes(k)) push(`${f}.costs.resources.${k}`, 'reference', kit.ref(`${f}.costs.resources`, k, 'resources'));
                if (typeof v !== 'number' || v < 0) push(`${f}.costs.resources.${k}`, 'range', kit.range(`${f}.costs.resources.${k}`, 0, 9999));
              }
            }
          }
        }
      }

      // risk
      if (!isObj(a.risk)) {
        push(`${f}.risk`, 'required', kit.required(`${f}.risk`));
      } else {
        const risk = a.risk;
        if (!RISK_LEVELS.includes(risk.level as RiskLevel)) push(`${f}.risk.level`, 'enum', kit.enumValue(`${f}.risk.level`, RISK_LEVELS.join(' | ')));
        if (!isInt(risk.base) || risk.base < 0) push(`${f}.risk.base`, 'range', kit.range(`${f}.risk.base`, 0, 9999));
        if (!isInt(risk.spread) || risk.spread < 0) push(`${f}.risk.spread`, 'range', kit.range(`${f}.risk.spread`, 0, 9999));
        if (risk.hiddenTag !== undefined && !isNonEmptyString(risk.hiddenTag)) push(`${f}.risk.hiddenTag`, 'type', kit.wrongType(`${f}.risk.hiddenTag`, 'string'));
      }

      // effects（固定动词表，宪法 §1）
      if (!Array.isArray(a.effects)) {
        push(`${f}.effects`, 'required', kit.required(`${f}.effects`));
      } else if (a.effects.length === 0) {
        push(`${f}.effects`, 'noEffects', kit.noEffects(`${f}.effects`));
      } else {
        for (let j = 0; j < a.effects.length; j++) {
          const e = a.effects[j];
          const ef = `${f}.effects[${j}]`;
          if (!isObj(e)) {
            push(ef, 'type', kit.wrongType(ef, 'object'));
            continue;
          }
          if (!VERBS.includes(e.verb as (typeof VERBS)[number])) {
            push(`${ef}.verb`, 'enum', kit.enumValue(`${ef}.verb`, VERBS.join(' | ')));
            continue;
          }
          switch (e.verb) {
            case 'resource': {
              if (!isNonEmptyString(e.resource)) push(`${ef}.resource`, 'required', kit.required(`${ef}.resource`));
              else if (resources.length > 0 && !resources.includes(e.resource)) push(`${ef}.resource`, 'reference', kit.ref(`${ef}.resource`, e.resource, 'resources'));
              if (!isInt(e.amount) || e.amount === 0) push(`${ef}.amount`, 'range', kit.range(`${ef}.amount`, -9999, 9999));
              break;
            }
            case 'knowledge': {
              if (!isNonEmptyString(e.knowledge)) push(`${ef}.knowledge`, 'required', kit.required(`${ef}.knowledge`));
              break;
            }
            case 'assetInvest': {
              if (!isNonEmptyString(e.asset)) push(`${ef}.asset`, 'required', kit.required(`${ef}.asset`));
              break;
            }
            case 'relation': {
              if (!isNonEmptyString(e.npcId)) push(`${ef}.npcId`, 'required', kit.required(`${ef}.npcId`));
              else if (npcIds.length > 0 && !npcIds.includes(e.npcId)) push(`${ef}.npcId`, 'reference', kit.ref(`${ef}.npcId`, e.npcId, 'npcs[].id'));
              if (!isInt(e.delta) || e.delta === 0 || e.delta < -3 || e.delta > 3) push(`${ef}.delta`, 'range', kit.range(`${ef}.delta`, -3, 3));
              break;
            }
            case 'windowOpen': {
              if (!WINDOW_KINDS.includes(e.kind as WindowKind)) push(`${ef}.kind`, 'enum', kit.enumValue(`${ef}.kind`, WINDOW_KINDS.join(' | ')));
              if (!isNonEmptyString(e.labelKey)) push(`${ef}.labelKey`, 'required', kit.required(`${ef}.labelKey`));
              break;
            }
            case 'unlock': {
              if (!isNonEmptyString(e.unlock)) push(`${ef}.unlock`, 'required', kit.required(`${ef}.unlock`));
              break;
            }
          }
        }
      }
    }
  }

  // leverage（宪法 §3.1 四要素 + 名称，缺一即错）
  if (!isObj(raw.leverage)) {
    push('leverage', 'required', kit.required('leverage'));
  } else {
    for (const key of ['name', 'causalChain', 'cost', 'whyUnreplicable', 'failureMode'] as const) {
      if (!isNonEmptyString(raw.leverage[key])) {
        push(`leverage.${key}`, 'leverage', kit.leverage(`leverage.${key}`, LEVERAGE_DESC[lang][key]));
      }
    }
  }

  // tierGates：3 级且必须与引擎固定门槛一致（防止 proposal 与实际门槛漂移）
  if (!Array.isArray(raw.tierGates)) {
    push('tierGates', 'required', kit.required('tierGates'));
  } else {
    if (raw.tierGates.length !== TIER_GATES.length) {
      push('tierGates', 'count', kit.tooFew('tierGates', TIER_GATES.length, raw.tierGates.length));
    }
    for (let i = 0; i < raw.tierGates.length; i++) {
      const g = raw.tierGates[i];
      const f = `tierGates[${i}]`;
      const fixed = TIER_GATES[i];
      if (!isObj(g)) {
        push(f, 'type', kit.wrongType(f, 'object'));
        continue;
      }
      if (!isInt(g.minAssetLevel) || g.minAssetLevel < 0) push(`${f}.minAssetLevel`, 'range', kit.range(`${f}.minAssetLevel`, 0, 99));
      if (!isInt(g.minKnowledge) || g.minKnowledge < 0) push(`${f}.minKnowledge`, 'range', kit.range(`${f}.minKnowledge`, 0, 99));
      if (typeof g.minStanding !== 'number' || g.minStanding < 0 || g.minStanding > 1) push(`${f}.minStanding`, 'range', kit.range(`${f}.minStanding`, 0, 1));
      if (fixed && (g.minAssetLevel !== fixed.minAssetLevel || g.minKnowledge !== fixed.minKnowledge || g.minStanding !== fixed.minStanding)) {
        push(f, 'gateMismatch', kit.gateMismatch(i, JSON.stringify(fixed)));
      }
    }
  }

  // expansionAnchors：Tier 2/3 宏观锚点（宪法 §7）
  const anchorTiers = new Set<number>();
  if (!Array.isArray(raw.expansionAnchors)) {
    push('expansionAnchors', 'required', kit.required('expansionAnchors'));
  } else {
    if (raw.expansionAnchors.length < 1) push('expansionAnchors', 'tooFew', kit.tooFew('expansionAnchors', 1, 0));
    for (let i = 0; i < raw.expansionAnchors.length; i++) {
      const an = raw.expansionAnchors[i];
      const f = `expansionAnchors[${i}]`;
      if (!isObj(an)) {
        push(f, 'type', kit.wrongType(f, 'object'));
        continue;
      }
      if (!isNonEmptyString(an.id)) push(`${f}.id`, 'required', kit.required(`${f}.id`));
      if (!isNonEmptyString(an.description)) push(`${f}.description`, 'required', kit.required(`${f}.description`));
      if (!isNonEmptyString(an.constraint)) push(`${f}.constraint`, 'required', kit.required(`${f}.constraint`));
      if (an.tier !== 2 && an.tier !== 3) push(`${f}.tier`, 'enum', kit.enumValue(`${f}.tier`, '2 | 3'));
      else anchorTiers.add(an.tier);
    }
  }
  for (const tierNeed of [2, 3]) {
    if (Array.isArray(raw.expansionAnchors) && !anchorTiers.has(tierNeed)) {
      push('expansionAnchors', 'anchorMissing', kit.anchorMissing(tierNeed));
    }
  }

  // 静默引用以保留数组校验结果（供未来扩展）
  void rulesExplicitOk;
  void rulesHiddenOk;

  if (issues.length > 0) return { ok: false, issues };
  return { ok: true, proposal: raw as unknown as WorldProposal };

  /** string[] 校验助手：长度 min..max，元素非空字符串。 */
  function checkStringArray(v: unknown, field: string, min: number, max: number): boolean {
    if (!Array.isArray(v)) {
      push(field, 'required', kit.required(field));
      return false;
    }
    let bad = false;
    if (v.length < min) {
      push(field, 'tooFew', kit.tooFew(field, min, v.length));
      bad = true;
    }
    if (Number.isFinite(max) && v.length > max) {
      push(field, 'tooMany', kit.tooMany(field, max, v.length));
      bad = true;
    }
    for (let i = 0; i < v.length; i++) {
      if (!isNonEmptyString(v[i])) {
        push(`${field}[${i}]`, 'type', kit.wrongType(`${field}[${i}]`, 'string'));
        bad = true;
      }
    }
    return !bad;
  }
}
