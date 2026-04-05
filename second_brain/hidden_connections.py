"""
Hidden connections engine — the core differentiator for a second brain tool.

Finds entity pairs that are semantically similar (close in embedding space)
but structurally disconnected (no direct edges in the graph). These are the
ideas your brain hasn't linked yet — the "you should look at these together"
moments that make a knowledge graph worth maintaining.

Algorithm:
  1. For each entity that has an embedding, query the HNSW vector index
     to retrieve its nearest neighbors in embedding space.
  2. Filter out any neighbor that is already directly connected via
     RELATES_TO, or indirectly via CONNECTS→EdgeNode→BINDS.
  3. Keep pairs whose cosine distance falls below the threshold
     (lower distance = higher similarity = stronger hidden connection).
  4. Deduplicate symmetric pairs (A↔B and B↔A are the same connection).
  5. Rank by distance ascending (closest first) and return top N.

Why cosine distance instead of similarity?
  The HNSW vector index returns cosine distance natively. Working in distance
  space avoids a redundant 1-d conversion on every row. A threshold of 0.3
  in distance space is equivalent to 0.7 in similarity space.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import config

if TYPE_CHECKING:
    from .graph import Graph


# ---------------------------------------------------------------------------
# Cypher fragments
# ---------------------------------------------------------------------------

# Check whether two entities share any direct structural link.
# Covers three connection patterns:
#   1. Direct RELATES_TO edge (either direction)
#   2. Shared EdgeNode: Entity -CONNECTS-> EdgeNode -BINDS-> Entity
#   3. Shared EdgeNode reverse: Entity <-BINDS- EdgeNode <-CONNECTS- Entity
_CONNECTED_CHECK = """
    MATCH (a:Entity {id: $src})-[:RELATES_TO]-(b:Entity {id: $tgt})
    RETURN 1 AS connected
    LIMIT 1
"""

# Fetch a single entity's embedding by ID.
_GET_EMBEDDING = """
    MATCH (e:Entity {id: $eid})
    WHERE e.embedding IS NOT NULL
    RETURN e.embedding AS emb
"""

# Fetch all entities that have embeddings (for the global scan).
_ALL_EMBEDDED_ENTITIES = """
    MATCH (e:Entity)
    WHERE e.embedding IS NOT NULL
    RETURN e.id AS id, e.label AS label,
           e.entity_type AS type, e.embedding AS emb
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_hidden_connections(
    graph: "Graph",
    top_n: int = 20,
    threshold: float | None = None,
) -> list[dict]:
    """Find semantically similar but unlinked entity pairs across the graph.

    Scans every embedded entity, queries its HNSW neighborhood, and filters
    out pairs that already share a structural link. What remains are the
    "hidden connections" — ideas that live close together in meaning space
    but have never been explicitly linked.

    Args:
        graph:     Graph instance (must have HNSW index built).
        top_n:     Maximum number of hidden connections to return.
        threshold: Maximum cosine distance to consider. Defaults to
                   ``1 - config.HIDDEN_CONNECTION_THRESHOLD`` (0.3).

    Returns:
        List of dicts sorted by distance (ascending), each containing:
            source_id, source_label, source_type,
            target_id, target_label, target_type,
            distance
    """
    if threshold is None:
        # Config stores similarity (0.7); convert to distance (0.3).
        threshold = 1.0 - config.HIDDEN_CONNECTION_THRESHOLD

    candidates_k = config.HIDDEN_CONNECTION_CANDIDATES

    # Step 1: Load all entities that have embeddings.
    entities = graph.query(_ALL_EMBEDDED_ENTITIES)
    if not entities:
        return []

    # Build a lookup for labels/types so we can annotate results cheaply.
    entity_meta: dict[str, dict] = {
        e["id"]: {"label": e["label"], "type": e["type"]}
        for e in entities
    }

    # Step 2: For each entity, find nearest neighbors via HNSW.
    # Collect candidate pairs, keyed as frozenset({id_a, id_b}) to dedupe.
    seen_pairs: dict[frozenset, float] = {}

    for entity in entities:
        eid = entity["id"]
        emb = entity["emb"]

        neighbors = _hnsw_neighbors(graph, emb, candidates_k)

        for neighbor in neighbors:
            nid = neighbor["id"]

            # Skip self-matches.
            if nid == eid:
                continue

            # Skip if distance exceeds threshold.
            dist = neighbor["distance"]
            if dist > threshold:
                continue

            # Deduplicate: keep the smallest distance seen for each pair.
            pair_key = frozenset({eid, nid})
            if pair_key in seen_pairs and seen_pairs[pair_key] <= dist:
                continue
            seen_pairs[pair_key] = dist

    # Step 3: Filter out pairs that are already structurally connected.
    hidden: list[dict] = []

    for pair_key, dist in sorted(seen_pairs.items(), key=lambda kv: kv[1]):
        ids = list(pair_key)
        src_id, tgt_id = ids[0], ids[1]

        if _are_connected(graph, src_id, tgt_id):
            continue

        src_meta = entity_meta.get(src_id, {"label": src_id, "type": ""})
        tgt_meta = entity_meta.get(tgt_id, {"label": tgt_id, "type": ""})

        hidden.append({
            "source_id": src_id,
            "source_label": src_meta["label"],
            "source_type": src_meta["type"],
            "target_id": tgt_id,
            "target_label": tgt_meta["label"],
            "target_type": tgt_meta["type"],
            "distance": round(dist, 4),
        })

        if len(hidden) >= top_n:
            break

    return hidden


