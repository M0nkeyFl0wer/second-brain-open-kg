"""
MCP server for open-second-brain agentic memory.

Exposes three high-level tools for LLM assistants:
- memory_write: Capture a thought, auto-classify, link to existing graph
- memory_zoom_out: Answer broad questions via community summaries
- memory_search: Hybrid search + graph expansion

Uses progressive disclosure — no Cypher exposed to the LLM.
The assistant describes what it wants in natural language,
and the tools handle all graph operations internally.

Run: python -m second_brain.mcp_server
Or configure in Claude Code settings as an MCP server.
"""
from __future__ import annotations

import logging
import traceback

# ---------------------------------------------------------------------------
# FastMCP import — try the mcp package first, fall back to standalone fastmcp
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP  # type: ignore[no-redef]

from second_brain.graph import Graph
from second_brain.ontology import Ontology
from second_brain.extract import Extractor, generate_entity_id
from second_brain.embed import embed_text

# Optional modules — graceful degradation if not available
try:
    from second_brain.community_summaries import search_communities
    _HAS_COMMUNITIES = True
except ImportError:
    _HAS_COMMUNITIES = False

try:
    from second_brain.hidden_connections import find_hidden_for_entity
    _HAS_HIDDEN = True
except ImportError:
    _HAS_HIDDEN = False


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server and shared state
# ---------------------------------------------------------------------------

mcp = FastMCP("second-brain")

# Lazy-initialized singletons. Created on first tool call so the server
# process starts fast and the graph directory is only opened when needed.
# Thread-safe via _init_lock (double-check locking pattern).
import atexit
import threading

_graph: Graph | None = None
_ontology: Ontology | None = None
_extractor: Extractor | None = None
_init_lock = threading.Lock()


def _init() -> tuple[Graph, Ontology, Extractor]:
    """Initialize (or return cached) Graph, Ontology, and Extractor.
    Thread-safe — uses double-check locking to avoid races on first call."""
    global _graph, _ontology, _extractor

    if _graph is not None:
        return _graph, _ontology, _extractor  # type: ignore[return-value]

    with _init_lock:
        if _graph is None:  # double-check after acquiring lock
            _ontology = Ontology()
            _graph = Graph(ontology=_ontology)
            _extractor = Extractor(_ontology)
            logger.info(
                "Initialized graph (%d entities, %d edges)",
                _graph.entity_count(),
                _graph.edge_count(),
            )

    return _graph, _ontology, _extractor  # type: ignore[return-value]


def _shutdown():
    """Clean up graph connection on process exit."""
    global _graph
    if _graph is not None:
        _graph.close()
        _graph = None
        logger.info("Graph connection closed")


atexit.register(_shutdown)


# ===========================================================================
# Tool 1: memory_write
# ===========================================================================

