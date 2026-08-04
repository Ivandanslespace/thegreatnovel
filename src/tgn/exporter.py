"""Markdown novel projection and atomic manuscript export."""
from __future__ import annotations
import os, tempfile
from pathlib import Path
from typing import Any

from .narrative import project_chapters

def _atomic_write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as h:
            h.write(text); h.flush(); os.fsync(h.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return path

def render_markdown(campaign: Any, *, final: bool | None = None) -> str:
    project_chapters(campaign)
    is_final = campaign.status == "finished" if final is None else bool(final)
    title = campaign.world.get("title", campaign.premise)
    def yaml(value: Any) -> str:
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    state = "final" if is_final else campaign.status
    lines = ["---", f"title: {yaml(title)}", f"campaign_id: {yaml(campaign.campaign_id)}", f"locale: {yaml(campaign.locale)}", f"status: {yaml(state)}", f"tier: {campaign.tier}", f"turn: {campaign.turn}", "---", ""]
    for ch in campaign.chapters:
        fallback_title = "Turn " + str(ch.get("turn", 0))
        chapter_title = str(ch.get("title") or fallback_title)
        heading = "## " + (f"<span dir=\"rtl\">{chapter_title}</span>" if campaign.locale == "ar" else chapter_title)
        text = ch.get("polished_text") or ch.get("fallback_text") or ""
        if campaign.locale == "ar": text = f"<div dir=\"rtl\"><bdi>{text}</bdi></div>"
        lines.extend([heading, text, ""])
    body = "\n".join(lines)
    return body

def export_campaign(campaign: Any, runtime: str | os.PathLike[str], *, final: bool | None = None) -> Path:
    root = Path(runtime); target_dir = root / ("exports" if (campaign.status == "finished" if final is None else final) else "manuscripts") / campaign.campaign_id
    return _atomic_write(target_dir / "novel.md", render_markdown(campaign, final=final))

def write_manuscript(campaign: Any, runtime: str | os.PathLike[str]) -> Path:
    return export_campaign(campaign, runtime, final=False)