def find_hidden_for_entity(
    graph: "Graph",
    entity_id: str,
    candidates: int = 20,
    threshold: float | None = None,
) -> list[dict]:
    """Find hidden connections for a specific entity.

    Answers the question: "What else in my knowledge graph connects to this
    idea that I haven't noticed yet?"

    Args:
        graph:      Graph instance (must have HNSW index built).
        entity_id:  The id of the entity to find hidden connections for.
        candidates: Number of nearest neighbors to retrieve from the index.
        threshold:  Maximum cosine distance. Defaults to
                    ``1 - config.HIDDEN_CONNECTION_THRESHOLD``.

    Returns:
        List of dicts sorted by distance (ascending), each containing:
            target_id, target_label, target_type, distance
    """
    if threshold is None:
        threshold = 1.0 - config.HIDDEN_CONNECTION_THRESHOLD

    # Fetch the entity's embedding.
    rows = graph.query(_GET_EMBEDDING, parameters={"eid": entity_id})
    if not rows:
        return []
    emb = rows[0]["emb"]

    # Query HNSW for nearest neighbors.
    neighbors = _hnsw_neighbors(graph, emb, candidates)

    hidden: list[dict] = []
    for neighbor in neighbors:
        nid = neighbor["id"]

        # Skip self.
        if nid == entity_id:
            continue

        # Skip beyond threshold.
        dist = neighbor["distance"]
        if dist > threshold:
            continue

        # Skip if already structurally connected.
        if _are_connected(graph, entity_id, nid):
            continue

        hidden.append({
            "target_id": nid,
            "target_label": neighbor["label"],
            "target_type": neighbor["type"],
            "distance": round(dist, 4),
        })

    # Already sorted by distance (HNSW returns ordered results).
    return hidden


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hnsw_neighbors(
    graph: "Graph",
    embedding: list[float],
    k: int,
) -> list[dict]:
    """Query the HNSW vector index for the k nearest Entity neighbors.

    Falls back to brute-force cosine similarity if the index is unavailable
    (e.g., not yet built via ``graph.rebuild_vector_indexes()``).

    Returns:
        List of dicts with keys: id, label, type, distance.
    """
    # Try the HNSW index first — fast O(log n) lookup.
    try:
        result = graph.conn.execute(
            """
            CALL QUERY_VECTOR_INDEX('Entity', 'entity_vec', $emb, $k)
            RETURN node.id AS id, node.label AS label,
                   node.entity_type AS type, distance
            """,
            parameters={"emb": embedding, "k": k},
        )
        columns = result.get_column_names()
        rows = []
        while result.has_next():
            row = result.get_next()
            rows.append(dict(zip(columns, row)))
        if rows:
            return rows
    except Exception:
        pass

    # Fallback: brute-force scan. Slower but always works.
    # Computes cosine similarity, then converts to distance for consistency.
    result = graph.query(
        """
        MATCH (e:Entity)
        WHERE e.embedding IS NOT NULL
        WITH e, array_cosine_similarity(e.embedding, $emb) AS sim
        ORDER BY sim DESC
        LIMIT $k
        RETURN e.id AS id, e.label AS label,
               e.entity_type AS type, (1.0 - sim) AS distance
        """,
        parameters={"emb": embedding, "k": k},
    )
    return result


def _are_connected(graph: "Graph", src_id: str, tgt_id: str) -> bool:
    """Check if two entities share any direct structural link.

    Tests three patterns:
      - Direct RELATES_TO edge (either direction)
      - Forward edge-node path: src -CONNECTS-> EdgeNode -BINDS-> tgt
      - Reverse edge-node path: tgt -CONNECTS-> EdgeNode -BINDS-> src
    """
    # Check direct RELATES_TO edge
    rows = graph.query(
        _CONNECTED_CHECK,
        parameters={"src": src_id, "tgt": tgt_id},
    )
    if rows:
        return True

    # Check edge-node path: src→CONNECTS→EdgeNode→BINDS→tgt (either direction)
    en_rows = graph.query("""
        MATCH (a:Entity {id: $src})-[:CONNECTS]->(en:EdgeNode)-[:BINDS]->(b:Entity {id: $tgt})
        RETURN 1 AS connected LIMIT 1
    """, parameters={"src": src_id, "tgt": tgt_id})
    if en_rows:
        return True

    en_rows2 = graph.query("""
        MATCH (a:Entity {id: $tgt})-[:CONNECTS]->(en:EdgeNode)-[:BINDS]->(b:Entity {id: $src})
        RETURN 1 AS connected LIMIT 1
    """, parameters={"src": src_id, "tgt": tgt_id})
    return bool(en_rows2)