@mcp.tool()
def memory_write(thought: str, tags: list[str] | None = None) -> str:
    """Capture a thought, auto-classify it, and link it to the existing knowledge graph.

    The thought is run through the full extraction pipeline (deterministic,
    NLP, and LLM phases), entities and edges are stored in the graph, and
    embeddings are computed so the new knowledge is immediately searchable.

    Args:
        thought: Free-form text — a note, idea, observation, or reflection.
        tags: Optional list of tags to include as additional context for
              extraction. These are prepended to the thought text.

    Returns:
        A summary of what was stored and what it connected to.
    """
    try:
        graph, ontology, extractor = _init()

        # Prepend tags to give the extractor richer context
        full_text = thought
        if tags:
            tag_line = "Tags: " + ", ".join(tags)
            full_text = f"{tag_line}\n\n{thought}"

        # ----- Phase 1: Extract entities and edges -----
        result = extractor.extract_from_text(full_text, source_url="mcp_input")
        entities = result.get("entities", [])
        edges = result.get("edges", [])

        if not entities:
            return "No entities could be extracted from this thought. Try adding more detail."

        # ----- Phase 2: Store entities -----
        # Use bulk_add for efficiency when there are multiple entities.
        # bulk_add_entities expects fully-formed dicts with all required fields.
        stored_count = graph.bulk_add_entities(entities)

        # ----- Phase 3: Store edges -----
        edge_count = graph.bulk_add_edges(edges) if edges else 0

        # ----- Phase 4: Compute and store embeddings for new entities -----
        # Each entity gets its own embedding based on its label + description,
        # making it individually searchable via vector similarity.
        embedded_ids = []
        for entity in entities:
            try:
                embed_input = entity["label"]
                if entity.get("description"):
                    embed_input += ": " + entity["description"]
                embedding = embed_text(embed_input)
                graph.set_embedding(entity["id"], embedding)
                embedded_ids.append(entity["id"])
            except Exception as e:
                logger.warning("Failed to embed entity %s: %s", entity["id"], e)

        # ----- Phase 5: Discover hidden connections for new entities -----
        # This is the "aha moment" feature — find ideas in the existing graph
        # that are semantically close to the new entities but not yet linked.
        hidden_links: list[str] = []
        if _HAS_HIDDEN:
            for entity in entities:
                try:
                    hidden = find_hidden_for_entity(
                        graph, entity["id"], candidates=10, threshold=0.35
                    )
                    for h in hidden[:3]:  # Cap at 3 per entity to keep output concise
                        hidden_links.append(
                            f"{entity['label']} <-> {h['target_label']} "
                            f"({h['target_type']}, distance={h['distance']})"
                        )
                except Exception as e:
                    logger.debug("Hidden connection check failed for %s: %s", entity["id"], e)

        # ----- Build response -----
        entity_labels = [e["label"] for e in entities]
        parts = [
            f"Stored {stored_count} entities, {edge_count} edges.",
            f"Entities: {', '.join(entity_labels[:10])}",
        ]

        if hidden_links:
            parts.append("Hidden connections discovered:")
            for link in hidden_links[:5]:
                parts.append(f"  - {link}")
        else:
            parts.append("No hidden connections found (graph may be small or indexes not built).")

        return "\n".join(parts)

    except Exception as e:
        logger.error("memory_write failed: %s", traceback.format_exc())
        return f"Error storing thought: {e}"


# ===========================================================================
# Tool 2: memory_zoom_out
# ===========================================================================

@mcp.tool()
def memory_zoom_out(query: str) -> str:
    """Answer broad, thematic questions by searching pre-computed community summaries.

    Instead of matching individual entities, this finds clusters of related
    knowledge that match the query. Good for questions like "What do I know
    about systems thinking?" or "What themes keep coming up in my notes?"

    Community summaries must be pre-computed via
    ``second_brain.community_summaries.compute_community_summaries()``.

    Args:
        query: A broad question or topic to explore.

    Returns:
        Formatted text with the top matching community themes, their sizes,
        and key member entities.
    """
    try:
        graph, ontology, extractor = _init()

        if not _HAS_COMMUNITIES:
            return (
                "Community summaries module not available. "
                "Ensure second_brain.community_summaries is importable."
            )

        # Embed the query to search community summary vectors
        query_embedding = embed_text(query)

        # Search for the top 3 matching communities
        communities = search_communities(graph, query_embedding, limit=3)

        if not communities:
            return (
                "No community summaries found. Run "
                "compute_community_summaries() first to build the zoom-out layer."
            )

        # Format the results into a readable summary
        parts = [f"Found {len(communities)} relevant knowledge clusters for: \"{query}\"\n"]

        for i, comm in enumerate(communities, 1):
            comm_id = comm.get("community_id", "?")
            size = comm.get("size", "?")
            summary = comm.get("summary", "(no summary)")
            top_entities = comm.get("top_entities", "")
            score = comm.get("score", None)

            parts.append(f"--- Cluster {i} (community {comm_id}, {size} members) ---")
            if score is not None:
                parts.append(f"Relevance score: {score:.4f}")
            parts.append(f"Theme: {summary}")
            if top_entities:
                parts.append(f"Key members: {top_entities}")
            parts.append("")  # Blank line between clusters

        return "\n".join(parts)

    except Exception as e:
        logger.error("memory_zoom_out failed: %s", traceback.format_exc())
        return f"Error searching communities: {e}"


# ===========================================================================
# Tool 3: memory_search
# ===========================================================================

