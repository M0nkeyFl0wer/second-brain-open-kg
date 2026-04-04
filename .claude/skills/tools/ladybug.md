---
name: ladybug
description: Reference skill for LadybugDB — an embedded graph database with Cypher queries, Python/Node/Rust APIs, vector search, graph algorithms, LLM embeddings, and 15+ extensions. Use when writing LadybugDB code, designing graph schemas, optimizing Cypher queries, or integrating LadybugDB into applications.
---

# LadybugDB Reference Guide

Comprehensive reference for writing correct, idiomatic LadybugDB code. LadybugDB is an embedded property graph database with Cypher query language, columnar storage, and vectorized query processing.

**Golden rule:** If you're about to write a Python loop over graph results to do traversal, filtering, aggregation, or path finding — stop. LadybugDB can probably do it in Cypher.

**Docs:** https://docs.ladybugdb.com | **GitHub:** https://github.com/LadybugDB/ladybug | **API docs:** https://api-docs.ladybugdb.com/python

---

## Installation

```bash
# CLI
curl -s https://install.ladybugdb.com | bash   # Linux
brew install ladybug                             # macOS

# Python
pip install real_ladybug
uv add real_ladybug

# Node.js
npm install @ladybugdb/core

# Rust
cargo add lbug

# Go
go get github.com/LadybugDB/go-ladybug@v0.11.0
```

---

## Core Principle: Let the DB Do the Work

| Instead of... | Use LadybugDB's... |
|---|---|
| Hand-coded 1-hop, 2-hop MATCH chains | Variable-length paths `[*1..4]` |
| Python loop building NetworkX graph | `result.get_as_networkx()` |
| Python shortest-path after dump to NetworkX | `MATCH ... -[* SHORTEST 1..10]->` |
| Individual CREATEs in a loop | `COPY FROM` (CSV, DataFrame, subquery) |
| Python dedup/filtering of results | `WITH ... WHERE` pipelining |
| String formatting in Cypher | Parameterized queries `$param` |
| NetworkX PageRank/WCC/Louvain | Native projected graph algorithms |
| Python aggregation over results | `collect()`, `COUNT {}` subqueries |
| Deleting node then manually deleting edges | `DETACH DELETE` |

---

## Python API

### Connection Model

```python
import real_ladybug as lb

# On-disk (persistent, WAL transactions, larger-than-memory)
db = lb.Database("example.lbug")

# In-memory (temporary, no WAL, lost on exit)
db = lb.Database(":memory:")

# With buffer pool config
db = lb.Database("example.lbug", buffer_pool_size=256*1024*1024)

# Read-only mode (allows concurrent access from other processes)
db_ro = lb.Database("example.lbug", read_only=True)

# Connections — one Database per process, multiple Connections fine
conn = lb.Connection(db)

# Async (thread pool for concurrent queries)
conn = lb.AsyncConnection(db, max_concurrent_queries=4)
result = await conn.execute("MATCH (n:Note) RETURN n.title")
```

### Query Execution

```python
# Parameterized queries (ALWAYS use these — safe, cached plan)
result = conn.execute(
    "MATCH (e:Entity) WHERE e.name = $name RETURN e.*",
    parameters={"name": entity_name}
)

# NEVER do this — injection risk, no plan caching
result = conn.execute(f"MATCH (e:Entity) WHERE e.name = '{name}' RETURN e.*")

# Multiple statements (semicolon-separated)
responses = conn.execute("RETURN 42; RETURN 'Alice'")
```

### Result Handling

```python
result.get_all()              # List of tuples
result.rows_as_dict()         # List of dicts with column names as keys
result.get_as_df()            # Pandas DataFrame
result.get_as_pl()            # Polars DataFrame
result.get_as_arrow()         # PyArrow Table
result.get_as_networkx()      # NetworkX graph
result.get_n(5)               # First 5 rows
result.get_next()             # Single next row
result.has_next()             # Boolean: more rows?
result.get_num_tuples()       # Row count
result.get_execution_time()   # ms — for profiling
result.get_compiling_time()   # ms — for profiling
```

### Data Loading

```python
# COPY FROM DataFrame (bulk import)
df = pd.DataFrame({"name": ["Adam"], "age": [30]})
conn.execute("COPY Person FROM df")

# LOAD FROM DataFrame (scan without copying)
result = conn.execute("LOAD FROM df RETURN *")

# Supports Pandas, Polars, and PyArrow
```

### User-Defined Functions

