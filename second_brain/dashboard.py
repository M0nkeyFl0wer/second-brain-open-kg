"""
FastAPI dashboard for the open-second-brain knowledge graph.

Serves JSON API endpoints for graph status, type distributions, graph
visualization data, entity expansion, hidden connections, community
summaries, and search. Also serves a static HTML page at the root.

Run standalone:
    python -m second_brain.dashboard
    # or: uvicorn second_brain.dashboard:app --host 0.0.0.0 --port 7700

All endpoints return JSON and degrade gracefully — empty results rather
than 500 errors — so the frontend always has something to render.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from second_brain.graph import Graph
from second_brain.ontology import Ontology
from second_brain.queries import QUERIES

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Open Second Brain Dashboard",
    description="Live knowledge graph dashboard API",
    version="0.1.0",
)

# CORS — allow local dev servers (Vite, plain file://, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global graph + ontology instances, initialized at startup
# ---------------------------------------------------------------------------

graph: Optional[Graph] = None
ontology: Optional[Ontology] = None


@app.on_event("startup")
def _startup():
    """Initialize Graph and Ontology once when the server boots."""
    global graph, ontology
    ontology = Ontology()
    graph = Graph(ontology=ontology)


@app.on_event("shutdown")
def _shutdown():
    """Clean up the database connection on exit."""
    global graph
    if graph:
        graph.close()
        graph = None


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

# Resolve the static directory relative to this file's location.
_STATIC_DIR = Path(__file__).parent.parent / "static"


@app.get("/", include_in_schema=False)
def serve_index():
    """Serve the single-page dashboard HTML."""
    index_path = _STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse(
        {"error": "index.html not found — place it in second_brain/static/"},
        status_code=404,
    )


# Mount static directory for CSS/JS/images referenced by index.html.
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Helper: safe query wrapper
# ---------------------------------------------------------------------------

def _safe_query(cypher: str, parameters: dict = None, fallback=None):
    """Run a Cypher query; return *fallback* on any error instead of raising."""
    try:
        return graph.query(cypher, parameters=parameters or {})
    except Exception:
        return fallback if fallback is not None else []


# ---------------------------------------------------------------------------
# API: /api/status
# ---------------------------------------------------------------------------

@app.get("/api/status")
def api_status():
    """
    Graph health snapshot.

    Returns entity/edge/document/edge-node/community counts, last ingestion
    timestamp, and ontology health metrics (ICR, IPR, CI).
    """
    try:
        entities = graph.entity_count()
        edges = graph.edge_count()
        docs = graph.document_count()

        # Edge-node count
        r = _safe_query(QUERIES["edge_node_count"])
        edge_node_count = r[0]["cnt"] if r else 0

        # Community count
        r = _safe_query(QUERIES["community_count"])
        community_count = r[0]["cnt"] if r else 0

        # Last ingestion timestamp
        last_ingestion = None
        r = _safe_query(
            "MATCH (d:Document) RETURN d.ingested_at AS t ORDER BY t DESC LIMIT 1"
        )
        if r and r[0].get("t"):
            last_ingestion = datetime.fromtimestamp(r[0]["t"]).isoformat()

        # ---- Ontology health metrics ----

        # Type distribution (needed for ICR and CI)
        type_dist = _safe_query(QUERIES["type_distribution"])
        edge_dist = _safe_query(QUERIES["edge_type_distribution"])

        declared_types = set(ontology.entity_type_names)
        declared_edges = set(ontology.edge_type_names)
        populated_types = {row["type"] for row in type_dist} if type_dist else set()
        populated_edges = {row["type"] for row in edge_dist} if edge_dist else set()

        # ICR — Instantiated Class Ratio: fraction of declared entity types
        # that actually appear in the graph. Higher is better.
        icr = (
            len(populated_types & declared_types) / len(declared_types)
            if declared_types else 0
        )

        # IPR — Instantiated Property Ratio: same idea for edge types.
        ipr = (
            len(populated_edges & declared_edges) / len(declared_edges)
            if declared_edges else 0
        )

        # CI — Concentration Index: proportion of the most-common entity type.
        # Lower is healthier (indicates type diversity).
        ci = 0.0
        ci_dominant = ""
        if type_dist and entities > 0:
            ci = type_dist[0]["cnt"] / entities
            ci_dominant = type_dist[0]["type"]

        return {
            "entity_count": entities,
            "edge_count": edges,
            "doc_count": docs,
            "edge_node_count": edge_node_count,
            "community_count": community_count,
            "last_ingestion": last_ingestion,
            "icr": round(icr, 4),
            "ipr": round(ipr, 4),
            "ci": round(ci, 4),
            "ci_dominant": ci_dominant,
        }

    except Exception as exc:
        return JSONResponse(
            {"error": str(exc), "entity_count": 0, "edge_count": 0,
             "doc_count": 0, "edge_node_count": 0, "community_count": 0,
             "last_ingestion": None, "icr": 0, "ipr": 0, "ci": 0,
             "ci_dominant": ""},
            status_code=200,  # degrade gracefully — no 500
        )


# ---------------------------------------------------------------------------
# API: /api/types
# ---------------------------------------------------------------------------

@app.get("/api/types")
def api_types():
    """
    Entity and edge type distributions.

    Each entry includes the type name, count, and percentage of total.
    """
    try:
        entities = graph.entity_count()
        edges = graph.edge_count()

        type_rows = _safe_query(QUERIES["type_distribution"])
        edge_rows = _safe_query(QUERIES["edge_type_distribution"])

        type_distribution = [
            {
                "type": row["type"],
                "count": row["cnt"],
                "percentage": round(row["cnt"] / entities * 100, 2) if entities else 0,
            }
            for row in (type_rows or [])
        ]

        edge_distribution = [
            {
                "type": row["type"],
                "count": row["cnt"],
                "percentage": round(row["cnt"] / edges * 100, 2) if edges else 0,
            }
            for row in (edge_rows or [])
        ]

        return {
            "type_distribution": type_distribution,
            "edge_distribution": edge_distribution,
        }

    except Exception as exc:
        return JSONResponse(
            {"error": str(exc), "type_distribution": [], "edge_distribution": []},
            status_code=200,
        )


# ---------------------------------------------------------------------------
# API: /api/graph
# ---------------------------------------------------------------------------

_MAX_GRAPH_NODES = 500


@app.get("/api/graph")
def api_graph(
    type: Optional[str] = Query(None, description="Filter nodes by entity_type"),
    skeleton: bool = Query(False, description="Reduce edges via skeleton extraction"),
):
    """
    Full graph data for vis-network rendering.

    Returns up to 500 nodes (top by degree) and their edges. When
    ``skeleton=true``, uses topology.extract_skeleton to prune edges
    for readability. An optional ``type`` filter limits to a single
    entity type.
    """
    try:
        # Fetch all entities (optionally filtered by type).
        if type:
            nodes_raw = _safe_query(
                "MATCH (e:Entity {entity_type: $etype}) "
                "RETURN e.id AS id, e.label AS label, "
                "e.entity_type AS type, e.confidence AS confidence",
                parameters={"etype": type},
            )
        else:
            nodes_raw = _safe_query(
                "MATCH (e:Entity) "
                "RETURN e.id AS id, e.label AS label, "
                "e.entity_type AS type, e.confidence AS confidence"
            )

        if not nodes_raw:
            return {"nodes": [], "edges": []}

        # Fetch all RELATES_TO edges.
        edges_raw = _safe_query(
            "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
            "RETURN a.id AS source, b.id AS target, "
            "r.edge_type AS type, r.weight AS weight"
        )

        # Build a node-id set for filtering edges to visible nodes only.
        node_ids = {n["id"] for n in nodes_raw}

        # Compute degree for each node (within visible set) to rank them.
        degree = {nid: 0 for nid in node_ids}
        for e in (edges_raw or []):
            if e["source"] in degree:
                degree[e["source"]] += 1
            if e["target"] in degree:
                degree[e["target"]] += 1

        # Cap at MAX_GRAPH_NODES, keeping highest-degree nodes.
        if len(nodes_raw) > _MAX_GRAPH_NODES:
            top_ids = set(
                sorted(degree, key=lambda nid: -degree[nid])[:_MAX_GRAPH_NODES]
            )
            nodes_raw = [n for n in nodes_raw if n["id"] in top_ids]
            node_ids = top_ids

        # Filter edges to only those connecting visible nodes.
        edges_filtered = [
            e for e in (edges_raw or [])
            if e["source"] in node_ids and e["target"] in node_ids
        ]

        # Optional skeleton mode: reduce edges for cleaner visualization.
        if skeleton:
            try:
                from second_brain.topology import extract_skeleton, build_networkx_graph
                import networkx as nx

                # Build a temporary NetworkX graph from the filtered data.
                G = nx.Graph()
                for n in nodes_raw:
                    G.add_node(n["id"], label=n["label"], type=n["type"])
                for e in edges_filtered:
                    G.add_edge(
                        e["source"], e["target"],
                        type=e["type"], weight=e.get("weight", 1.0),
                    )

                S = extract_skeleton(G, max_edges=200)

                # Rebuild edges from skeleton.
                edges_filtered = [
                    {
                        "source": u,
                        "target": v,
                        "type": data.get("type", ""),
                        "weight": data.get("weight", 1.0),
                    }
                    for u, v, data in S.edges(data=True)
                ]
            except Exception:
                pass  # fall through with unfiltered edges

        # Build response.
        nodes_out = [
            {
                "id": n["id"],
                "label": n["label"],
                "type": n["type"],
                "confidence": n.get("confidence", 0.5),
            }
            for n in nodes_raw
        ]

        edges_out = [
            {
                "source": e["source"],
                "target": e["target"],
                "type": e["type"],
                "weight": e.get("weight", 1.0),
            }
            for e in edges_filtered
        ]

        return {"nodes": nodes_out, "edges": edges_out}

    except Exception as exc:
        return JSONResponse(
            {"error": str(exc), "nodes": [], "edges": []},
            status_code=200,
        )


# ---------------------------------------------------------------------------
# API: /api/graph/{entity_id}  —  1-hop entity expansion
# ---------------------------------------------------------------------------

@app.get("/api/graph/{entity_id}")
def api_entity_expand(entity_id: str):
    """
    Entity details plus all 1-hop neighbors.

    Traverses RELATES_TO edges (both directions) as well as the
    CONNECTS -> EdgeNode -> BINDS hypergraph path.
    """
    try:
        # Fetch the entity itself.
        entity_rows = _safe_query(
            "MATCH (e:Entity {id: $eid}) "
            "RETURN e.id AS id, e.label AS label, "
            "e.entity_type AS type, e.description AS description",
            parameters={"eid": entity_id},
        )

        if not entity_rows:
            return JSONResponse(
                {"error": "Entity not found", "entity": None, "neighbors": []},
                status_code=404,
            )

        entity = entity_rows[0]

        # Collect neighbors via RELATES_TO (outgoing).
        outgoing = _safe_query(
            "MATCH (a:Entity {id: $eid})-[r:RELATES_TO]->(b:Entity) "
            "RETURN b.id AS id, b.label AS label, "
            "b.entity_type AS type, r.edge_type AS edge_type",
            parameters={"eid": entity_id},
        )

        # Collect neighbors via RELATES_TO (incoming).
        incoming = _safe_query(
            "MATCH (b:Entity)-[r:RELATES_TO]->(a:Entity {id: $eid}) "
            "RETURN b.id AS id, b.label AS label, "
            "b.entity_type AS type, r.edge_type AS edge_type",
            parameters={"eid": entity_id},
        )

        # Collect neighbors via EdgeNode (CONNECTS -> EdgeNode -> BINDS).
        via_edge_fwd = _safe_query(
            "MATCH (a:Entity {id: $eid})-[:CONNECTS]->(en:EdgeNode)-[:BINDS]->(b:Entity) "
            "RETURN b.id AS id, b.label AS label, "
            "b.entity_type AS type, en.semantic_type AS edge_type",
            parameters={"eid": entity_id},
        )

        # Reverse direction: entity is a BINDS target.
        via_edge_rev = _safe_query(
            "MATCH (b:Entity)-[:CONNECTS]->(en:EdgeNode)-[:BINDS]->(a:Entity {id: $eid}) "
            "RETURN b.id AS id, b.label AS label, "
            "b.entity_type AS type, en.semantic_type AS edge_type",
            parameters={"eid": entity_id},
        )

        # Merge and deduplicate neighbors by id.
        seen = set()
        neighbors = []
        for row in (outgoing or []) + (incoming or []) + (via_edge_fwd or []) + (via_edge_rev or []):
            if row["id"] not in seen:
                seen.add(row["id"])
                neighbors.append({
                    "id": row["id"],
                    "label": row["label"],
                    "type": row["type"],
                    "edge_type": row.get("edge_type", ""),
                })

        return {
            "entity": {
                "id": entity["id"],
                "label": entity["label"],
                "type": entity["type"],
                "description": entity.get("description", ""),
            },
            "neighbors": neighbors,
        }

    except Exception as exc:
        return JSONResponse(
            {"error": str(exc), "entity": None, "neighbors": []},
            status_code=200,
        )


# ---------------------------------------------------------------------------
# API: /api/hidden
# ---------------------------------------------------------------------------

@app.get("/api/hidden")
def api_hidden():
    """
    Top 50 hidden connections in the graph.

    Hidden connections are entity pairs that are close in embedding space
    (semantically similar) but have no structural link in the graph.
    """
    try:
        from second_brain.hidden_connections import find_hidden_connections

        results = find_hidden_connections(graph, top_n=50)

        return [
            {
                "source_label": r["source_label"],
                "target_label": r["target_label"],
                "source_type": r["source_type"],
                "target_type": r["target_type"],
                "distance": r["distance"],
            }
            for r in results
        ]

    except Exception as exc:
        # Hidden connections require embeddings + HNSW index.
        # Return empty list if unavailable rather than erroring.
        return JSONResponse([], status_code=200)


# ---------------------------------------------------------------------------
# API: /api/communities
# ---------------------------------------------------------------------------

@app.get("/api/communities")
def api_communities():
    """
    Pre-computed community summaries from CommunityMeta nodes.

    Each community has an ID, size, LLM-generated summary, and a list of
    top entities (stored as a comma-separated string in the graph).
    """
    try:
        rows = _safe_query(
            "MATCH (c:CommunityMeta) "
            "RETURN c.community_id AS community_id, c.size AS size, "
            "c.summary AS summary, c.top_entities AS top_entities "
            "ORDER BY c.size DESC"
        )

        return [
            {
                "community_id": row["community_id"],
                "size": row["size"],
                "summary": row.get("summary", ""),
                # top_entities is stored as a comma-separated string.
                "top_entities": (
                    [s.strip() for s in row["top_entities"].split(",")]
                    if row.get("top_entities") else []
                ),
            }
            for row in (rows or [])
        ]

    except Exception as exc:
        return JSONResponse([], status_code=200)


# ---------------------------------------------------------------------------
# API: /api/search
# ---------------------------------------------------------------------------

@app.get("/api/search")
def api_search(
    q: str = Query("", description="Search query string"),
    mode: str = Query("keyword", description="Search mode: keyword, semantic, or hybrid"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
):
    """
    Unified search endpoint.

    Modes:
      - keyword:  Cypher CONTAINS match on entity labels.
      - semantic: Embed the query via Ollama, then vector search.
      - hybrid:   Reciprocal Rank Fusion of keyword + semantic results.
    """
    if not q:
        return []

    try:
        if mode == "semantic":
            # Embed the query text, then vector-search the graph.
            from second_brain.embed import embed_text

            emb = embed_text(q)
            raw = graph.vector_search(emb, limit=limit)
            return [
                {
                    "id": r["id"],
                    "label": r["label"],
                    "type": r.get("type", ""),
                    "score": r.get("score", 0),
                }
                for r in raw
            ]

        elif mode == "hybrid":
            # Hybrid search: merge keyword + semantic via RRF.
            # Reuse the logic from the search CLI script.
            from second_brain.embed import embed_text

            RRF_K = 60

            # Keyword leg.
            keyword_results = _safe_query(
                QUERIES["entity_by_label"],
                parameters={"query": q, "limit": limit * 2},
            )

            # Semantic leg.
            emb = embed_text(q)
            semantic_results = graph.vector_search(emb, limit=limit * 2)

            # Reciprocal Rank Fusion.
            rrf_scores: dict[str, float] = {}
            entity_data: dict[str, dict] = {}

            for rank, r in enumerate(keyword_results or [], start=1):
                eid = r["id"]
                rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (RRF_K + rank)
                entity_data[eid] = r

            for rank, r in enumerate(semantic_results or [], start=1):
                eid = r["id"]
                rrf_scores[eid] = rrf_scores.get(eid, 0) + 1.0 / (RRF_K + rank)
                if eid not in entity_data:
                    entity_data[eid] = r

            sorted_ids = sorted(rrf_scores, key=lambda x: -rrf_scores[x])

            return [
                {
                    "id": eid,
                    "label": entity_data[eid].get("label", ""),
                    "type": entity_data[eid].get("type", ""),
                    "score": round(rrf_scores[eid], 4),
                }
                for eid in sorted_ids[:limit]
            ]

        else:
            # Default: keyword search via Cypher CONTAINS.
            raw = _safe_query(
                QUERIES["entity_by_label"],
                parameters={"query": q, "limit": limit},
            )
            return [
                {
                    "id": r["id"],
                    "label": r["label"],
                    "type": r.get("type", ""),
                    "score": r.get("confidence", 0),
                }
                for r in (raw or [])
            ]

    except Exception as exc:
        return JSONResponse(
            {"error": str(exc), "results": []},
            status_code=200,
        )


# ---------------------------------------------------------------------------
# Path traversal — visualize multi-hop reasoning chains
# ---------------------------------------------------------------------------

@app.get("/api/path")
def api_path(source: str = "", target: str = "", max_hops: int = 4):
    """
    Find and return paths between two entities for traversal visualization.
    Each path includes: ordered node list, edge types, per-hop confidence,
    and overall path confidence. The frontend animates these hop-by-hop
    to illustrate how the graph answers "how does X relate to Y?"

    Query params:
        source: label substring to match source entity
        target: label substring to match target entity
        max_hops: maximum traversal depth (1-6, default 4)
    """
    if not source or not target:
        return {"paths": [], "error": "Provide both source and target"}

    max_hops = max(1, min(6, max_hops))

    try:
        paths = graph.find_path(source, target, max_hops=max_hops)

        # Enrich each path with per-hop detail for animation
        enriched = []
        for p in paths[:5]:  # Cap at 5 paths
            hops = []
            for i, label in enumerate(p["node_labels"]):
                hop = {"label": label}
                if i < len(p["edge_types"]):
                    hop["edge_to_next"] = p["edge_types"][i]
                hops.append(hop)

            enriched.append({
                "hops": hops,
                "node_labels": p["node_labels"],
                "edge_types": p["edge_types"],
                "path_confidence": p["path_confidence"],
                "hop_count": len(p["edge_types"]),
            })

        return {
            "source": source,
            "target": target,
            "max_hops": max_hops,
            "paths": enriched,
            "path_count": len(enriched),
        }

    except Exception as exc:
        return {"paths": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7700)
