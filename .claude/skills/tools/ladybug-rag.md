---
name: ladybug-rag
description: Build graph RAG applications with LadybugDB — combining vector search, LLM embeddings, knowledge graphs, and hybrid retrieval. Use when designing RAG pipelines, implementing semantic search over graphs, building knowledge graph + vector hybrid systems, or integrating LadybugDB with LLM workflows.
---

# LadybugDB Graph RAG Patterns

Build retrieval-augmented generation systems that combine graph structure with vector similarity. LadybugDB is uniquely suited for graph RAG because vector indexes, full-text search, graph algorithms, and LLM embeddings all run inside the same embedded database — no external services, no data copying.

**When to use this skill:** Building RAG pipelines, semantic search over knowledge graphs, hybrid retrieval (graph + vector + BM25), or any LLM-powered application backed by LadybugDB.

---

## Architecture: Why Graph RAG > Flat RAG

Flat vector RAG retrieves chunks by similarity alone. Graph RAG adds:
- **Structural context** — follow edges to get related entities, not just similar text
- **Multi-hop reasoning** — traverse SUPPORTS, DERIVES_FROM, CONTRADICTS chains
- **Hybrid ranking** — combine vector distance, BM25 score, graph centrality, and edge weight
- **Explainability** — show the user *why* a result was retrieved (via path)

---

## Setup: Extensions Required

```cypher
INSTALL vector; LOAD EXTENSION vector;
INSTALL fts;    LOAD EXTENSION fts;
INSTALL llm;    LOAD EXTENSION llm;
INSTALL algo;   LOAD EXTENSION algo;
```

Load these every session — they're session-scoped.

---

## Schema for Graph RAG

### Minimal Schema

```cypher
CREATE NODE TABLE IF NOT EXISTS Document(
    id STRING PRIMARY KEY,
    title STRING,
    content STRING,
    source STRING,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    embedding FLOAT[384]
);

CREATE NODE TABLE IF NOT EXISTS Entity(
    id STRING PRIMARY KEY,
    name STRING,
    entity_type STRING,
    description STRING DEFAULT '',
    embedding FLOAT[384]
);

CREATE REL TABLE IF NOT EXISTS MENTIONS(FROM Document TO Entity);
CREATE REL TABLE IF NOT EXISTS RELATED(FROM Entity TO Entity, weight DOUBLE DEFAULT 1.0);
CREATE REL TABLE IF NOT EXISTS SUPPORTS(FROM Entity TO Entity, weight DOUBLE DEFAULT 1.0);
CREATE REL TABLE IF NOT EXISTS CONTRADICTS(FROM Entity TO Entity);
```

### With Chunks (for large documents)

```cypher
CREATE NODE TABLE IF NOT EXISTS Chunk(
    id STRING PRIMARY KEY,
    doc_id STRING,
    content STRING,
    chunk_index INT64,
    embedding FLOAT[384]
);

CREATE REL TABLE IF NOT EXISTS HAS_CHUNK(FROM Document TO Chunk);
CREATE REL TABLE IF NOT EXISTS CHUNK_MENTIONS(FROM Chunk TO Entity);
```

---

## Embedding Generation

### Option A: In-Database (LLM Extension)

```cypher
-- Ollama (local, no API key needed)
MATCH (d:Document) WHERE d.embedding IS NULL
SET d.embedding = CREATE_EMBEDDING(d.content, "ollama", "nomic-embed-text");

-- OpenAI
SET d.embedding = CREATE_EMBEDDING(d.content, "openai", "text-embedding-3-small", 384);

-- Voyage AI (best for code/technical)
SET d.embedding = CREATE_EMBEDDING(d.content, "voyageai", "voyage-3-large", 384);
```

**Env vars needed:** `OPENAI_API_KEY`, `VOYAGE_API_KEY`, or just run Ollama locally.

### Option B: Python-Side (More Control)

```python
from sentence_transformers import SentenceTransformer
import real_ladybug as lb
import pandas as pd

model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-dim

# Batch embed
texts = ["doc 1 content", "doc 2 content"]
embeddings = model.encode(texts).tolist()

# Bulk load via DataFrame
df = pd.DataFrame({
    "id": ["d1", "d2"],
    "title": ["Doc 1", "Doc 2"],
    "content": texts,
    "source": ["file", "file"],
    "embedding": embeddings
})
conn.execute("COPY Document FROM df")
```