```python
# With type annotations
def difference(a: int, b: int) -> int:
    return abs(a - b)
conn.create_function("difference", difference)

# With explicit types
conn.create_function("difference", difference,
    [lb.Type.INT64, lb.Type.INT64], lb.Type.INT64)

# Use in Cypher: RETURN difference(i.a, i.b) AS diff
conn.remove_function("difference")
```

### Type Mapping (Python <-> LadybugDB)

| Python | LadybugDB |
|--------|-----------|
| `bool` | `BOOL` |
| `int` | `INT64` |
| `float` | `DOUBLE` |
| `str` | `STRING` |
| `datetime` | `TIMESTAMP` |
| `date` | `DATE` |
| `timedelta` | `INTERVAL` |
| `uuid` | `UUID` |
| `list` | `LIST` |
| `dict` | `MAP` |

---

## Schema Design

### Node Tables

```cypher
CREATE NODE TABLE IF NOT EXISTS Entity(
    id STRING PRIMARY KEY,
    name STRING,
    entity_type STRING,
    confidence DOUBLE DEFAULT 1.0,
    tags STRING[] DEFAULT [],
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- Rich property types
CREATE NODE TABLE Note(
    id STRING PRIMARY KEY,
    title STRING,
    tags STRING[] DEFAULT [],
    metadata STRUCT(source STRING, weight DOUBLE),
    embedding FLOAT[384]  -- fixed-size for vector index
);
```

### Relationship Tables

```cypher
-- Default MANY_MANY
CREATE REL TABLE RELATED(FROM Entity TO Entity, weight DOUBLE DEFAULT 1.0);

-- Many-to-one
CREATE REL TABLE PART_OF(FROM Note TO Entity, MANY_ONE);

-- Multi-source relationships
CREATE REL TABLE Follows(FROM User TO User, since INT64);
CREATE REL TABLE LivesIn(FROM User TO City);
```

### Schema Evolution

```cypher
ALTER TABLE Entity ADD tags STRING[] DEFAULT [];
ALTER TABLE Entity DROP old_column;
```

**Always import nodes BEFORE relationships.**

---

## Data Types

**Integers:** INT8, INT16, INT32 (INT), INT64 (SERIAL), INT128, UINT8-64
**Floats:** FLOAT (REAL/FLOAT4), DOUBLE (FLOAT8), DECIMAL(precision, scale)
**Other scalars:** BOOLEAN, STRING, UUID, DATE, TIMESTAMP, INTERVAL (DURATION), BLOB, NULL
**Complex:** LIST, ARRAY (fixed-length), MAP, STRUCT, UNION, JSON (v0.15+)
**Graph:** NODE, REL, RECURSIVE_REL
**Casting:** `CAST(value, "TYPE")` — overflow raises exception

---

## Cypher Query Patterns

### Variable-Length Paths

```cypher
-- 1 to 4 hops
MATCH (a:Entity)-[e:SUPPORTS|DERIVES_FROM*1..4]->(b:Entity)
WHERE a.name = $start_name
RETURN b.name, length(e) AS depth, properties(nodes(e), 'name') AS path;
```

**Path semantics:**
- **WALK** (default): nodes/edges can repeat
- **TRAIL**: all relationships distinct
- **ACYCLIC**: all nodes distinct

```cypher
-- Acyclic paths only
MATCH (a:Entity)-[e:SUPPORTS* ACYCLIC 1..4]->(b:Entity)
WHERE a.name = $start AND b.name = $end
RETURN properties(nodes(e), 'name') AS chain;
```

### Inline Filtering on Traversal

```cypher
MATCH (a:Entity)-[e:RELATED*1..3 (r, n | WHERE n.entity_type = 'concept' AND r.weight > 0.5)]->(b:Entity)
WHERE a.name = $start
RETURN b.name, length(e);
```

### Shortest Path

```cypher
-- Single shortest
MATCH (a:Entity)-[e* SHORTEST 1..10]->(b:Entity)
WHERE a.name = $start AND b.name = $end
RETURN length(e), properties(nodes(e), 'name') AS path;

-- All shortest
MATCH p = (a:Entity)-[* ALL SHORTEST 1..5]-(b:Entity)
WHERE a.name = $start AND b.name = $end
RETURN properties(nodes(p), 'name'), length(p);

-- Weighted shortest
MATCH p = (a:Entity)-[e:SUPPORTS* WSHORTEST(weight)]->(b:Entity)
WHERE a.name = $start
RETURN properties(nodes(p), 'name'), cost(e);
```

### MERGE (Upsert)

```cypher
MERGE (e:Entity {id: $eid})
ON CREATE SET e.name = $name, e.entity_type = $etype, e.confidence = 1.0
ON MATCH SET e.confidence = e.confidence + 0.1;
```

