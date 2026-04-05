"""
Pre-compute community summaries using LadybugDB's native Louvain algorithm.

This module runs Louvain community detection on the Entity/RELATES_TO projected
graph, then stores each community's summary as a CommunityMeta node with an
embedding vector. The result is a "zoom out" layer: broad questions query
community summaries instead of individual entities, giving thematic answers
without scanning the entire graph.

Flow:
  1. Project a subgraph of Entity nodes and RELATES_TO edges
  2. Run native Louvain (faster than NetworkX, runs inside the DB engine)
  3. For each community above the size threshold, compute a summary from
     the top-5 entities by degree
  4. Embed each summary and MERGE it as a CommunityMeta node
  5. Rebuild HNSW vector indexes so the summaries are searchable

Usage:
    from second_brain.graph import Graph
    from second_brain.community_summaries import compute_community_summaries, search_communities

    g = Graph()
    communities = compute_community_summaries(g)
    results = search_communities(g, query_embedding, limit=5)
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from second_brain import config
from second_brain.embed import embed_text

if TYPE_CHECKING:
    from second_brain.graph import Graph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_community_summaries(
    graph: Graph,
    min_community_size: int | None = None,
) -> list[dict]:
    """
    Detect communities via native Louvain and store summaries as CommunityMeta nodes.

    Steps:
        1. Create a projected graph over Entity nodes and RELATES_TO edges.
        2. Run Louvain to get community assignments.
        3. For each community >= min_community_size:
           a. Find the top-5 entities by degree within the community.
           b. Concatenate their labels and descriptions into a summary string.
           c. Embed the summary via embed_text().
           d. MERGE a CommunityMeta node with the summary and embedding.
        4. Drop the projected graph (session-scoped resource).
        5. Rebuild HNSW vector indexes on CommunityMeta so summaries
           are immediately searchable.

    Args:
        graph: An open Graph instance (LadybugDB-backed).
        min_community_size: Ignore communities smaller than this.
            Defaults to config.MIN_COMMUNITY_SIZE (3).

    Returns:
        List of dicts, one per stored community:
        [{"id": "community_0", "size": 12, "top_entities": "...", "summary": "..."}, ...]
    """
    if min_community_size is None:
        min_community_size = config.MIN_COMMUNITY_SIZE

    # Ensure the algo extension is loaded (idempotent; Graph.__init__ does this
    # too, but belt-and-suspenders for standalone usage).
    _ensure_algo_extension(graph)

    # ------------------------------------------------------------------
    # 0. Clear stale CommunityMeta nodes before recomputing
    # ------------------------------------------------------------------
    graph.conn.execute("MATCH (c:CommunityMeta) DETACH DELETE c")
    logger.info("Cleared existing CommunityMeta nodes")

    # ------------------------------------------------------------------
    # 1. Create projected graph
    # ------------------------------------------------------------------
    proj_name = "PKG"
    try:
        graph.conn.execute(f"CALL DROP_PROJECTED_GRAPH('{proj_name}')")
    except Exception:
        pass  # No existing projection to drop

    logger.info("Projecting Entity/RELATES_TO graph for Louvain...")
    graph.conn.execute(
        f"CALL PROJECT_GRAPH('{proj_name}', ['Entity'], ['RELATES_TO'])"
    )

    # ------------------------------------------------------------------
    # 2-4. Run Louvain, process communities, and ensure projected graph cleanup
    # ------------------------------------------------------------------
    stored: list[dict] = []
    try:
        # 2. Run Louvain community detection
        logger.info("Running native Louvain community detection...")
        raw_communities = graph.query(
            f"CALL louvain('{proj_name}') "
            "RETURN louvain_id, collect(node.id) AS member_ids, count(*) AS size"
        )

        # Filter by minimum size
        communities = [
            c for c in raw_communities
            if c["size"] >= min_community_size
        ]
        logger.info(
            "Louvain found %d communities total, %d with size >= %d",
            len(raw_communities), len(communities), min_community_size,
        )

        # 3. For each qualifying community, build summary and store
        now = int(time.time())

        for comm in communities:
            comm_id: int = comm["louvain_id"]
            member_ids: list[str] = comm["member_ids"]
            size: int = comm["size"]
            node_id = f"community_{comm_id}"

            # 3a. Get top-5 entities by degree within this community.
            top_entities = _top_entities_by_degree(graph, member_ids, top_n=5)

            # 3b. Build a human-readable summary from entity labels + descriptions.
            top_labels = [e["label"] for e in top_entities]
            top_entities_str = ", ".join(top_labels)

            summary = _build_summary_text(top_entities, size)

            # 3c. Embed the summary.
            embedding = embed_text(summary)

            # 3d. MERGE CommunityMeta node.  HNSW indexes are NOT active yet,
            #     so SET on the embedding column is safe here.
            graph.conn.execute(
                """
                MERGE (c:CommunityMeta {id: $id})
                SET c.community_id = $cid,
                    c.size         = $sz,
                    c.summary      = $summary,
                    c.top_entities = $top_ents,
                    c.computed_at  = $now,
                    c.embedding    = $emb
                """,
                parameters={
                    "id": node_id,
                    "cid": comm_id,
                    "sz": size,
                    "summary": summary,
                    "top_ents": top_entities_str,
                    "now": now,
                    "emb": embedding,
                },
            )

            stored.append({
                "id": node_id,
                "community_id": comm_id,
                "size": size,
                "top_entities": top_entities_str,
                "summary": summary,
            })
            logger.debug("Stored community %s (size=%d): %s", node_id, size, top_entities_str)
    finally:
        # 4. Drop the projected graph (free session-scoped memory)
        try:
            graph.conn.execute(f"CALL DROP_PROJECTED_GRAPH('{proj_name}')")
        except Exception:
            logger.warning("Could not drop projected graph '%s'", proj_name)

    # ------------------------------------------------------------------
    # 5. Rebuild HNSW vector indexes so community summaries are searchable
    # ------------------------------------------------------------------
    logger.info("Rebuilding vector indexes...")
    graph.rebuild_vector_indexes()

    logger.info("Stored %d community summaries.", len(stored))
    return stored


def search_communities(
    graph: Graph,
    query_embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    """
    Search community summaries by vector similarity.

    This is the "zoom out" operation: instead of matching individual entities,
    it finds the pre-computed community summaries closest to the query. Useful
    for broad questions like "What do I know about systems thinking?" where the
    answer spans many entities.

    Tries the HNSW index first for speed, then falls back to brute-force
    cosine similarity over all CommunityMeta nodes.

    Args:
        graph: An open Graph instance.
        query_embedding: 768-dim float vector for the query.
        limit: Maximum number of community results to return.

    Returns:
        List of dicts with keys: id, community_id, size, summary,
        top_entities, score (cosine distance or similarity).
    """
    # --- Attempt 1: HNSW index lookup (fast, O(log n)) ---
    try:
        result = graph.conn.execute(
            """
            CALL QUERY_VECTOR_INDEX('CommunityMeta', 'community_vec', $qemb, $lim)
            RETURN node.id          AS id,
                   node.community_id AS community_id,
                   node.size         AS size,
                   node.summary      AS summary,
                   node.top_entities AS top_entities,
                   distance          AS score
            """,
            parameters={"qemb": query_embedding, "lim": limit},
        )
        rows = _result_to_dicts(result)
        if rows:
            return rows
    except Exception:
        logger.debug("HNSW index lookup failed, falling back to brute force.")

    # --- Attempt 2: brute-force cosine similarity ---
    rows = graph.query(
        """
        MATCH (c:CommunityMeta)
        WHERE c.embedding IS NOT NULL
        WITH c, array_cosine_similarity(c.embedding, $qemb) AS score
        ORDER BY score DESC
        LIMIT $lim
        RETURN c.id          AS id,
               c.community_id AS community_id,
               c.size         AS size,
               c.summary      AS summary,
               c.top_entities AS top_entities,
               score
        """,
        parameters={"qemb": query_embedding, "lim": limit},
    )
    return rows


def get_community_members(graph: Graph, community_id: int) -> list[dict]:
    """
    Get all Entity members of a specific community.

    Re-runs Louvain on a fresh projection to find current membership.
    (Community assignments are not stored on Entity nodes -- they live only
    in CommunityMeta summaries and are recomputed each cycle.)

    Args:
        graph: An open Graph instance.
        community_id: The Louvain community ID to look up.

    Returns:
        List of entity dicts with keys: id, label, entity_type, description.
        Empty list if the community_id is not found.
    """
    _ensure_algo_extension(graph)

    proj_name = "PKG_MEMBERS"
    try:
        graph.conn.execute(f"CALL DROP_PROJECTED_GRAPH('{proj_name}')")
    except Exception:
        pass

    graph.conn.execute(
        f"CALL PROJECT_GRAPH('{proj_name}', ['Entity'], ['RELATES_TO'])"
    )

    # Run Louvain and filter to the requested community
    try:
        raw = graph.query(
            f"CALL louvain('{proj_name}') "
            "RETURN louvain_id, collect(node.id) AS member_ids "
        )
    finally:
        # Drop projection immediately -- we have the data we need
        try:
            graph.conn.execute(f"CALL DROP_PROJECTED_GRAPH('{proj_name}')")
        except Exception:
            logger.warning("Could not drop projected graph '%s'", proj_name)

    # Find the matching community
    member_ids: list[str] = []
    for row in raw:
        if row["louvain_id"] == community_id:
            member_ids = row["member_ids"]
            break

    if not member_ids:
        return []

    # Fetch full entity details for each member
    members: list[dict] = []
    for eid in member_ids:
        rows = graph.query(
            """
            MATCH (e:Entity {id: $eid})
            RETURN e.id          AS id,
                   e.label       AS label,
                   e.entity_type AS entity_type,
                   e.description AS description
            """,
            parameters={"eid": eid},
        )
        if rows:
            members.append(rows[0])

    return members


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_algo_extension(graph: Graph) -> None:
    """Load the algo extension if not already loaded."""
    try:
        graph.conn.execute("INSTALL algo; LOAD EXTENSION algo;")
    except Exception:
        pass  # Already loaded


def _top_entities_by_degree(
    graph: Graph,
    member_ids: list[str],
    top_n: int = 5,
) -> list[dict]:
    """
    Return the top-N entities (by RELATES_TO degree) from a list of member IDs.

    Queries each member's degree and returns them sorted descending.
    For small communities this is fine; for very large ones a single
    Cypher query with IN-list would be better, but LadybugDB doesn't
    support list parameters in WHERE ... IN yet.
    """
    entities: list[dict] = []
    for eid in member_ids:
        rows = graph.query(
            """
            MATCH (e:Entity {id: $eid})
            OPTIONAL MATCH (e)-[r:RELATES_TO]-()
            RETURN e.id          AS id,
                   e.label       AS label,
                   e.entity_type AS entity_type,
                   e.description AS description,
                   count(r)      AS degree
            """,
            parameters={"eid": eid},
        )
        if rows:
            entities.append(rows[0])

    # Sort by degree descending, take top N
    entities.sort(key=lambda e: e.get("degree", 0), reverse=True)
    return entities[:top_n]


def _build_summary_text(top_entities: list[dict], community_size: int) -> str:
    """
    Build a concise textual summary from the top entities of a community.

    The summary is designed for embedding: it should capture the thematic
    essence of the community so that vector similarity matches broad queries
    to the right community.
    """
    parts: list[str] = [
        f"Community of {community_size} related concepts."
    ]

    for ent in top_entities:
        label = ent.get("label", "")
        desc = ent.get("description", "")
        etype = ent.get("entity_type", "")

        if label and desc:
            parts.append(f"{label} ({etype}): {desc}")
        elif label:
            parts.append(f"{label} ({etype})")

    return " ".join(parts)


def _result_to_dicts(result) -> list[dict]:
    """Convert a raw LadybugDB result object to a list of dicts."""
    columns = result.get_column_names()
    rows: list[dict] = []
    while result.has_next():
        row = result.get_next()
        rows.append(dict(zip(columns, row)))
    return rows
