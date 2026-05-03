"""
open-second-brain — personal knowledge graph with DuckDB + LadybugDB hybrid.

Architecture:
- DuckDB (chunks.duckdb): chunks, embeddings, FTS, HNSW vector index
- LadybugDB (brain.ldb): typed entities, typed edges with evidence

Write path:
    file change → chunk → embed → extract triplets → write to graph

Read path:
    query → BM25 + HNSW → RRF → graph expansion → response

Modules:
- ontology: entity types, edge types, validation
- chunk_store: DuckDB wrapper (FTS + HNSW + RRF)
- graph: LadybugDB wrapper (concurrency rules, WAL preflight)
- extract: triplet extraction with evidence enforcement
- embed: embedding pipeline with embedded_at tracking
- attach_bridge: DuckDB ATTACH from Cypher
"""