### Bulk Operations

```cypher
-- From CSV
COPY Entity FROM "entities.csv" (HEADER=true);

-- From subquery
COPY MENTIONS FROM (
    MATCH (n:Note), (e:Entity)
    WHERE n.title CONTAINS e.name
    RETURN n.id, e.id
);
```

### COUNT Subquery

```cypher
MATCH (e:Entity)
RETURN e.name, e.entity_type,
       COUNT { MATCH (e)<-[:MENTIONS]-(n:Note) } AS mentions,
       COUNT { MATCH (e)-[:SUPPORTS]->() } AS supports
ORDER BY mentions DESC LIMIT 20;
```

### Multi-Label Queries

```cypher
MATCH (n:Entity|Note) WHERE n.name CONTAINS 'Docker' RETURN label(n), n.name;
MATCH (a:Entity)-[r:SUPPORTS|DERIVES_FROM|RELATED]->(b:Entity)
RETURN a.name, type(r), b.name;
```

---

## Extensions

Extensions are session-scoped — load each session:

```cypher
INSTALL algo; LOAD EXTENSION algo;
INSTALL fts;  LOAD EXTENSION fts;
INSTALL vector; LOAD EXTENSION vector;
INSTALL llm; LOAD EXTENSION llm;
INSTALL sqlite; LOAD EXTENSION sqlite;

-- List available
CALL SHOW_OFFICIAL_EXTENSIONS() RETURN *;
-- List loaded
CALL SHOW_LOADED_EXTENSIONS() RETURN *;
```

**Available (15):** algo, azure, delta, duckdb, fts, httpfs, iceberg, json, llm, neo4j, postgres, sqlite, unity, vector

### Graph Algorithms (algo)

Require a projected graph:

```cypher
-- Create projected graph
CALL PROJECT_GRAPH('KG', ['Entity'], ['SUPPORTS', 'DERIVES_FROM', 'RELATED']);

-- With filters
CALL PROJECT_GRAPH('Filtered',
    {'Entity': 'n.entity_type = "concept"'},
    {'RELATED': 'r.weight > 0.5'}
);

-- PageRank
CALL page_rank('KG', dampingFactor := 0.85, maxIterations := 50)
RETURN node.name, rank ORDER BY rank DESC LIMIT 20;

-- Weakly Connected Components
CALL weakly_connected_components('KG')
RETURN group_id, collect(node.name), count(*) AS size ORDER BY size DESC;

-- Louvain Community Detection
CALL louvain('KG', maxPhases := 20)
RETURN louvain_id, collect(node.name) AS members ORDER BY size(members) DESC;

-- K-Core Decomposition
CALL k_core_decomposition('KG')
RETURN node.name, k_degree ORDER BY k_degree DESC;

-- Strongly Connected Components
CALL strongly_connected_components('KG')
RETURN group_id, collect(node.name);

-- Cleanup (projected graphs are session-scoped)
CALL DROP_PROJECTED_GRAPH('KG');
```

### Full-Text Search (fts)

```cypher
CALL CREATE_FTS_INDEX('Note', 'note_fts', ['title', 'path']);
CALL QUERY_FTS_INDEX('Note', 'note_fts', 'category theory')
RETURN node.title, score ORDER BY score DESC;
```

### Vector Search (vector)

```cypher
-- Create HNSW index
CALL CREATE_VECTOR_INDEX('Note', 'note_vec', 'embedding',
    mu := 30, ml := 60, pu := 0.05,
    metric := 'cosine', efc := 200);

-- Query
CALL QUERY_VECTOR_INDEX('Note', 'note_vec', $query_embedding, 10, efs := 200)
RETURN node.title, distance;

-- Drop
CALL DROP_VECTOR_INDEX('Note', 'note_vec');

-- List all indexes
CALL SHOW_INDEXES() RETURN *;
```

**HNSW params:** `mu` (upper degree, 30), `ml` (lower degree, 60), `pu` (upper sample %, 0.05), `metric` (cosine/l2/l2sq/dotproduct), `efc` (construction candidates, 200)
**Query params:** `efs` (search candidates, 200) — higher = more accurate

### LLM Embeddings (llm)

```cypher
-- CREATE_EMBEDDING(prompt, provider, model, [dimensions], [region], [endpoint])
RETURN CREATE_EMBEDDING("Hello world", "ollama", "nomic-embed-text");
RETURN CREATE_EMBEDDING("Hello world", "openai", "text-embedding-3-small", 512);
RETURN CREATE_EMBEDDING("Hello world", "voyageai", "voyage-3-large", 512);
```

