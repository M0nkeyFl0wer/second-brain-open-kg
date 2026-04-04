"""
Pre-built, parameterized Cypher query patterns for the personal knowledge graph.
Every query the system runs is defined here. No dynamic Cypher generation.
This means: (1) no query hallucination, (2) every query is auditable,
(3) you can see exactly what the system does with your data.
"""

QUERIES = {
    # =========================================================================
    # Entity search
    # =========================================================================

    # Search entities by label substring match
    "entity_by_label": """
        MATCH (e:Entity)
        WHERE e.label CONTAINS $query
        RETURN e.id AS id, e.label AS label, e.entity_type AS type,
               e.confidence AS confidence, e.source_url AS source
        ORDER BY e.confidence DESC LIMIT $limit
    """,

    # Filter entities by type
    "entity_by_type": """
        MATCH (e:Entity {entity_type: $etype})
        RETURN e.id AS id, e.label AS label, e.confidence AS confidence,
               e.source_url AS source
        ORDER BY e.label LIMIT $limit
    """,

    # Combined label + type filter
    "entity_by_label_and_type": """
        MATCH (e:Entity)
        WHERE e.label CONTAINS $query AND e.entity_type = $etype
        RETURN e.id AS id, e.label AS label, e.entity_type AS type,
               e.confidence AS confidence, e.source_url AS source
        ORDER BY e.confidence DESC LIMIT $limit
    """,

    # =========================================================================
    # Vector search (brute-force fallback when HNSW index not available)
    # =========================================================================

    "vector_search": """
        MATCH (e:Entity)
        WHERE e.embedding IS NOT NULL
        WITH e, array_cosine_similarity(e.embedding, $qemb) AS score
        ORDER BY score DESC
        LIMIT $limit
        RETURN e.id AS id, e.label AS label,
               e.entity_type AS type, score
    """,

    # =========================================================================
    # Topology support — feeds NetworkX and native algo extension
    # =========================================================================

    "all_entities_for_topology": """
        MATCH (e:Entity)
        RETURN e.id AS id, e.entity_type AS type, e.label AS label,
               e.confidence AS confidence
    """,

    "all_edges_for_topology": """
        MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
        RETURN a.id AS src, b.id AS tgt, r.edge_type AS type,
               r.weight AS weight, r.confidence AS confidence
    """,

    # =========================================================================
    # PKG-specific queries
    # =========================================================================

    # Conflicting beliefs — ideas you hold that contradict each other
    "conflicting_beliefs": """
        MATCH (a:Entity)-[r:RELATES_TO {edge_type: 'CONFLICTS_WITH'}]->(b:Entity)
        RETURN a.label AS belief_a, b.label AS belief_b,
               a.source_url AS source_a, b.source_url AS source_b,
               r.created_at AS found_at
        ORDER BY r.created_at DESC LIMIT $limit
    """,

    # Open questions — things you're still exploring
    "open_questions": """
        MATCH (q:Entity {entity_type: 'question'})
        OPTIONAL MATCH (q)<-[r:RELATES_TO {edge_type: 'ANSWERS'}]-(a:Entity)
        WITH q, count(r) AS answer_count
        WHERE answer_count = 0
        RETURN q.label AS question, q.source_url AS source
        ORDER BY q.created_at DESC LIMIT $limit
    """,

    # Insights and what inspired them
    "insights_with_sources": """
        MATCH (i:Entity {entity_type: 'insight'})-[r:RELATES_TO]->(src:Entity)
        WHERE r.edge_type IN ['INSPIRED_BY', 'LEARNED_FROM']
        RETURN i.label AS insight, src.label AS source,
               src.entity_type AS source_type, r.edge_type AS relation
        ORDER BY i.created_at DESC LIMIT $limit
    """,

    # Edge-node traversal — Semantic Spacetime hypergraph queries
    "edge_node_traversal": """
        MATCH (a:Entity)-[:CONNECTS]->(en:EdgeNode)-[:BINDS]->(b:Entity)
        WHERE en.semantic_type = $stype
        RETURN a.label AS from_entity, en.label AS relationship,
               en.semantic_type AS type, b.label AS to_entity,
               en.weight AS weight
        ORDER BY en.weight DESC LIMIT $limit
    """,

    # =========================================================================
    # Daily reflection queries
    # =========================================================================

    # New ideas added in time window
    "new_entities_since": """
        MATCH (e:Entity) WHERE e.created_at > $since
        RETURN e.entity_type AS type, count(e) AS cnt
        ORDER BY cnt DESC
    """,

    # Underdeveloped ideas — entities with few connections
    "underdeveloped_ideas": """
        MATCH (e:Entity)
        WHERE NOT (e)-[:RELATES_TO]-()
          AND NOT (e)-[:MENTIONED_IN]-()
          AND e.created_at < $before
        RETURN e.label AS label, e.entity_type AS type
        LIMIT $limit
    """,

    # =========================================================================
    # Ontology health metrics
    # =========================================================================

    "type_distribution": """
        MATCH (e:Entity)
        RETURN e.entity_type AS type, count(e) AS cnt
        ORDER BY cnt DESC
    """,

    "edge_type_distribution": """
        MATCH ()-[r:RELATES_TO]->()
        RETURN r.edge_type AS type, count(r) AS cnt
        ORDER BY cnt DESC
    """,

    # =========================================================================
    # Counts
    # =========================================================================

    "entity_count": "MATCH (e:Entity) RETURN count(e) AS cnt",
    "edge_count": "MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS cnt",
    "document_count": "MATCH (d:Document) RETURN count(d) AS cnt",
    "edge_node_count": "MATCH (en:EdgeNode) RETURN count(en) AS cnt",
    "community_count": "MATCH (c:CommunityMeta) RETURN count(c) AS cnt",
}
