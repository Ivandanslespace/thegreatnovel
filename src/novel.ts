/**
 * 结局合成：end 时把书名页/目录/章节/结局梗概拼接为完整小说 novel.md。
 *
 * 小说只汇总已经成立的事实（章节正文 + 可追溯历史），不重新发明因果
 * （宪章 §1：删除叙事不能删除因果——history.jsonl 仍在）。
 */
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import type { Blueprint, GameState } from './types.ts';
import { readHistory, saveDirFor } from './save.ts';
import { stripFrontmatter } from './chapter.ts';

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
  const parts: string[] = [];

  // 书名页
  parts.push(`# ${bp.meta.title ?? bp.meta.name}`);
  parts.push('');
  parts.push(`> 世界由一句话开始：「${bp.meta.prompt}」`);
  parts.push('');
  parts.push(`- 世界：${bp.meta.name}`);
  parts.push(`- 控制轴：${bp.meta.controlAxis}`);
  parts.push(`- 种子：${state.seed}`);
  parts.push(`- 回合数：${state.turn}`);
  parts.push(`- 最终阶层：${state.tier}`);
  parts.push(`- 杠杆：${bp.leverage.name}（使用 ${state.leverageUses} 次）`);
  parts.push('');

  // 目录
  parts.push('## 目录');
  parts.push('');
  for (const ch of state.chapters) {
    parts.push(`${ch.index}. ${ch.title}（回合 ${ch.startTurn}–${ch.endTurn}）`);
  }
  parts.push(`${state.chapters.length + 1}. 终章：${reason}`);
  parts.push('');

  // 章节正文
  for (const ch of state.chapters) {
    const content = await readFile(path.join(dir, 'chapters', ch.file), 'utf8');
    parts.push('---');
    parts.push('');
    parts.push(`## 第${ch.index}章 ${ch.title}`);
    parts.push('');
    // 去掉入库时的 frontmatter，只保留正文
    const body = stripFrontmatter(content);
    parts.push(body.trim());
    parts.push('');
  }

  // 终章：结局梗概（来自可追溯历史，不发明新因果；M8：history 从 jsonl 读取）
  parts.push('---');
  parts.push('');
  parts.push(`## 终章 ${reason}`);
  parts.push('');
  const history = await readHistory(base, state.world);
  const visibleHistory = history.filter((h) => h.visible);
  const keyMoments = visibleHistory.filter((h) => h.kind === 'tier' || h.kind === 'ending');
  if (keyMoments.length > 0) {
    parts.push('### 关键时刻');
    parts.push('');
    for (const h of keyMoments) {
      parts.push(`- 回合 ${h.turn}：${h.text}`);
    }
    parts.push('');
  }
  parts.push('### 大事记');
  parts.push('');
  for (const h of visibleHistory) {
    parts.push(`- 回合 ${h.turn}：${h.text}`);
  }
  parts.push('');
  parts.push('---');
  parts.push('');
  parts.push('*本作由确定性引擎结算、由叙事者书写；删除文字不能删除因果。*');
  parts.push('');

  const novelFile = path.join(dir, 'novel.md');
  await writeFile(novelFile, parts.join('\n'), 'utf8');
  return { novelFile, chapters: state.chapters.length };
}
