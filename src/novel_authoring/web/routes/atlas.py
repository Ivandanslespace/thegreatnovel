from __future__ import annotations

from typing import Any

from novel_authoring.atlas.service import AtlasError, get_atlas_overview
from novel_authoring.db.database import Database

GRAPH_TYPES = {
    "characters",
    "factions",
    "abilities",
    "resources_and_items",
    "regions",
    "plot_threads",
    "stage_transitions",
}
HORIZONS = {"CURRENT", "NEAR", "MID", "FAR"}
INFORMATION_STATUSES = {
    "CANON",
    "AUTHOR_INTENT",
    "APPROVED_OUTLINE",
    "INFERENCE",
    "CANDIDATE",
    "PROSE_ONLY",
}


def _public_index(index: dict[str, Any]) -> dict[str, Any]:
    return {
        key: index.get(key)
        for key in (
            "atlas_id",
            "atlas_version",
            "book_id",
            "edition_id",
            "base_event_seq",
            "base_projection_hash",
            "source_manifest_sha256",
            "artifact_manifest_sha256",
            "status",
            "readiness_status",
            "author_accepted",
            "created_at",
            "invalidated_at",
        )
    }


def public_atlas_overview(database: Database, book_id: str, edition_id: str) -> dict[str, Any]:
    overview = get_atlas_overview(database, book_id, edition_id)
    if "index" in overview:
        overview["index"] = _public_index(dict(overview["index"]))
    overview["history"] = [_public_index(dict(item)) for item in overview.get("history", [])]
    overview.pop("actions", None)
    return overview


def _filtered_graph(
    graph: dict[str, Any],
    *,
    status: str | None = None,
    horizon: str | None = None,
    node_type: str | None = None,
    query: str | None = None,
    limit: int = 250,
) -> dict[str, Any]:
    normalized_status = None if not status else status.upper()
    normalized_horizon = None if not horizon else horizon.upper()
    normalized_query = (query or "").strip().lower()
    nodes = []
    for node in graph.get("nodes", []):
        if normalized_status and str(node.get("information_status", "")) != normalized_status:
            continue
        if normalized_horizon and str(node.get("horizon", "")) != normalized_horizon:
            continue
        if node_type and str(node.get("node_type", "")) != node_type:
            continue
        haystack = " ".join(
            str(node.get(key, "")) for key in ("node_id", "name", "description", "node_type")
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        nodes.append(node)
    node_ids = {str(node["node_id"]) for node in nodes}
    edges = [
        edge
        for edge in graph.get("edges", [])
        if str(edge.get("from_id")) in node_ids and str(edge.get("to_id")) in node_ids
    ]
    return {
        "graph_type": graph.get("graph_type", ""),
        "atlas_version": graph.get("atlas_version"),
        "nodes": nodes[: max(1, min(limit, 500))],
        "edges": edges[: max(1, min(limit * 2, 1000))],
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }


def atlas_graph_view(
    database: Database,
    book_id: str,
    edition_id: str,
    graph_type: str,
    *,
    status: str | None = None,
    horizon: str | None = None,
    node_type: str | None = None,
    query: str | None = None,
    limit: int = 250,
) -> dict[str, Any]:
    if graph_type not in GRAPH_TYPES:
        raise AtlasError(f"不支持的 Atlas graph_type：{graph_type}")
    if status and status.upper() not in INFORMATION_STATUSES:
        raise AtlasError(f"不支持的 information_status：{status}")
    if horizon and horizon.upper() not in HORIZONS:
        raise AtlasError(f"不支持的 horizon：{horizon}")
    overview = get_atlas_overview(database, book_id, edition_id)
    if not overview.get("available"):
        return {"available": False, "graph_type": graph_type, "nodes": [], "edges": []}
    graph = dict(overview.get("graphs", {}).get(graph_type, {}))
    if not graph:
        return {
            "available": True,
            "graph_type": graph_type,
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
            "readiness": overview.get("readiness"),
        }
    return {
        "available": True,
        "atlas": _public_index(dict(overview["index"])),
        "readiness": overview.get("readiness"),
        **_filtered_graph(
            graph,
            status=status,
            horizon=horizon,
            node_type=node_type,
            query=query,
            limit=limit,
        ),
    }


def atlas_entry_detail(
    database: Database,
    book_id: str,
    edition_id: str,
    graph_type: str,
    entry_id: str,
) -> dict[str, Any]:
    view = atlas_graph_view(database, book_id, edition_id, graph_type, limit=500)
    node = next(
        (item for item in view.get("nodes", []) if str(item.get("node_id")) == entry_id), None
    )
    if node is None:
        raise AtlasError(f"Atlas 节点不存在：{entry_id}")
    edges = [
        edge
        for edge in view.get("edges", [])
        if str(edge.get("from_id")) == entry_id or str(edge.get("to_id")) == entry_id
    ]
    return {
        "atlas": view.get("atlas"),
        "readiness": view.get("readiness"),
        "node": node,
        "edges": edges,
    }


def atlas_context(
    database: Database,
    book_id: str,
    edition_id: str,
    *,
    view: str = "overview",
    status: str | None = None,
    horizon: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    overview = public_atlas_overview(database, book_id, edition_id)
    graph = None
    if view in GRAPH_TYPES:
        graph = atlas_graph_view(
            database,
            book_id,
            edition_id,
            view,
            status=status,
            horizon=horizon,
            query=query,
        )
    return {
        "book_id": book_id,
        "edition_id": edition_id,
        "view": view,
        "status": status,
        "horizon": horizon,
        "q": query,
        "overview": overview,
        "graph": graph,
        "graph_types": sorted(GRAPH_TYPES),
        "information_statuses": sorted(INFORMATION_STATUSES),
        "horizons": sorted(HORIZONS),
    }
