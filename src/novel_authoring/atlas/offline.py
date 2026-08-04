# ruff: noqa: E501

"""Self-contained offline author-workbench snapshot exporter."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from typing import Any

from novel_authoring.atlas.service import atlas_root, get_atlas_overview
from novel_authoring.canon.projection import projection_from_connection
from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, resolve_edition_id
from novel_authoring.initialization import latest_initialization
from novel_authoring.utils import sha256_bytes, sha256_file, stable_id, utc_now


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def _read_text(path: Path, limit: int = 250_000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except OSError:
        return ""


def _copy_visuals(source_root: Path | None, destination: Path) -> dict[str, str]:
    destination.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    if source_root is None:
        return result
    for path in sorted((source_root / "visuals").glob("*.svg")):
        target = destination / path.name
        try:
            shutil.copyfile(path, target)
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            result[path.name] = f"data:image/svg+xml;base64,{encoded}"
        except OSError:
            continue
    return result


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(path, target)
        except OSError:
            continue


def _portable(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _portable(item)
            for key, item in value.items()
            if key not in {"artifact_root", "manifest_path", "workspace_root"}
        }
    if isinstance(value, list):
        return [_portable(item) for item in value]
    return value


def export_snapshot(
    database: Database,
    book_id: str,
    *,
    edition_id: str | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Export an entirely local HTML snapshot with no fetch/import dependency."""
    database.initialize()
    selected = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, selected)
        book_row = connection.execute("SELECT title FROM books WHERE book_id=?", (book_id,)).fetchone()
        metric_rows = connection.execute(
            "SELECT run_id AS metric_id, status, confidence AS score, scope_id, created_at "
            "FROM metric_runs "
            "WHERE book_id=? AND edition_id=? ORDER BY created_at DESC LIMIT 100",
            (book_id, selected),
        ).fetchall()
    if output_root is None:
        base_root = (
            Path(str(database.scalar("SELECT workspace_root FROM books WHERE book_id=?", (book_id,))))
            / "exports"
            / "author_workbench_snapshot"
        )
        root = base_root
        if (base_root / "index.html").is_file():
            root = base_root.with_name(
                f"{base_root.name}_{stable_id('snapshot', book_id, selected, utc_now()).split('_', 1)[-1]}"
            )
    else:
        root = output_root
    root = root.resolve()
    for name in ("assets", "atlas", "metrics", "visuals"):
        (root / name).mkdir(parents=True, exist_ok=True)
    atlas_data: dict[str, Any]
    source_atlas_root: Path | None = None
    try:
        atlas_data = get_atlas_overview(database, book_id, selected)
        if atlas_data.get("available"):
            source_atlas_root = atlas_root(database, book_id, selected)
            index = atlas_data.get("index") or {}
            if index.get("artifact_root"):
                source_atlas_root = Path(str(index["artifact_root"]))
    except Exception as exc:  # Snapshot should still be usable before Atlas exists.
        atlas_data = {"available": False, "error": str(exc), "book_id": book_id, "edition_id": selected}
    init_data = latest_initialization(database, book_id, selected)
    visuals = _copy_visuals(source_atlas_root, root / "visuals")
    reports: dict[str, str] = {}
    init_root = Path(init_data["root"]) if init_data else None
    for report_root in filter(None, [source_atlas_root, init_root]):
        for path in (report_root / "reports").glob("*.md"):
            reports[path.name] = _read_text(path)
            (root / "atlas" / path.name).write_text(reports[path.name], encoding="utf-8")
    (root / "atlas" / "overview.json").write_text(
        json.dumps(_portable(atlas_data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / "metrics" / "runs.json").write_text(
        json.dumps([dict(row) for row in metric_rows], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / "assets" / "README.txt").write_text(
        "本目录属于 author_workbench_snapshot；index.html 已内嵌全部 CSS、JS、章节、Atlas 摘要和 SVG。\n",
        encoding="utf-8",
    )
    if source_atlas_root is not None:
        _copy_tree(source_atlas_root, root / "atlas")
        (root / "atlas" / "overview.json").write_text(
            json.dumps(_portable(atlas_data), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if init_root is not None:
        _copy_tree(init_root, root / "initialization")
    with database.connect() as connection:
        projection_hash = projection_from_connection(connection, book_id, selected).sha256()
        effective_content_hash = sha256_bytes("".join(
            str(item.get("content_sha256") or "") for item in chapters
        ).encode("utf-8"))
    init_payload = None if init_data is None else _portable(init_data)
    if isinstance(init_payload, dict):
        init_payload["root"] = "initialization"
    atlas_data = _portable(atlas_data)
    payload = {
        "book": {"book_id": book_id, "title": "" if book_row is None else str(book_row["title"]), "edition_id": selected},
        "generated_at": utc_now(),
        "chapters": [
            {
                "ordinal": int(item["ordinal"]),
                "chapter_id": str(item["chapter_id"]),
                "heading": str(item.get("raw_heading") or item.get("title") or ""),
                "title": str(item.get("title") or ""),
                "content": str(item.get("content") or ""),
                "source_span_id": item.get("source_span_id"),
            }
            for item in chapters
        ],
        "atlas": atlas_data,
        "initialization": init_payload,
        "metrics": [dict(row) for row in metric_rows],
        "reports": reports,
        "visuals": visuals,
    }
    data = _json_for_script(payload)
    book_payload = payload["book"]
    title = (
        str(book_payload["title"])
        if isinstance(book_payload, dict) and book_payload.get("title")
        else book_id
    )
    html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 本地作者工作台</title>
<style>
:root{{--bg:#f6f7fb;--panel:#fff;--ink:#182033;--muted:#697386;--line:#d9e0ea;--accent:#2457d6;--soft:#e8efff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 system-ui,"Microsoft YaHei",sans-serif}}button,input{{font:inherit}}button{{cursor:pointer}}header{{position:sticky;top:0;z-index:4;display:flex;align-items:center;gap:12px;padding:14px 22px;background:var(--panel);border-bottom:1px solid var(--line)}}header strong{{font-size:18px}}header span{{color:var(--muted)}}.layout{{display:grid;grid-template-columns:280px minmax(0,1fr);gap:18px;width:min(1500px,calc(100% - 28px));margin:18px auto}}aside,section,.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px}}aside{{position:sticky;top:75px;align-self:start;max-height:calc(100vh - 95px);overflow:auto;padding:12px}}main{{min-width:0}}.tabs{{display:flex;flex-wrap:wrap;gap:7px;padding:10px;border-bottom:1px solid var(--line)}}.tabs button{{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:6px 11px}}.tabs button.active{{background:var(--soft);border-color:var(--accent);color:var(--accent)}}.stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}}.card{{padding:13px}}.stat span,.muted{{color:var(--muted)}}.stat strong{{display:block;font-size:21px;margin-top:3px}}#chapter-list{{display:grid;gap:2px;margin-top:10px}}#chapter-list button{{display:grid;grid-template-columns:42px 1fr;text-align:left;border:0;background:transparent;padding:7px;border-radius:6px;color:var(--ink)}}#chapter-list button:hover,#chapter-list button.active{{background:var(--soft)}}.reader{{padding:18px;min-height:60vh}}.reader h1{{margin-top:0}}.reader pre{{white-space:pre-wrap;font:15px/1.85 inherit}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}.report{{white-space:pre-wrap;background:var(--bg);border-radius:8px;padding:12px;max-height:360px;overflow:auto}}.visual{{overflow:auto;border:1px solid var(--line);border-radius:8px;padding:6px;background:#fff}}.visual svg{{min-width:700px;width:100%;height:auto}}.search{{width:100%;padding:8px;border:1px solid var(--line);border-radius:7px;margin:6px 0 8px}}.hidden{{display:none!important}}.notice{{padding:10px;border-left:4px solid var(--accent);background:var(--soft);margin-bottom:12px}}code{{overflow-wrap:anywhere}}@media(max-width:900px){{.layout{{grid-template-columns:1fr}}aside{{position:static;max-height:none}}.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><header><strong>小说作者工作台</strong><span>{title} · 本地离线快照 · {selected}</span><span style="margin-left:auto">Facts are deterministic. Meaning is probabilistic.</span></header>
<div class="layout"><aside><input class="search" id="search" placeholder="搜索章节标题或正文"><div class="muted" id="chapter-count"></div><div id="chapter-list"></div></aside><main><div class="tabs"><button class="active" data-tab="reader">章节阅读</button><button data-tab="atlas">Story Atlas</button><button data-tab="reports">报告与初始化</button><button data-tab="metrics">语义指标</button><button data-tab="visuals">七张图</button></div><div id="reader" class="tab"><div class="stats"><div class="card stat"><span>章节</span><strong id="stat-chapters"></strong></div><div class="card stat"><span>Arc</span><strong id="stat-arcs"></strong></div><div class="card stat"><span>初始化</span><strong id="stat-ready"></strong></div><div class="card stat"><span>Atlas</span><strong id="stat-atlas"></strong></div></div><div class="reader card"><h1 id="chapter-title"></h1><div class="muted" id="chapter-meta"></div><pre id="chapter-content"></pre></div></div><div id="atlas" class="tab hidden"><div class="card"><h2>Story Atlas</h2><div id="atlas-summary"></div><div id="atlas-graphs" class="grid"></div></div></div><div id="reports" class="tab hidden"><div id="init-summary" class="card"></div><div id="report-list" class="grid" style="margin-top:12px"></div></div><div id="metrics" class="tab hidden"><div class="card"><h2>指标运行</h2><div id="metric-list" class="grid"></div></div></div><div id="visuals" class="tab hidden"><div id="visual-list" class="grid"></div></div></main></div>
<script>const SNAPSHOT={data};
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s)); let current=0;
function esc(v){{return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function renderList(filter=''){{const list=$('#chapter-list'); list.innerHTML=''; const q=filter.toLowerCase(); let shown=0; SNAPSHOT.chapters.forEach((c,i)=>{{if(q&&!((c.heading+' '+c.content).toLowerCase().includes(q)))return; const b=document.createElement('button'); b.className=i===current?'active':''; b.innerHTML='<span>'+c.ordinal+'</span><span>'+esc(c.title||c.heading)+'</span>'; b.onclick=()=>showChapter(i); list.appendChild(b); shown++}}); $('#chapter-count').textContent=shown+' / '+SNAPSHOT.chapters.length+' 章'}}
function showChapter(i){{current=i;const c=SNAPSHOT.chapters[i]; if(!c)return; $('#chapter-title').textContent=c.heading; $('#chapter-meta').innerHTML='第 '+c.ordinal+' 章 · <code>'+esc(c.chapter_id)+'</code> · source span: '+esc(c.source_span_id||'unknown'); $('#chapter-content').textContent=c.content; renderList($('#search').value)}}
function textify(v){{if(v==null)return ''; if(typeof v==='string')return v; return JSON.stringify(v,null,2)}}
function renderAtlas(){{const a=SNAPSHOT.atlas||{{}}; const r=a.readiness||{{}}; $('#atlas-summary').innerHTML='<div class="notice">'+(a.available?'Atlas v'+esc(a.manifest?.atlas_version)+' · Readiness '+esc(r.status)+' · Source '+Math.round((r.source_coverage||0)*100)+'%':'当前快照没有已登记 Atlas；初始化任务仍可继续')+'</div><div class="grid"><div><b>Current World</b><p class="muted">'+esc(a.manifest?.current_chapter_ordinal||'—')+' 章 · 图谱 '+Object.keys(a.graphs||{{}}).length+' 类</p></div><div><b>Gaps</b><p class="muted">'+esc((r.gaps||[]).join('；')||'—')+'</p></div></div>'; const g=$('#atlas-graphs'); g.innerHTML=''; Object.entries(a.graphs||{{}}).forEach(([name,x])=>{{const d=document.createElement('div');d.className='card';d.innerHTML='<h3>'+esc(name)+'</h3><p class="muted">'+(x.nodes||[]).length+' nodes · '+(x.edges||[]).length+' edges</p>';g.appendChild(d)}})}}
function renderReports(){{const i=SNAPSHOT.initialization;$('#init-summary').innerHTML='<h2>初始化进度</h2>'+(i?'<div class="notice">'+esc(i.status?.state)+' · readiness '+esc(i.status?.readiness?.status||i.status?.readiness||'BLOCKED')+' · 初始化 '+esc(i.manifest?.initialization_id)+'</div><p>章节 '+esc(i.manifest?.chapter_count)+' · Arc '+esc(i.manifest?.arc_count)+' · 已完成 Arc '+esc((i.status?.completed_arc_ids||[]).length)+'</p>':'<p class="muted">未找到初始化目录。</p>');const l=$('#report-list');l.innerHTML='';Object.entries(SNAPSHOT.reports||{{}}).forEach(([n,t])=>{{const d=document.createElement('div');d.className='card';d.innerHTML='<h3>'+esc(n)+'</h3><div class="report">'+esc(t)+'</div>';l.appendChild(d)}})}}
function renderMetrics(){{const l=$('#metric-list');l.innerHTML='';(SNAPSHOT.metrics||[]).forEach(m=>{{const d=document.createElement('div');d.className='card';d.innerHTML='<b>'+esc(m.metric_id)+'</b><p>'+esc(m.status)+' · '+esc(m.score??'—')+'</p><small class="muted">'+esc(m.scope_id)+'</small>';l.appendChild(d)}});if(!l.children.length)l.innerHTML='<p class="muted">暂无指标运行。</p>'}}
function renderVisuals(){{const l=$('#visual-list');l.innerHTML='';Object.entries(SNAPSHOT.visuals||{{}}).forEach(([n,s])=>{{const d=document.createElement('div');d.className='card';d.innerHTML='<h3>'+esc(n)+'</h3><div class="visual"><img alt="'+esc(n)+'" src="'+s+'"></div>';l.appendChild(d)}});if(!l.children.length)l.innerHTML='<p class="muted">暂无 SVG 视觉资产。</p>'}}
$$('[data-tab]').forEach(b=>b.onclick=()=>{{$$('.tab').forEach(x=>x.classList.add('hidden'));$('#'+b.dataset.tab).classList.remove('hidden');$$('[data-tab]').forEach(x=>x.classList.toggle('active',x===b))}});$('#search').oninput=e=>renderList(e.target.value);renderList();showChapter(0);$('#stat-chapters').textContent=SNAPSHOT.chapters.length;$('#stat-arcs').textContent=SNAPSHOT.initialization?.manifest?.arc_count??'—';$('#stat-ready').textContent=SNAPSHOT.initialization?.status?.readiness?.status??SNAPSHOT.initialization?.status?.readiness??'未初始化';$('#stat-atlas').textContent=SNAPSHOT.atlas?.available?'v'+(SNAPSHOT.atlas.manifest?.atlas_version||'—'):'未登记';renderAtlas();renderReports();renderMetrics();renderVisuals();</script></body></html>'''
    (root / "index.html").write_text(html, encoding="utf-8")
    snapshot_id = root.name
    atlas_index = atlas_data.get("index", {}) if isinstance(atlas_data, dict) else {}
    initialization_manifest = (
        {} if init_payload is None else init_payload.get("manifest", {})
    )
    files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "snapshot_manifest.json"
    )
    snapshot_manifest = {
        "schema_version": "author-workbench-snapshot-v1",
        "snapshot_id": snapshot_id,
        "book_id": book_id,
        "edition_id": selected,
        "created_at": payload["generated_at"],
        "source_manifest_sha256": atlas_index.get("source_manifest_sha256", ""),
        "effective_content_sha256": effective_content_hash,
        "base_projection_hash": projection_hash,
        "atlas_id": atlas_index.get("atlas_id"),
        "atlas_version": atlas_index.get("atlas_version"),
        "atlas_manifest_hash": atlas_index.get("artifact_manifest_sha256"),
        "initialization_id": initialization_manifest.get("initialization_id"),
        "files": files,
        "file_hashes": {relative: sha256_file(root / relative) for relative in files},
    }
    (root / "snapshot_manifest.json").write_text(
        json.dumps(snapshot_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "output_root": str(root),
        "index": str(root / "index.html"),
        "snapshot_id": snapshot_id,
        "snapshot_manifest": str(root / "snapshot_manifest.json"),
        "chapter_count": len(chapters),
        "atlas_available": bool(atlas_data.get("available")),
        "visual_count": len(visuals),
        "report_count": len(reports),
        "initialization_id": None if not init_data else init_data["manifest"].get("initialization_id"),
    }