**Providers:** ollama, openai, voyageai, amazon-bedrock, google-vertex, google-gemini

**Required env vars:** `OPENAI_API_KEY`, `VOYAGE_API_KEY`, `GOOGLE_GEMINI_API_KEY`, `AWS_ACCESS_KEY` + `AWS_SECRET_ACCESS_KEY`, `GOOGLE_CLOUD_PROJECT_ID` + `GOOGLE_VERTEX_ACCESS_KEY`

### Attached Databases

```cypher
-- SQLite
ATTACH 'data/content.db' AS content (dbtype sqlite);
MATCH (p:Entity) WHERE p.id IN (SELECT id FROM content.items WHERE active = 1)
RETURN p.name;
DETACH content;

-- Also: duckdb, postgres extensions
```

### Macros

```cypher
CREATE MACRO edge_weight(etype) AS
  CASE etype
    WHEN 'SUPPORTS' THEN 1.2
    WHEN 'DERIVES_FROM' THEN 1.1
    WHEN 'RELATED' THEN 0.8
    ELSE 1.0
  END;

-- Use: RETURN edge_weight(type(r)) AS weight;
```

---

## Built-in Functions

```cypher
-- Array/vector operations (no index needed)
RETURN array_cosine_similarity(a.embedding, b.embedding) AS sim;
RETURN array_distance(a.embedding, b.embedding) AS dist;

-- List lambdas
RETURN list_filter(e.tags, x -> x STARTS WITH 'kg-') AS kg_tags;
RETURN list_transform(names, x -> lower(x)) AS normalized;

-- String
RETURN levenshtein(a.name, b.name) AS edit_distance;

-- Regex
MATCH (e:Entity) WHERE e.name =~ '(?i).*docker.*' RETURN e.name;
```

---

## Debugging / Profiling

```cypher
-- Query plan (without executing)
EXPLAIN MATCH (a:Entity)-[:SUPPORTS*1..3]->(b:Entity) RETURN a.name, b.name;

-- Execute + show timing per operator
PROFILE MATCH (a:Entity)-[:SUPPORTS*1..3]->(b:Entity) RETURN a.name, b.name;

-- Introspection
CALL SHOW_TABLES() RETURN *;
CALL TABLE_INFO('Entity') RETURN *;
CALL SHOW_CONNECTION('MENTIONS') RETURN *;
CALL SHOW_INDEXES() RETURN *;

-- Max depth for variable-length paths (default 30)
CALL var_length_extend_max_depth=10;
```

---

## Concurrency Rules

1. **Single writer** — one write transaction at a time across all connections
2. **Multiple readers** — fine, use separate Connection objects
3. **Multi-process** — API server pattern (one process holds DB, others connect via HTTP)
4. **Read-only mode** — `Database(path, read_only=True)` for read-only processes
5. **Bulk writes** — batch via COPY FROM, not queued individual CREATEs

---

## Filtered Vector Search

Two approaches for pre-filtering before vector search:

```cypher
-- Approach 1: Projected graph with filter
CALL PROJECT_GRAPH('filtered', {'Note': 'n.category = "science"'}, []);
-- Then query the projected graph by name

-- Approach 2: Cypher-based projection
CALL PROJECT_GRAPH_CYPHER('filtered',
    'MATCH (n:Note) WHERE n.category = "science" RETURN n');
```

---

## Anti-Patterns to Avoid

1. **String formatting in Cypher** — Always use `$param` parameterized queries
2. **Python loops for traversal** — Use variable-length paths `[*1..N]`
3. **Individual CREATEs in a loop** — Use `COPY FROM` for bulk writes
4. **Dumping entire graph to NetworkX** — Use targeted queries or native algorithms
5. **WALK semantics by default** — Use TRAIL or ACYCLIC when you need distinct paths
6. **Ignoring MERGE** — Use `MERGE ... ON CREATE SET ... ON MATCH SET` for upserts
7. **Forgetting to load extensions** — Extensions are session-scoped, load every session
8. **Not using IF NOT EXISTS** — Schema creation should be idempotent

---

## Known Issues (GitHub)

- Vector index recall can be low (~18%) on fresh data (#351) — consider tuning `mu`, `ml`, `efc` params
- Ubuntu 22.04 compatibility issues (#309)
- Non-batched inserts significantly slower than DuckDB (#302) — always use COPY FROM for bulk
- UNWIND + MERGE can return wrong tuple counts (#285)
- WASM thread pool sizing issues for multi-engine apps (#363)