### Option C: Hybrid (Python embed + Cypher store)

```python
embedding = model.encode("query text").tolist()
conn.execute(
    "MATCH (d:Document {id: $id}) SET d.embedding = $emb",
    parameters={"id": doc_id, "emb": embedding}
)
```

---

## Index Creation

### Vector Index (HNSW)

```cypher
-- Document embeddings
CALL CREATE_VECTOR_INDEX('Document', 'doc_vec', 'embedding',
    mu := 30, ml := 60, metric := 'cosine', efc := 200);

-- Entity embeddings
CALL CREATE_VECTOR_INDEX('Entity', 'entity_vec', 'embedding',
    mu := 30, ml := 60, metric := 'cosine', efc := 200);

-- Chunk embeddings (if using chunks)
CALL CREATE_VECTOR_INDEX('Chunk', 'chunk_vec', 'embedding',
    mu := 30, ml := 60, metric := 'cosine', efc := 200);
```

**Tuning tips:**
- `mu`/`ml` higher = more accurate, larger index, slower build
- `metric`: use `cosine` for normalized embeddings, `l2` for raw
- `efc`: higher = better index quality, slower construction
- `efs` (at query time): higher = more accurate search, slower

### Full-Text Search Index (BM25)

```cypher
CALL CREATE_FTS_INDEX('Document', 'doc_fts', ['title', 'content']);
CALL CREATE_FTS_INDEX('Entity', 'entity_fts', ['name', 'description']);
```

---

## Retrieval Patterns

### Pattern 1: Pure Vector Search

```cypher
CALL QUERY_VECTOR_INDEX('Document', 'doc_vec', $query_embedding, 10, efs := 200)
RETURN node.title, node.content, distance;
```

### Pattern 2: Pure Graph Traversal

```cypher
-- Find all documents connected to a topic within 2 hops
MATCH (e:Entity {name: $topic})<-[:MENTIONS]-(d:Document)
RETURN d.title, d.content;

-- Expand to related entities first
MATCH (e:Entity {name: $topic})-[:RELATED|SUPPORTS*1..2]->(e2:Entity)<-[:MENTIONS]-(d:Document)
RETURN DISTINCT d.title, d.content, e2.name AS via_entity;
```

### Pattern 3: Vector + Graph Expansion (Recommended)

The core graph RAG pattern — vector search seeds, graph traversal expands:

```python
def graph_rag_retrieve(conn, query_embedding, k=5, expansion_hops=2):
    # Step 1: Vector search for seed documents
    seeds = conn.execute("""
        CALL QUERY_VECTOR_INDEX('Document', 'doc_vec', $emb, $k)
        RETURN node.id AS id, node.title AS title, node.content AS content, distance
    """, parameters={"emb": query_embedding, "k": k}).get_all()

    seed_ids = [row[0] for row in seeds]

    # Step 2: Graph expansion — find related docs via entity connections
    expanded = conn.execute("""
        UNWIND $seeds AS seed_id
        MATCH (d1:Document {id: seed_id})-[:MENTIONS]->(e:Entity)
              -[:RELATED|SUPPORTS*1..$hops]->(e2:Entity)<-[:MENTIONS]-(d2:Document)
        WHERE NOT d2.id IN $seeds
        WITH d2, count(DISTINCT e2) AS connection_strength
        ORDER BY connection_strength DESC LIMIT $k
        RETURN d2.id, d2.title, d2.content, connection_strength
    """, parameters={"seeds": seed_ids, "hops": expansion_hops, "k": k}).get_all()

    return seeds + expanded
```

### Pattern 4: Hybrid Retrieval (Vector + BM25 + Graph)

Reciprocal rank fusion across all three signals:

