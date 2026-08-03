/**
 * 结局合成：end 时把书名页/目录/章节/结局梗概拼接为完整小说 novel.md。
 *
 * 小说只汇总已经成立的事实（章节正文 + 可追溯历史），不重新发明因果
 * （宪章 §1：删除叙事不能删除因果——history.jsonl 仍在）。
 * 固定文案按 state.language 取四语样板文本（V1.1；语言是表现层元数据，不影响结算）。
 */
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import type { Blueprint, GameState } from './types.ts';
import { readHistory, saveDirFor } from './save.ts';
import { stripFrontmatter } from './chapter.ts';
import { getNovelStrings, languageOf } from './i18n.ts';

export interface ComposeResult {
  novelFile: string;
  chapters: number;
}

/** 合成完整小说并写入 saves/<世界名>/novel.md。 */
export async function composeNovel(
  base: string,
  bp: Blueprint,
  state: GameState,
  reason: string,
): Promise<ComposeResult> {
  const dir = saveDirFor(base, state.world);
  const t = getNovelStrings(languageOf(state));
  const parts: string[] = [];

  // 书名页
  parts.push(`# ${bp.meta.title ?? bp.meta.name}`);
  parts.push('');
  parts.push(t.worldFromPrompt(bp.meta.prompt));
  parts.push('');
  parts.push(t.metaWorld(bp.meta.name));
  parts.push(t.metaControlAxis(bp.meta.controlAxis));
  parts.push(t.metaSeed(state.seed));
  parts.push(t.metaTurns(state.turn));
  parts.push(t.metaFinalTier(state.tier));
  parts.push(t.metaLeverage(bp.leverage.name, state.leverageUses));
  parts.push('');

  // 目录
  parts.push(t.tocTitle);
  parts.push('');
  for (const ch of state.chapters) {
    parts.push(t.tocChapter(ch.index, ch.title, ch.startTurn, ch.endTurn));
  }
  parts.push(t.tocFinal(state.chapters.length + 1, reason));
  parts.push('');

  // 章节正文
  for (const ch of state.chapters) {
    const content = await readFile(path.join(dir, 'chapters', ch.file), 'utf8');
    parts.push('---');
    parts.push('');
    parts.push(t.chapterHeading(ch.index, ch.title));
    parts.push('');
    // 去掉入库时的 frontmatter，只保留正文
    const body = stripFrontmatter(content);
    parts.push(body.trim());
    parts.push('');
  }

  // 终章：结局梗概（来自可追溯历史，不发明新因果；M8：history 从 jsonl 读取）
  parts.push('---');
  parts.push('');
  parts.push(t.finalHeading(reason));
  parts.push('');
  const history = await readHistory(base, state.world);
  const visibleHistory = history.filter((h) => h.visible);
  const keyMoments = visibleHistory.filter((h) => h.kind === 'tier' || h.kind === 'ending');
  if (keyMoments.length > 0) {
    parts.push(t.keyMomentsTitle);
    parts.push('');
    for (const h of keyMoments) {
      parts.push(t.historyLine(h.turn, h.text));
    }
    parts.push('');
  }
  parts.push(t.chronicleTitle);
  parts.push('');
  for (const h of visibleHistory) {
    parts.push(t.historyLine(h.turn, h.text));
  }
  parts.push('');
  parts.push('---');
  parts.push('');
  parts.push(t.footer);
  parts.push('');

  const novelFile = path.join(dir, 'novel.md');
  await writeFile(novelFile, parts.join('\n'), 'utf8');
  return { novelFile, chapters: state.chapters.length };
}