@mcp.tool()
def memory_search(query: str, mode: str = "hybrid", hops: int = 2) -> str:
    """Search the knowledge graph and expand results via graph traversal.

    Combines text search (keyword), vector similarity (semantic), or both
    (hybrid) to find relevant entities, then walks the graph outward by
    ``hops`` steps to surface connected context.

    Args:
        query: What to search for — a concept, name, topic, or question.
        mode: Search strategy. One of:
              - "keyword": Full-text search on entity labels and descriptions.
              - "semantic": Vector similarity search using embeddings.
              - "hybrid": Both keyword and semantic, merged and deduplicated.
        hops: How many graph traversal steps to expand from each result.
              1 = direct neighbors only, 2 = neighbors of neighbors, etc.
              Default is 2. Max is 4 (to avoid runaway expansion).

    Returns:
        Formatted text listing matched entities, their types, and connections
        discovered through graph expansion.
    """
    try:
        graph, ontology, extractor = _init()

        # Clamp hops to a safe range
        hops = max(1, min(hops, 4))

        results: list[dict] = []
        seen_ids: set[str] = set()

        # ----- Keyword search -----
        if mode in ("keyword", "hybrid"):
            keyword_results = graph.query(
                """
                MATCH (e:Entity)
                WHERE e.label CONTAINS $query
                RETURN e.id AS id, e.label AS label,
                       e.entity_type AS type, e.description AS description,
                       e.confidence AS confidence
                ORDER BY e.confidence DESC
                LIMIT 10
                """,
                parameters={"query": query},
            )
            for r in keyword_results:
                if r["id"] not in seen_ids:
                    r["match_type"] = "keyword"
                    results.append(r)
                    seen_ids.add(r["id"])

        # ----- Semantic search -----
        if mode in ("semantic", "hybrid"):
            query_embedding = embed_text(query)
            vector_results = graph.vector_search(query_embedding, limit=10)
            for r in vector_results:
                if r["id"] not in seen_ids:
                    r["match_type"] = "semantic"
                    results.append(r)
                    seen_ids.add(r["id"])

        if not results:
            return f"No results found for \"{query}\" (mode={mode})."

        # ----- Graph expansion: walk outward from each result -----
        # For each matched entity, find its neighbors up to `hops` away.
        # This surfaces context the LLM wouldn't get from search alone.
        expanded_connections: dict[str, list[dict]] = {}

        for result in results[:5]:  # Expand only the top 5 to keep output manageable
            entity_id = result["id"]
            neighbors = graph.query(
                """
                MATCH (e:Entity {id: $eid})-[r:RELATES_TO*1..%d]-(neighbor:Entity)
                WHERE neighbor.id <> $eid
                RETURN DISTINCT neighbor.id AS id,
                       neighbor.label AS label,
                       neighbor.entity_type AS type,
                       r[0].edge_type AS edge_type
                LIMIT 10
                """ % hops,
                parameters={"eid": entity_id},
            )

            # Also check for edge-node connections (Semantic Spacetime paths)
            try:
                edgenode_neighbors = graph.query(
                    """
                    MATCH (e:Entity {id: $eid})-[:CONNECTS]->(en:EdgeNode)-[:BINDS]->(neighbor:Entity)
                    RETURN DISTINCT neighbor.id AS id,
                           neighbor.label AS label,
                           neighbor.entity_type AS type,
                           en.semantic_type AS edge_type
                    LIMIT 5
                    """,
                    parameters={"eid": entity_id},
                )
                neighbors.extend(edgenode_neighbors)
            except Exception:
                pass  # EdgeNode traversal is optional

            if neighbors:
                expanded_connections[entity_id] = neighbors

        # ----- Format output -----
        parts = [
            f"Found {len(results)} entities for \"{query}\" (mode={mode}, hops={hops})\n"
        ]

        for result in results:
            entity_id = result["id"]
            label = result.get("label", entity_id)
            etype = result.get("type", "unknown")
            desc = result.get("description", "")
            match_type = result.get("match_type", "")
            confidence = result.get("confidence", None)
            score = result.get("score", None)

            header = f"[{etype}] {label}"
            if match_type:
                header += f" ({match_type}"
                if score is not None:
                    header += f", score={score:.4f}"
                if confidence is not None:
                    header += f", conf={confidence:.2f}"
                header += ")"

            parts.append(header)
            if desc:
                parts.append(f"  {desc}")

            # Show expanded connections for this entity
            connections = expanded_connections.get(entity_id, [])
            if connections:
                conn_strs = []
                for conn in connections[:5]:
                    edge = conn.get("edge_type", "RELATES_TO")
                    conn_strs.append(f"{conn['label']} ({conn['type']}) via {edge}")
                parts.append(f"  Connected to: {'; '.join(conn_strs)}")

            parts.append("")  # Blank line between results

        return "\n".join(parts)

    except Exception as e:
        logger.error("memory_search failed: %s", traceback.format_exc())
        return f"Error searching memory: {e}"


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    # Configure logging so tool errors are visible in stderr
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    mcp.run()