```python
def hybrid_retrieve(conn, query_text, query_embedding, k=10):
    # Vector results
    vec_results = conn.execute("""
        CALL QUERY_VECTOR_INDEX('Document', 'doc_vec', $emb, $k)
        RETURN node.id AS id, node.title AS title, distance
    """, parameters={"emb": query_embedding, "k": k * 2}).get_all()

    # BM25 results
    fts_results = conn.execute("""
        CALL QUERY_FTS_INDEX('Document', 'doc_fts', $query)
        RETURN node.id AS id, node.title AS title, score
        ORDER BY score DESC LIMIT $k
    """, parameters={"query": query_text, "k": k * 2}).get_all()

    # Graph centrality boost (precomputed or live)
    centrality = conn.execute("""
        UNWIND $ids AS doc_id
        MATCH (d:Document {id: doc_id})-[:MENTIONS]->(e:Entity)
        RETURN doc_id, count(e) AS entity_count
    """, parameters={"ids": [r[0] for r in vec_results + fts_results]}).rows_as_dict()

    # RRF fusion
    return reciprocal_rank_fusion(vec_results, fts_results, centrality, k=k)


def reciprocal_rank_fusion(*result_lists, k=60, top_k=10):
    """Combine ranked lists using RRF. k=60 is standard smoothing constant."""
    scores = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            doc_id = item[0] if isinstance(item, (list, tuple)) else item["doc_id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
```

### Pattern 5: Entity-Centric RAG

When the query targets a specific entity, not a document:

```cypher
-- Find entity by name or embedding similarity
CALL QUERY_VECTOR_INDEX('Entity', 'entity_vec', $emb, 5)
WITH node AS target_entity, distance
WHERE distance < 0.3

-- Get its neighborhood
MATCH (target_entity)-[r*1..2]-(neighbor:Entity)
WITH target_entity, collect(DISTINCT {
    name: neighbor.name,
    type: neighbor.entity_type,
    rel: type(r)
}) AS neighborhood

-- Get supporting documents
MATCH (target_entity)<-[:MENTIONS]-(d:Document)
RETURN target_entity.name, target_entity.description,
       neighborhood, collect(d.title) AS sources;
```

### Pattern 6: Filtered Vector Search

Pre-filter before vector search using projected graphs:

```cypher
-- Only search within a specific category
CALL PROJECT_GRAPH('science_docs',
    {'Document': 'n.source = "arxiv"'}, []);

-- Or with Cypher-based projection
CALL PROJECT_GRAPH_CYPHER('recent_docs',
    'MATCH (n:Document) WHERE n.created_at > timestamp("2026-01-01") RETURN n');
```

---

## Context Assembly for LLM

### Building the Prompt Context

```python
def build_context(conn, query, query_embedding, max_tokens=4000):
    """Assemble retrieved context for LLM prompt."""
    results = graph_rag_retrieve(conn, query_embedding, k=5, expansion_hops=2)

    # Get entity context for seed docs
    doc_ids = [r[0] for r in results]
    entities = conn.execute("""
        UNWIND $ids AS doc_id
        MATCH (d:Document {id: doc_id})-[:MENTIONS]->(e:Entity)
        WITH doc_id, collect(e.name + ' (' + e.entity_type + ')') AS entities
        RETURN doc_id, entities
    """, parameters={"ids": doc_ids}).rows_as_dict()

    entity_map = {e["doc_id"]: e["entities"] for e in entities}

    context_parts = []
    for doc_id, title, content, *_ in results:
        ents = entity_map.get(doc_id, [])
        context_parts.append(
            f"## {title}\n"
            f"Entities: {', '.join(ents[:10])}\n\n"
            f"{content[:800]}"
        )

    return "\n\n---\n\n".join(context_parts)
```

### Path-Based Explanations

Show the user how retrieved context connects to the query:

```cypher
-- Find path from query entity to document
MATCH path = (q:Entity {name: $query_entity})
      -[*SHORTEST 1..4]->(e:Entity)<-[:MENTIONS]-(d:Document {id: $doc_id})
RETURN [n IN nodes(path) | n.name] AS reasoning_chain,
       [r IN relationships(path) | type(r)] AS edge_types;
```

---

## Ingestion Pipeline

### Full Ingestion Flow

