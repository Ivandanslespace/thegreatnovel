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
from novel_authoring.storage.layout import BookLayout
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


def _decode_json_column(row: dict[str, Any], key: str, default: Any) -> None:
    raw = row.get(key)
    if raw is None or raw == "":
        row[key.removesuffix("_json")] = default
        return
    try:
        row[key.removesuffix("_json")] = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        row[key.removesuffix("_json")] = default


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
        metric_runs = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM metric_runs WHERE book_id=? AND edition_id=? "
                "ORDER BY created_at DESC",
                (book_id, selected),
            ).fetchall()
        ]
        for row in metric_runs:
            _decode_json_column(row, "requested_metric_ids_json", [])
            _decode_json_column(row, "disputed_components_json", [])
            _decode_json_column(row, "stale_components_json", [])
        metric_run_results = [
            dict(row)
            for row in connection.execute(
                "SELECT r.* FROM metric_run_results r JOIN metric_runs m ON m.run_id=r.run_id "
                "WHERE m.book_id=? AND m.edition_id=? ORDER BY m.created_at DESC, r.metric_id",
                (book_id, selected),
            ).fetchall()
        ]
        for row in metric_run_results:
            for key, default in (
                ("components_json", {}),
                ("missing_components_json", []),
                ("evidence_summary_json", []),
                ("disputed_components_json", []),
                ("stale_components_json", []),
                ("formula_contribution_json", {}),
            ):
                _decode_json_column(row, key, default)
        metric_observations = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM metric_observations WHERE book_id=? AND edition_id=? "
                "ORDER BY created_at DESC, observation_id DESC",
                (book_id, selected),
            ).fetchall()
        ]
        observation_ids = [str(row["observation_id"]) for row in metric_observations]
        metric_evidence_links: list[dict[str, Any]] = []
        if observation_ids:
            placeholders = ",".join("?" for _ in observation_ids)
            metric_evidence_links = [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM metric_evidence_links WHERE observation_id IN ({placeholders}) "
                    "ORDER BY created_at, link_id",
                    observation_ids,
                ).fetchall()
            ]
        evidence_by_observation: dict[str, list[dict[str, Any]]] = {}
        for link in metric_evidence_links:
            evidence_by_observation.setdefault(str(link["observation_id"]), []).append(link)
        for row in metric_observations:
            _decode_json_column(row, "value_json", None)
            row["evidence_links"] = evidence_by_observation.get(str(row["observation_id"]), [])
        chapter_features = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM chapter_features WHERE book_id=? AND edition_id=? "
                "ORDER BY created_at, feature_id",
                (book_id, selected),
            ).fetchall()
        ]
        for row in chapter_features:
            _decode_json_column(row, "evidence_json", {})
        rhythm_snapshots = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM rhythm_diagnostic_snapshots WHERE book_id=? AND edition_id=? "
                "ORDER BY as_of_chapter DESC, created_at DESC",
                (book_id, selected),
            ).fetchall()
        ]
        for row in rhythm_snapshots:
            _decode_json_column(row, "analyzer_versions_json", [])
            _decode_json_column(row, "snapshot_json", {})
    canonical_portable = False
    if output_root is None:
        book_root = Path(
            str(database.scalar("SELECT workspace_root FROM books WHERE book_id=?", (book_id,)))
        ).resolve()
        if (book_root / "book.yaml").is_file():
            canonical_portable = True
            root = BookLayout(book_root.parent).for_book(book_id).edition(selected).latest_export
            if root.exists() and any(root.iterdir()):
                archive_root = root.parent / "archive"
                archive_root.mkdir(parents=True, exist_ok=True)
                archived = archive_root / (
                    f"portable-{stable_id('snapshot', book_id, selected, utc_now()).split('_', 1)[-1]}"
                )
                shutil.move(str(root), str(archived))
                _prune_portable_archive(archive_root, keep=3)
        else:
            base_root = book_root / "exports" / "author_workbench_snapshot"
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
    visuals = {} if canonical_portable else _copy_visuals(source_atlas_root, root / "visuals")
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
        json.dumps(metric_runs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for filename, value in (
        ("metric_runs.json", metric_runs),
        ("metric_run_results.json", metric_run_results),
        ("metric_observations.json", metric_observations),
        ("metric_evidence_links.json", metric_evidence_links),
        ("chapter_features.json", chapter_features),
        ("rhythm_snapshots.json", rhythm_snapshots),
    ):
        (root / "metrics" / filename).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
    initialization_coverage = {}
    if isinstance(init_payload, dict):
        status_payload = init_payload.get("status") or {}
        readiness_payload = status_payload.get("readiness") or {}
        initialization_coverage = {
            key: readiness_payload.get(key)
            for key in (
                "source_mapping_coverage",
                "arc_output_coverage",
                "chapter_semantic_feature_coverage",
                "metric_observation_coverage",
                "recent_detailed_metric_coverage",
                "current_chapter_metric_coverage",
                "metric_bootstrap_status",
            )
            if key in readiness_payload
        }
    metrics_payload = {
        "runs": metric_runs,
        "run_results": metric_run_results,
        "observations": metric_observations,
        "evidence_links": metric_evidence_links,
        "chapter_features": chapter_features,
        "rhythm_snapshots": rhythm_snapshots,
        "initialization_coverage": initialization_coverage,
    }
    (root / "metrics" / "initialization_coverage.json").write_text(
        json.dumps(initialization_coverage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
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
        "metrics": metrics_payload,
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
<div class="layout"><aside><input class="search" id="search" placeholder="搜索章节标题或正文"><div class="muted" id="chapter-count"></div><div id="chapter-list"></div></aside><main><div class="tabs"><button class="active" data-tab="reader">章节阅读</button><button data-tab="atlas">Story Atlas</button><button data-tab="reports">报告与初始化</button><button data-tab="metrics">语义指标</button><button data-tab="visuals">七张图</button></div><div id="reader" class="tab"><div class="stats"><div class="card stat"><span>章节</span><strong id="stat-chapters"></strong></div><div class="card stat"><span>Arc</span><strong id="stat-arcs"></strong></div><div class="card stat"><span>初始化</span><strong id="stat-ready"></strong></div><div class="card stat"><span>Atlas</span><strong id="stat-atlas"></strong></div></div><div class="reader card"><h1 id="chapter-title"></h1><div class="muted" id="chapter-meta"></div><pre id="chapter-content"></pre></div></div><div id="atlas" class="tab hidden"><div class="card"><h2>Story Atlas</h2><div id="atlas-summary"></div><div id="atlas-graphs" class="grid"></div></div></div><div id="reports" class="tab hidden"><div id="init-summary" class="card"></div><div id="report-list" class="grid" style="margin-top:12px"></div></div><div id="metrics" class="tab hidden"><div class="card"><h2>语义指标</h2><label>章节<select id="metric-chapter"></select></label><div id="metric-list" class="grid"></div></div></div><div id="visuals" class="tab hidden"><div id="visual-list" class="grid"></div></div></main></div>
<script>const SNAPSHOT={data};
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s)); let current=0;
function esc(v){{return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function renderList(filter=''){{const list=$('#chapter-list'); list.innerHTML=''; const q=filter.toLowerCase(); let shown=0; SNAPSHOT.chapters.forEach((c,i)=>{{if(q&&!((c.heading+' '+c.content).toLowerCase().includes(q)))return; const b=document.createElement('button'); b.className=i===current?'active':''; b.innerHTML='<span>'+c.ordinal+'</span><span>'+esc(c.title||c.heading)+'</span>'; b.onclick=()=>showChapter(i); list.appendChild(b); shown++}}); $('#chapter-count').textContent=shown+' / '+SNAPSHOT.chapters.length+' 章'}}
function showChapter(i){{current=i;const c=SNAPSHOT.chapters[i]; if(!c)return; $('#chapter-title').textContent=c.heading; $('#chapter-meta').innerHTML='第 '+c.ordinal+' 章 · <code>'+esc(c.chapter_id)+'</code> · source span: '+esc(c.source_span_id||'unknown'); $('#chapter-content').textContent=c.content; renderList($('#search').value)}}
function textify(v){{if(v==null)return ''; if(typeof v==='string')return v; return JSON.stringify(v,null,2)}}
function renderAtlas(){{const a=SNAPSHOT.atlas||{{}}; const r=a.readiness||{{}}; $('#atlas-summary').innerHTML='<div class="notice">'+(a.available?'Atlas v'+esc(a.manifest?.atlas_version)+' · Readiness '+esc(r.status)+' · Source '+Math.round((r.source_coverage||0)*100)+'%':'当前快照没有已登记 Atlas；初始化任务仍可继续')+'</div><div class="grid"><div><b>Current World</b><p class="muted">'+esc(a.manifest?.current_chapter_ordinal||'—')+' 章 · 图谱 '+Object.keys(a.graphs||{{}}).length+' 类</p></div><div><b>Gaps</b><p class="muted">'+esc((r.gaps||[]).join('；')||'—')+'</p></div></div>'; const g=$('#atlas-graphs'); g.innerHTML=''; Object.entries(a.graphs||{{}}).forEach(([name,x])=>{{const d=document.createElement('div');d.className='card';d.innerHTML='<h3>'+esc(name)+'</h3><p class="muted">'+(x.nodes||[]).length+' nodes · '+(x.edges||[]).length+' edges</p>';g.appendChild(d)}})}}
function renderReports(){{const i=SNAPSHOT.initialization;$('#init-summary').innerHTML='<h2>初始化进度</h2>'+(i?'<div class="notice">'+esc(i.status?.state)+' · readiness '+esc(i.status?.readiness?.status||i.status?.readiness||'BLOCKED')+' · 初始化 '+esc(i.manifest?.initialization_id)+'</div><p>章节 '+esc(i.manifest?.chapter_count)+' · Arc '+esc(i.manifest?.arc_count)+' · 已完成 Arc '+esc((i.status?.completed_arc_ids||[]).length)+'</p>':'<p class="muted">未找到初始化目录。</p>');const l=$('#report-list');l.innerHTML='';Object.entries(SNAPSHOT.reports||{{}}).forEach(([n,t])=>{{const d=document.createElement('div');d.className='card';d.innerHTML='<h3>'+esc(n)+'</h3><div class="report">'+esc(t)+'</div>';l.appendChild(d)}})}}
function renderMetrics(){{const data=SNAPSHOT.metrics||{{}};const select=$('#metric-chapter');select.innerHTML='';SNAPSHOT.chapters.forEach(c=>{{const option=document.createElement('option');option.value=c.chapter_id;option.textContent=c.ordinal+' · '+(c.title||c.heading);select.appendChild(option)}});function draw(){{const chapterId=select.value;const runs=(data.runs||[]).filter(r=>r.scope_type==='CHAPTER'&&r.scope_id===chapterId&&!r.invalidated_at);const latest=runs[0];const results=latest?(data.run_results||[]).filter(r=>r.run_id===latest.run_id):[];const observations=(data.observations||[]).filter(o=>o.scope_type==='CHAPTER'&&o.scope_id===chapterId&&Number(o.active||0)===1);const evidenceBy={{}};(data.evidence_links||[]).forEach(e=>{{(evidenceBy[e.observation_id]||(evidenceBy[e.observation_id]=[])).push(e)}});const l=$('#metric-list');l.innerHTML='';if(!latest){{l.innerHTML='<p class="muted">该章节尚未完成语义指标分析。</p>';return}};const head=document.createElement('div');head.className='card';head.innerHTML='<div class="notice">最新 Run：<code>'+esc(latest.run_id)+'</code> · '+esc(latest.status)+' · completeness '+esc(latest.completeness)+' · Observation history '+observations.length+'</div>';l.appendChild(head);results.forEach(r=>{{const components=Object.entries(r.components||{{}}).map(([k,v])=>'<li><code>'+esc(k)+'</code> · '+esc(v.status||'—')+' · '+esc(v.source_kind||'—')+' · '+esc(textify(v.value))+'</li>').join('');const metricObs=observations.filter(o=>o.metric_id===r.metric_id);const obsText=metricObs.map(o=>'<li>'+esc(o.component_id)+' · '+esc(o.status)+' · '+esc(o.source_kind)+' · '+esc(textify(o.value))+' · '+esc(o.reason||'')+'</li>').join('');const ev=metricObs.flatMap(o=>evidenceBy[o.observation_id]||[]).map(e=>'<li>'+esc(e.segment_id||e.source_span_id||e.event_id||'—')+' · '+esc(e.evidence_quote||'')+'</li>').join('');const d=document.createElement('div');d.className='card';d.innerHTML='<b>'+esc(r.metric_id)+'</b><p>'+esc(r.status)+' · score '+esc(r.score??'—')+' · completeness '+esc(r.completeness)+'</p><h4>Components</h4><ul>'+components+'</ul><h4>Evidence</h4><ul>'+(ev||'<li class="muted">暂无 Evidence</li>')+'</ul><h4>Observation history</h4><ul>'+(obsText||'<li class="muted">该章节尚未完成语义指标分析。</li>')+'</ul>';l.appendChild(d)}})}}select.onchange=draw;select.value=SNAPSHOT.chapters[current]?.chapter_id||SNAPSHOT.chapters[0]?.chapter_id||'';draw()}}
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
    portable_manifest = None
    if canonical_portable:
        portable_manifest = _write_portable_bundle(
            root,
            payload=payload,
            book_id=book_id,
            edition_id=selected,
        )
    return {
        "output_root": str(root),
        "index": str(root / "index.html"),
        "snapshot_id": snapshot_id,
        "snapshot_manifest": None if canonical_portable else str(root / "snapshot_manifest.json"),
        "manifest": None if portable_manifest is None else str(root / "manifest.json"),
        "portable_bundle": canonical_portable,
        "chapter_count": len(chapters),
        "atlas_available": bool(atlas_data.get("available")),
        "visual_count": len(visuals),
        "report_count": len(reports),
        "initialization_id": None if not init_data else init_data["manifest"].get("initialization_id"),
    }


def _write_portable_bundle(
    root: Path,
    *,
    payload: dict[str, Any],
    book_id: str,
    edition_id: str,
) -> dict[str, Any]:
    """Write the fixed latest bundle without network or ``file://`` fetches."""

    # ``root`` is the generated ``exports/latest`` directory.  It is safe to
    # rebuild because previous latest bundles were moved to archive before
    # this function was called.  Keeping only the fixed contract here avoids
    # stale legacy ``atlas/``, ``metrics/`` and ``snapshot_manifest.json``
    # files leaking into a portable bundle.
    for child in list(root.iterdir()):
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        elif child.is_file() or child.is_symlink():
            child.unlink()

    data_root = root / "data"
    chapters_root = data_root / "chapters"
    metrics_root = data_root / "metrics"
    atlas_root_path = data_root / "atlas"
    reports_root = data_root / "reports"
    assets_root = root / "assets"
    for directory in (chapters_root, metrics_root, atlas_root_path, reports_root, assets_root):
        directory.mkdir(parents=True, exist_ok=True)

    book_value = payload.get("book") or {"book_id": book_id, "edition_id": edition_id}
    atlas_value = _portable(payload.get("atlas") or {})
    metrics_value = _portable(payload.get("metrics") or {})
    reports_value = payload.get("reports") or {}
    chapters = payload.get("chapters") or []
    (data_root / "book.js").write_text(
        "window.__NOVEL_SNAPSHOT__.registerBook(" + _json_for_script(book_value) + ");\n",
        encoding="utf-8",
        newline="\n",
    )
    (atlas_root_path / "atlas.js").write_text(
        "window.__NOVEL_SNAPSHOT__.registerAtlas(" + _json_for_script(atlas_value) + ");\n",
        encoding="utf-8",
        newline="\n",
    )
    (metrics_root / "metrics.js").write_text(
        "window.__NOVEL_SNAPSHOT__.registerMetrics(" + _json_for_script(metrics_value) + ");\n",
        encoding="utf-8",
        newline="\n",
    )
    (reports_root / "reports.js").write_text(
        "window.__NOVEL_SNAPSHOT__.registerReports(" + _json_for_script(reports_value) + ");\n",
        encoding="utf-8",
        newline="\n",
    )

    max_bytes = 512 * 1024
    chunk_files: list[str] = []
    chunk_sizes: dict[str, int] = {}
    current: list[Any] = []

    def flush_chunk() -> None:
        if not current:
            return
        chunk_number = len(chunk_files) + 1
        relative = f"chapters/chunk-{chunk_number:03d}.js"
        body = (
            "window.__NOVEL_SNAPSHOT__.registerChapterChunk("
            + _json_for_script(list(current))
            + ");\n"
        )
        target = chapters_root / f"chunk-{chunk_number:03d}.js"
        target.write_text(body, encoding="utf-8", newline="\n")
        chunk_files.append(relative)
        chunk_sizes[f"data/{relative}"] = target.stat().st_size
        current.clear()

    for chapter in chapters:
        candidate = [*current, chapter]
        candidate_body = (
            "window.__NOVEL_SNAPSHOT__.registerChapterChunk("
            + _json_for_script(candidate)
            + ");\n"
        )
        if current and len(candidate_body.encode("utf-8")) > max_bytes:
            flush_chunk()
        current.append(chapter)
    flush_chunk()

    (assets_root / "style.css").write_text(_portable_style_css(), encoding="utf-8", newline="\n")
    (assets_root / "app.js").write_text(
        _portable_app_js(), encoding="utf-8", newline="\n"
    )
    html = _portable_index_html(book_value, chunk_files)
    (root / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (root / "README.txt").write_text(
        "Portable Snapshot Bundle\n"
        "可直接打开 index.html；所有数据和脚本均在 bundle 内，不使用 fetch、网络或服务端。\n"
        "章节按字节阈值分块；Atlas 图谱以 JSON 为 canonical source，SVG 仅由显式 atlas export-visuals 生成。\n",
        encoding="utf-8",
        newline="\n",
    )
    files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "schema_version": "portable-snapshot-v2",
        "bundle_kind": "PORTABLE_SNAPSHOT_BUNDLE",
        "book_id": book_id,
        "edition_id": edition_id,
        "latest": True,
        "generated_at": utc_now(),
        "index": "index.html",
        "assets": {"app": "assets/app.js", "style": "assets/style.css"},
        "data": {
            "book": "data/book.js",
            "chapters": [f"data/{path}" for path in chunk_files],
            "metrics": "data/metrics/metrics.js",
            "atlas": "data/atlas/atlas.js",
            "reports": "data/reports/reports.js",
        },
        "chapter_chunk_max_bytes": max_bytes,
        "chapter_chunk_sizes": chunk_sizes,
        "files": files,
        "file_hashes": {relative: sha256_file(root / relative) for relative in files},
        "graphs": "JSON_CANONICAL_DYNAMIC_RENDER",
        "svg_status": "REGENERABLE_EXPLICIT_EXPORT",
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def _prune_portable_archive(archive_root: Path, *, keep: int) -> None:
    """Retain the newest generated portable archives without touching legacy archives."""

    generated = sorted(
        (path for path in archive_root.glob("portable-*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for stale in generated[max(0, keep) :]:
        shutil.rmtree(stale)


def _portable_index_html_legacy(book: Any, chunk_files: list[str]) -> str:
    title = str(book.get("title") or book.get("book_id") or "Novel") if isinstance(book, dict) else "Novel"
    scripts = "\n".join(
        f'<script src="data/{path}"></script>' if not path.startswith("chapters/") else f'<script src="data/{path}"></script>'
        for path in ["book.js", "atlas.js", "metrics.js", "reports.js", *chunk_files]
    )
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Portable Snapshot</title>
<style>
body{{margin:0;background:#f5f7fb;color:#192236;font:14px/1.6 system-ui,"Microsoft YaHei",sans-serif}}header{{padding:16px 24px;background:#fff;border-bottom:1px solid #dce3ef;position:sticky;top:0}}main{{max-width:1400px;margin:18px auto;padding:0 18px}}nav{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}button{{border:1px solid #cbd5e1;background:#fff;border-radius:999px;padding:7px 12px;cursor:pointer}}button.active{{background:#e8efff;border-color:#2457d6;color:#2457d6}}section{{background:#fff;border:1px solid #dce3ef;border-radius:12px;padding:16px;margin-bottom:14px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}.muted{{color:#667085}}pre{{white-space:pre-wrap;font:14px/1.7 inherit}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #edf0f5;text-align:left;padding:6px}}.hidden{{display:none}}
</style></head><body><header><strong>小说作者 Portable Snapshot</strong> <span id="book-meta" class="muted"></span></header><main>
<nav><button data-view="GraphView">GraphView</button><button data-view="TimelineView">TimelineView</button><button data-view="TopologyView">TopologyView</button><button data-view="DependencyView">DependencyView</button></nav>
<section id="app"></section></main>
<script>window.NOVEL_CHAPTERS=[];</script>
{scripts}
<script>
const book=window.NOVEL_BOOK||{{}};const chapters=window.NOVEL_CHAPTERS||[];const atlas=window.NOVEL_ATLAS||{{}};const metrics=window.NOVEL_METRICS||{{}};const reports=window.NOVEL_REPORTS||{{}};const app=document.getElementById('app');document.getElementById('book-meta').textContent=(book.title||book.book_id||'')+' · '+(book.edition_id||'base')+' · '+chapters.length+' chapters';
function esc(v){{return String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function graphView(){{const graphs=atlas.graphs||{{}};return '<h2>GraphView</h2><div class="grid">'+Object.entries(graphs).map(([name,g])=>'<section><h3>'+esc(name)+'</h3><p>'+((g.nodes||[]).length)+' nodes · '+((g.edges||[]).length)+' edges</p><pre>'+esc(JSON.stringify(g,null,2))+'</pre></section>').join('')+'</div>'}}
function timelineView(){{return '<h2>TimelineView</h2><table><tr><th>Ordinal</th><th>Title</th><th>Content</th></tr>'+chapters.map(c=>'<tr><td>'+esc(c.ordinal)+'</td><td>'+esc(c.title||c.heading)+'</td><td>'+esc((c.content||'').slice(0,180))+'</td></tr>').join('')+'</table>'}}
function topologyView(){{const graphs=atlas.graphs||{{}};return '<h2>TopologyView</h2><p class="muted">JSON graph topology，运行时绘制，不依赖静态 SVG。</p><div class="grid">'+Object.entries(graphs).map(([name,g])=>'<section><b>'+esc(name)+'</b><p>节点 '+((g.nodes||[]).length)+' · 边 '+((g.edges||[]).length)+'</p></section>').join('')+'</div>'}}
function dependencyView(){{const runs=metrics.runs||[];return '<h2>DependencyView</h2><p>Metric runs: '+runs.length+' · Observations: '+((metrics.observations||[]).length)+'</p><pre>'+esc(JSON.stringify({{runs:runs.slice(0,30),reports:Object.keys(reports)}},null,2))+'</pre>'}}
function render(name){{document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===name));app.innerHTML=name==='TimelineView'?timelineView():name==='TopologyView'?topologyView():name==='DependencyView'?dependencyView():graphView()}}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>render(b.dataset.view));render('GraphView');
</script></body></html>'''


def _portable_style_css() -> str:
    return """:root{color-scheme:light;--bg:#f5f7fb;--panel:#fff;--ink:#192236;--muted:#667085;--line:#dce3ef;--accent:#2457d6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 system-ui,"Microsoft YaHei",sans-serif}header{padding:16px 24px;background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}main{max-width:1400px;margin:18px auto;padding:0 18px}nav{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}button{border:1px solid #cbd5e1;background:var(--panel);border-radius:999px;padding:7px 12px;cursor:pointer}button.active{background:#e8efff;border-color:var(--accent);color:var(--accent)}section,.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}.muted{color:var(--muted)}pre{white-space:pre-wrap;font:14px/1.7 inherit}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #edf0f5;text-align:left;padding:6px}.hidden{display:none}.reader{white-space:pre-wrap;line-height:1.9}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat strong{display:block;font-size:21px}@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}}"""


def _portable_app_js() -> str:
    return r"""(function(){
const state=window.__NOVEL_SNAPSHOT__=window.__NOVEL_SNAPSHOT__||{chapters:[],book:{},atlas:{},metrics:{},reports:{}};
state.registerBook=function(value){state.book=value||{}};
state.registerChapterChunk=function(value){if(Array.isArray(value))state.chapters.push.apply(state.chapters,value)};
state.registerMetrics=function(value){state.metrics=value||{}};
state.registerAtlas=function(value){state.atlas=value||{}};
state.registerReports=function(value){state.reports=value||{}};
function esc(value){return String(value??'').replace(/[&<>"']/g,function(c){return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])})}
function graphView(){const graphs=state.atlas.graphs||{};return '<h2>GraphView</h2><div class="grid">'+Object.entries(graphs).map(function(e){const n=e[0],g=e[1]||{};return '<section><h3>'+esc(n)+'</h3><p>'+(g.nodes||[]).length+' nodes · '+(g.edges||[]).length+' edges</p><pre>'+esc(JSON.stringify(g,null,2))+'</pre></section>'}).join('')+'</div>'}
function timelineView(){return '<h2>TimelineView</h2><table><tr><th>Ordinal</th><th>Title</th><th>Content</th></tr>'+state.chapters.map(function(c){return '<tr><td>'+esc(c.ordinal)+'</td><td>'+esc(c.title||c.heading)+'</td><td>'+esc((c.content||'').slice(0,220))+'</td></tr>'}).join('')+'</table>'}
function topologyView(){const graphs=state.atlas.graphs||{};return '<h2>TopologyView</h2><p class="muted">图谱由 JSON 动态渲染；没有静态 SVG 依赖。</p><div class="grid">'+Object.entries(graphs).map(function(e){const n=e[0],g=e[1]||{};return '<section><b>'+esc(n)+'</b><p>节点 '+(g.nodes||[]).length+' · 边 '+(g.edges||[]).length+'</p></section>'}).join('')+'</div>'}
function dependencyView(){const m=state.metrics||{};return '<h2>DependencyView</h2><p>Metric runs: '+(m.runs||[]).length+' · Observations: '+(m.observations||[]).length+'</p><pre>'+esc(JSON.stringify({initialization_coverage:m.initialization_coverage||{},reports:Object.keys(state.reports||{})},null,2))+'</pre>'}
function readerView(){if(!state.chapters.length)return '<p class="muted">没有章节数据。</p>';const c=state.chapters[0];return '<h2>章节阅读</h2><p class="muted">共 '+state.chapters.length+' 章；当前显示第 '+esc(c.ordinal)+' 章</p><article class="reader"><h3>'+esc(c.heading||c.title)+'</h3>'+esc(c.content||'')+'</article>'}
function render(view){document.querySelectorAll('nav button').forEach(function(b){b.classList.toggle('active',b.dataset.view===view)});const app=document.getElementById('app');app.innerHTML=view==='TimelineView'?timelineView():view==='TopologyView'?topologyView():view==='DependencyView'?dependencyView():view==='ReaderView'?readerView():graphView()}
function boot(){document.getElementById('book-meta').textContent=(state.book.title||state.book.book_id||'')+' · '+(state.book.edition_id||'base')+' · '+state.chapters.length+' chapters';document.querySelectorAll('nav button').forEach(function(b){b.onclick=function(){render(b.dataset.view)}});render('ReaderView')}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
"""


def _portable_index_html(book: Any, chunk_files: list[str]) -> str:
    title = str(book.get("title") or book.get("book_id") or "Novel") if isinstance(book, dict) else "Novel"
    scripts = ["data/book.js", *[f"data/{path}" for path in chunk_files], "data/metrics/metrics.js", "data/atlas/atlas.js", "data/reports/reports.js", "assets/app.js"]
    script_tags = "\n".join(f'<script src="{path}"></script>' for path in scripts)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Portable Snapshot</title><link rel="stylesheet" href="assets/style.css"></head><body><header><strong>小说作者 Portable Snapshot</strong> <span id="book-meta" class="muted"></span></header><main><nav><button data-view="ReaderView">ReaderView</button><button data-view="GraphView">GraphView</button><button data-view="TimelineView">TimelineView</button><button data-view="TopologyView">TopologyView</button><button data-view="DependencyView">DependencyView</button></nav><section id="app"></section></main>
{script_tags}
</body></html>"""
