# ruff: noqa: E501

"""Offline SVG Story Atlas visual renderer.

Graphviz is intentionally optional. The pure-Python renderer is deterministic,
does not use coordinates from the novel, and works when the web extra is absent.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

VISUAL_GRAPH_FILES = {
    "character_graph.svg": "characters.json",
    "faction_graph.svg": "factions.json",
    "ability_graph.svg": "abilities.json",
    "resource_chain.svg": "resources_and_items.json",
    "region_topology.svg": "regions.json",
    "plot_thread_graph.svg": "plot_threads.json",
    "stage_ladder.svg": "stage_transitions.json",
}


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _short(value: object, length: int = 24) -> str:
    text = str(value)
    return text if len(text) <= length else text[: length - 1] + "…"


def _graph_data(atlas_root: Path, filename: str) -> dict[str, Any]:
    path = atlas_root / "graphs" / filename
    if not path.is_file():
        return {"graph_type": filename.removesuffix(".json"), "atlas_version": 0, "nodes": [], "edges": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"graph_type": filename.removesuffix(".json"), "atlas_version": 0, "nodes": [], "edges": []}
    return value if isinstance(value, dict) else {}


def _positions(nodes: list[dict[str, Any]], kind: str) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    count = max(1, len(nodes))
    if kind == "stage_transitions":
        for index, node in enumerate(nodes):
            positions[str(node.get("node_id"))] = (120 + index * 220, 235)
        return positions
    if kind == "resources_and_items":
        for index, node in enumerate(nodes):
            positions[str(node.get("node_id"))] = (120 + (index % 4) * 250, 130 + (index // 4) * 150)
        return positions
    if kind == "regions":
        for index, node in enumerate(nodes):
            angle = (math.tau * index) / count
            positions[str(node.get("node_id"))] = (580 + math.cos(angle) * 360, 300 + math.sin(angle) * 210)
        return positions
    if kind == "factions":
        # Factions use a compact two-column topology so alliances and
        # oppositions remain legible instead of looking like another ring.
        for index, node in enumerate(nodes):
            column = index % 2
            row = index // 2
            positions[str(node.get("node_id"))] = (280 + column * 600, 150 + row * 150)
        return positions
    if kind == "abilities":
        # Abilities are rendered as a rising progression to suggest
        # evolution, while still allowing arbitrary graph edges.
        for index, node in enumerate(nodes):
            fraction = index / max(1, count - 1)
            positions[str(node.get("node_id"))] = (150 + fraction * 860, 470 - fraction * 300)
        return positions
    if kind == "plot_threads":
        # Plot threads use parallel lanes, making dormant/active threads easy
        # to compare at a glance.
        for index, node in enumerate(nodes):
            lane = index % 3
            sequence = index // 3
            positions[str(node.get("node_id"))] = (180 + sequence * 260, 150 + lane * 170)
        return positions
    for index, node in enumerate(nodes):
        angle = (math.tau * index) / count
        radius = 210 if kind == "characters" else 245
        positions[str(node.get("node_id"))] = (580 + math.cos(angle) * radius, 300 + math.sin(angle) * radius)
    return positions


def _style_for_status(status: str) -> tuple[str, str]:
    return {
        "CANON": ("#2f6fed", "#eaf1ff"),
        "INFERENCE": ("#9a6700", "#fff7dc"),
        "CANDIDATE": ("#7c3aed", "#f3e8ff"),
        "AUTHOR_INTENT": ("#087443", "#e6f8ef"),
        "APPROVED_OUTLINE": ("#087443", "#e6f8ef"),
        "PROSE_ONLY": ("#667085", "#f1f3f5"),
    }.get(status, ("#667085", "#f1f3f5"))


def _metadata_text(atlas_root: Path, graph: dict[str, Any], title: str, metadata: dict[str, Any]) -> str:
    manifest_path = atlas_root / "atlas_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            manifest = {}
    version = metadata.get("atlas_version", manifest.get("atlas_version", graph.get("atlas_version", 0)))
    coverage = metadata.get("source_coverage", manifest.get("source_coverage", {}))
    if isinstance(coverage, dict):
        coverage_text = coverage.get("chapter_coverage", coverage.get("coverage", "unknown"))
    else:
        coverage_text = coverage
    evidence_count = 0
    confidence_count = 0
    for node in graph.get("nodes", []):
        evidence_count += len(node.get("evidence", {}).get("source_span_ids", []))
        if node.get("confidence") not in (None, "UNKNOWN"):
            confidence_count += 1
    return (
        f"Atlas v{_escape(version)} · source coverage {_escape(coverage_text)} · "
        f"nodes {len(graph.get('nodes', []))} · edges {len(graph.get('edges', []))} · "
        f"evidence {evidence_count} · confidence values {confidence_count}"
    )


def render_svg(
    *,
    title: str,
    graph: dict[str, Any],
    atlas_root: Path,
    metadata: dict[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    nodes = [item for item in graph.get("nodes", []) if isinstance(item, dict)]
    edges = [item for item in graph.get("edges", []) if isinstance(item, dict)]
    kind = str(graph.get("graph_type", "graph"))
    positions = _positions(nodes, kind)
    width = 1280 if kind != "stage_transitions" else max(1280, 260 * max(1, len(nodes)))
    height = 680 if kind != "stage_transitions" else 480
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{_escape(title)}</title>',
        f'<desc id="desc">{_escape(_metadata_text(atlas_root, graph, title, metadata))}</desc>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 z" fill="#667085"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="28" y="32" font-family="system-ui, sans-serif" font-size="22" font-weight="700" fill="#162033">{_escape(title)}</text>',
        f'<text x="28" y="56" font-family="system-ui, sans-serif" font-size="12" fill="#667085">{_escape(_metadata_text(atlas_root, graph, title, metadata))}</text>',
        '<g transform="translate(28 78)">',
    ]
    if not nodes:
        parts.append('<text x="0" y="80" font-family="system-ui, sans-serif" font-size="16" fill="#667085">当前没有可渲染的已验证节点</text>')
    for edge in edges:
        start = positions.get(str(edge.get("from_id")))
        end = positions.get(str(edge.get("to_id")))
        if start is None or end is None:
            continue
        status = str(edge.get("information_status", "CANON"))
        stroke, _ = _style_for_status(status)
        dash = ' stroke-dasharray="7 5"' if status == "INFERENCE" else (' stroke-dasharray="2 5"' if status == "CANDIDATE" else "")
        x1, y1 = start
        x2, y2 = end
        label = _short(edge.get("label") or edge.get("relation_type") or "relation", 28)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="1.6" marker-end="url(#arrow)"{dash}/>'
        )
        parts.append(
            f'<text x="{(x1+x2)/2:.1f}" y="{(y1+y2)/2-5:.1f}" font-family="system-ui, sans-serif" font-size="10" fill="{stroke}">{_escape(label)}</text>'
        )
    for node in nodes:
        node_id = str(node.get("node_id"))
        x, y = positions.get(node_id, (80, 120))
        status = str(node.get("information_status", "CANON"))
        stroke, fill = _style_for_status(status)
        dash = ' stroke-dasharray="7 5"' if status == "INFERENCE" else (' stroke-dasharray="2 5"' if status == "CANDIDATE" else "")
        name = _short(node.get("name") or node_id, 22)
        parts.append(f'<g data-node-id="{_escape(node_id)}"><circle cx="{x:.1f}" cy="{y:.1f}" r="38" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/><text x="{x:.1f}" y="{y-3:.1f}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#162033">{_escape(name)}</text><text x="{x:.1f}" y="{y+14:.1f}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="9" fill="#667085">{_escape(status)}</text></g>')
    parts.extend([
        '</g>',
        '<g transform="translate(28 640)" font-family="system-ui, sans-serif" font-size="11"><text x="0" y="0" fill="#2f6fed">● CANON</text><text x="90" y="0" fill="#9a6700">◌ INFERENCE</text><text x="205" y="0" fill="#7c3aed">⋯ CANDIDATE</text><text x="330" y="0" fill="#667085">节点/关系均显示 evidence 与 confidence 摘要</text></g>',
        '</svg>',
    ])
    return "".join(parts)


def render_atlas_visuals(
    atlas_root: Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    """Render the seven required visual assets and return relative paths."""
    root = atlas_root.resolve()
    if (root / "atlas_manifest.json").is_file() and "versions" in root.parts:
        raise ValueError("已登记版本化 Atlas 不可原地重绘；请在 staging artifact 中渲染后重新登记")
    output = root / "visuals"
    output.mkdir(parents=True, exist_ok=True)
    titles = {
        "character_graph.svg": "Character Graph",
        "faction_graph.svg": "Faction Graph",
        "ability_graph.svg": "Ability Evolution Graph",
        "resource_chain.svg": "Resource and Production Chain",
        "region_topology.svg": "Region Topology",
        "plot_thread_graph.svg": "Plot Thread Graph",
        "stage_ladder.svg": "Stage Transition Ladder",
    }
    paths: list[str] = []
    for output_name, graph_name in VISUAL_GRAPH_FILES.items():
        graph = _graph_data(root, graph_name)
        path = output / output_name
        path.write_text(
            render_svg(title=titles[output_name], graph=graph, atlas_root=root, metadata=metadata),
            encoding="utf-8",
        )
        paths.append(f"visuals/{output_name}")
    return paths