```python
import real_ladybug as lb
from sentence_transformers import SentenceTransformer
import pandas as pd

db = lb.Database("knowledge.lbug")
conn = lb.Connection(db)
model = SentenceTransformer("all-MiniLM-L6-v2")

# 1. Schema (idempotent)
conn.execute("""
    CREATE NODE TABLE IF NOT EXISTS Document(
        id STRING PRIMARY KEY, title STRING, content STRING,
        source STRING, embedding FLOAT[384]
    );
    CREATE NODE TABLE IF NOT EXISTS Entity(
        id STRING PRIMARY KEY, name STRING, entity_type STRING,
        embedding FLOAT[384]
    );
    CREATE REL TABLE IF NOT EXISTS MENTIONS(FROM Document TO Entity);
    CREATE REL TABLE IF NOT EXISTS RELATED(FROM Entity TO Entity, weight DOUBLE DEFAULT 1.0);
""")

# 2. Load extensions
conn.execute("INSTALL vector; LOAD EXTENSION vector;")
conn.execute("INSTALL fts; LOAD EXTENSION fts;")

# 3. Ingest documents (batch via COPY FROM)
docs_df = pd.DataFrame({
    "id": doc_ids,
    "title": titles,
    "content": contents,
    "source": sources,
    "embedding": model.encode(contents).tolist()
})
conn.execute("COPY Document FROM docs_df")

# 4. Extract and ingest entities (your extraction logic)
entities_df = pd.DataFrame({
    "id": entity_ids,
    "name": entity_names,
    "entity_type": entity_types,
    "embedding": model.encode(entity_names).tolist()
})
conn.execute("COPY Entity FROM entities_df")

# 5. Create mention edges
conn.execute("""
    COPY MENTIONS FROM (
        MATCH (d:Document), (e:Entity)
        WHERE d.content CONTAINS e.name
        RETURN d.id, e.id
    )
""")

# 6. Create indexes
conn.execute("""
    CALL CREATE_VECTOR_INDEX('Document', 'doc_vec', 'embedding',
        mu := 30, ml := 60, metric := 'cosine');
    CALL CREATE_VECTOR_INDEX('Entity', 'entity_vec', 'embedding',
        mu := 30, ml := 60, metric := 'cosine');
    CALL CREATE_FTS_INDEX('Document', 'doc_fts', ['title', 'content']);
""")
```

### Incremental Updates

```python
# Add new documents without rebuilding everything
def ingest_document(conn, model, doc_id, title, content, source):
    embedding = model.encode(content).tolist()

    # Upsert document
    conn.execute("""
        MERGE (d:Document {id: $id})
        ON CREATE SET d.title = $title, d.content = $content,
                      d.source = $source, d.embedding = $emb
        ON MATCH SET d.content = $content, d.embedding = $emb
    """, parameters={"id": doc_id, "title": title, "content": content,
                     "source": source, "emb": embedding})

    # Extract entities and create edges
    # (use your extraction logic here)

    # Note: vector index needs rebuild after significant changes
    # CALL DROP_VECTOR_INDEX('Document', 'doc_vec');
    # CALL CREATE_VECTOR_INDEX(...);
```

---

## Graph Algorithms for RAG

### PageRank for Authority Scoring

Boost retrieval results by entity importance:

```cypher
CALL PROJECT_GRAPH('KG', ['Entity'], ['RELATED', 'SUPPORTS']);
CALL page_rank('KG', dampingFactor := 0.85, maxIterations := 50)
RETURN node.id, node.name, rank ORDER BY rank DESC;
```

Use PageRank as a retrieval signal alongside vector distance and BM25 score.

### Community Detection for Topic Clustering

```cypher
CALL louvain('KG', maxPhases := 20)
RETURN louvain_id, collect(node.name) AS members, count(*) AS size
ORDER BY size DESC;
```

Use communities to diversify retrieval — don't return 10 results from the same cluster.

### Connected Components for Orphan Detection

```cypher
CALL weakly_connected_components('KG')
WITH group_id, collect(node.name) AS members, count(*) AS size
WHERE size = 1
RETURN members AS orphan_entities;
```

Orphan entities may indicate missing edges or poor extraction.

---

## Performance Tips

1. **Always COPY FROM for bulk** — individual CREATEs are 13x slower than DuckDB (#302)
2. **Tune HNSW params** — default recall can be low (#351). Try `mu:=40, ml:=80, efc:=300`
3. **Use efs at query time** — `efs := 300` or higher for better recall at slight speed cost
4. **Batch embeddings** — embed in Python batches, then COPY FROM DataFrame
5. **Parameterize queries** — `$param` for plan caching
6. **Profile expensive queries** — `PROFILE MATCH ...` shows per-operator timing
7. **Pre-compute centrality** — store PageRank as a node property, don't compute at query time
8. **Use read-only connections** — `Database(path, read_only=True)` for retrieval processes
