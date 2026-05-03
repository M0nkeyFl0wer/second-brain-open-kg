# open-second-brain → Hybrid Stack + Harness Implementation Plan

**Date**: 2026-05-03
**Goal**: Upgrade personal KG to DuckDB+LadybugDB hybrid with integrated triplet extraction, harness hooks, and SME validation

---

## Implementation Status (2026-05-03)

| Component | Status | File |
|-----------|--------|------|
| `second_brain/ontology.py` | ✅ Done | Entity/edge types, validate_edge, slugify, extraction_prompt_fragment |
| `second_brain/chunk_store.py` | ✅ Done | DuckDB FTS + HNSW + RRF, two-handle pattern, DELETE+INSERT for re-embed |
| `second_brain/graph.py` | ✅ Done | LadybugDB wrapper, WAL preflight, RAM flush, per-request open/close |
| `second_brain/extract.py` | ✅ Done | LLM triplet extraction with evidence enforcement |
| `second_brain/path_finder.py` | ✅ Done | shortest_path, neighborhood, verify_path, detect_gaps |
| `scripts/enrich.py` | ✅ Done | Nightly LLM pass, every 4h via systemd timer |
| `scripts/health_check.py` | ✅ Done | Graph + chunk observability, every 15min via systemd timer |
| `systemd/` | ✅ Done | Enrich + health timers with OOMScoreAdjust=-200 |
| `docs/hardening.md` | ✅ Done | Copied from ~/Projects/security-hardening-2026-01-28.md |
| `config/edge_types.json` | ✅ Done | Empty config (user fills via onboard.py) |
| `scripts/onboard.py` | ⬜ Todo | Interactive edge-type selection |
| `scripts/smoke_test.py` | ⬜ Todo | Pipeline smoke tests |
| `hooks/` (harness) | ⬜ Todo | Symlink from agentic-rag-harness |
| `.mcp/` config | ⬜ Todo | MCP server config for rag_search etc |
| `docs/ONTOLOGY.md` | ⬜ Todo | Entity/edge type reference |
| `docs/ACTIVE_STACK.md` | ⬜ Todo | Pipeline stages + services |
| `tests/fixture_corpus/` | ⬜ Todo | SME ground-truth triplets |
| `Makefile` (pre-push) | ⬜ Todo | codetopo + smoke test |
| `README.md` (onboarding) | ⬜ Todo | Edge type examples |

---

## Decisions Logged (2026-05-03)

| Decision | Rationale | Impact |
|----------|-----------|--------|
| DuckDB as chunk substrate | Native HNSW + BM25, ATTACH from Cypher works, embedded single-file | FLOAT[768] embeddings, two-handle RRF pattern |
| Corroboration = explicit SUPPORTS edge | Research confirms explicit typed edges from LLM extraction | No semantic similarity functions |
| HNSW UPDATE blocked | Cannot UPDATE indexed column in DuckDB | Re-embed strategy: DELETE + INSERT |
| `LOAD vss` before HNSW index | Required before CREATE INDEX ... USING HNSW | Missing from duckdb-rag skill |
| Two-handle RRF for FTS+HNSW | FTS persistent vs HNSW memory-handle differ | Use _ro/_mem pattern for large corpora |

---

## Phase 1: Architecture & Schema

### 1.1 Directory Structure

```
open-second-brain/
├── second_brain/
│   ├── __init__.py
│   ├── ontology.py          # Entity + edge types (triplet-first)
│   ├── graph.py             # LadybugDB wrapper (concurrency rules)
│   ├── chunk_store.py       # DuckDB wrapper (BM25 + HNSW + RRF)
│   ├── extract.py           # Triplet extraction (evidence required)
│   ├── embed.py             # Embedding pipeline (embedded_at tracking)
│   └── attach_bridge.py     # DuckDB ATTACH from Cypher
├── scripts/
│   ├── ingest_obsidian.py   # File watcher + queue writer
│   ├── enrich.py            # Scheduled LLM enrichment pass
│   ├── onboard.py           # Interactive first-run setup
│   └── smoke_test.py        # Pipeline smoke tests
├── hooks/                   # Harness hooks (symlinked from agentic-rag-harness)
│   ├── session-context.sh
│   ├── user-prompt-context.sh
│   ├── kg-context-inject.sh
│   ├── codetopo-check.sh
│   ├── pre-compact.sh
│   ├── post-compact.sh
│   └── session-end.sh
├── rules/
│   └── verification.md      # From agentic-rag-harness
├── skills/
│   └── rag-status.md        # From agentic-rag-harness
├── data/
│   ├── brain.ldb            # LadybugDB graph (entities + edges)
│   ├── chunks.duckdb        # DuckDB chunks + embeddings + FTS
│   └── graph_queue.jsonl    # Write queue (never direct to graph)
├── docs/
│   ├── ONTOLOGY.md          # Entity/edge type documentation
│   ├── ACTIVE_STACK.md      # Pipeline stages + services
│   └── hardening.md         # Copied from ~/Projects/security-hardening-2026-01-28.md
├── tests/
│   └── fixture_corpus/      # SME validation corpus
├── .mcp/                    # MCP server config (rag_search, rag_query_graph, etc.)
├── Makefile                 # Pre-push: codetopo + smoke test
└── README.md                # With onboarding examples
```

### 1.2 DuckDB Chunk Schema

```sql
CREATE TABLE chunk (
    id              VARCHAR PRIMARY KEY,
    doc_id          VARCHAR NOT NULL,
    source_uri      VARCHAR NOT NULL,
    title           VARCHAR,
    body            VARCHAR NOT NULL,
    chunk_index     INTEGER NOT NULL,
    entity_ids      VARCHAR[],
    sensitivity     VARCHAR DEFAULT 'public',
    created_at      TIMESTAMP DEFAULT now(),
    source_mtime    TIMESTAMP,
    embedded_at     TIMESTAMP
);

CREATE INDEX idx_chunk_doc ON chunk(doc_id);
CREATE INDEX idx_chunk_entity ON chunk USING GIN(entity_ids);

PRAGMA create_fts_index('chunk', 'id', 'body', 'title',
    stemmer='porter', stopwords='english', overwrite=1);

-- NOTE: LOAD vss; must precede this
SET hnsw_enable_experimental_persistence = true;
CREATE INDEX chunk_embedding_hnsw ON chunk USING HNSW (embedding)
    WITH (metric='cosine', ef_construction=200, M=32);
```

### 1.3 LadybugDB Graph Schema

```cypher
CREATE NODE TABLE entity (
    id          STRING PRIMARY KEY,
    label       STRING NOT NULL,
    entity_type STRING NOT NULL,
    meta        JSON,
    sensitivity STRING DEFAULT 'public',
    created_at  TIMESTAMP DEFAULT now()
);

CREATE EDGE TABLE edge (
    from        entity,
    to          entity,
    edge_type   STRING NOT NULL,
    evidence    STRING NOT NULL,
    confidence  DOUBLE NOT NULL,
    valid_from  TIMESTAMP DEFAULT now(),
    valid_until TIMESTAMP DEFAULT NULL,
    extraction  STRING NOT NULL
);

CREATE INDEX idx_entity_type ON entity(entity_type);
CREATE INDEX idx_edge_type ON edge(edge_type);
```

### 1.4 ATTACH Bridge

```cypher
-- In graph.py or attach_bridge.py
ATTACH 'data/chunks.duckdb' AS duck (dbtype duckdb);
LOAD FROM duck.chunk WHERE id = $chunk_id RETURN body, embedding;
```

### 1.5 Concurrency Rules (per ladybug skill)

- WAL preflight before opening write-mode
- Per-request open/close for read connections
- RAM flush every 2000 entities during bulk writes
- Read-only API mode when builder process exists

---

## Phase 2: Onboarding System

### 2.1 Interactive Onboarding (`scripts/onboard.py`)

- Scans vault content to suggest edge types
- Interactive prompt for edge type selection
- Writes `config/edge_types.json`

### 2.2 README Onboarding Section

- Edge type examples with triplet illustrations
- Manual config via `config/edge_types.json`

---

## Phase 3: Triplet Extraction Pipeline

### 3.1 Extraction Flow

```
file change → chunk → embed → extract triplets → write to graph
```

### 3.2 Evidence Enforcement

- Every edge requires `evidence` field (verbatim quote)
- Rejection logging to `write_log.jsonl`
- Threshold check: fail if rejection rate > 20%

### 3.3 Temporal Confidence Model

- `SUPPORTS` edge for corroboration (explicit typed edge, not similarity function)
- `CONFLICTS_WITH` edge for contradictions
- Deduplication by exact ID match (slug equality), not fuzzy name matching
- Re-embed strategy for changed notes: DELETE + INSERT (HNSW blocks UPDATE)

---

## Phase 4: Harness Integration

### 4.1 Symlink Hooks from agentic-rag-harness

- 7 hooks: session-context, user-prompt-context, kg-context-inject, codetopo-check, pre-compact, post-compact, session-end

### 4.2 MCP Server Config

- rag_search, rag_get_context, rag_query_graph, rag_save, rag_log_decision

### 4.3 Cross-Repo Bleed Defense (3 layers)

1. API-side `WHERE document_id = $path_prefix` filter
2. Hook-side scope resolution
3. MCP tool auto-fills `path_prefix` from `task_type`

---

## Phase 5: Testing & Validation

### 5.1 Fixture Corpus (`tests/fixture_corpus/`)

- Ground-truth triplets for SME validation

### 5.2 Smoke Tests (`scripts/smoke_test.py`)

- Triplet extraction with evidence
- Hybrid retrieval (BM25 + ANN + RRF)
- WAL preflight and concurrency rules

### 5.3 SME Validation (via rag-status skill)

---

## Phase 6: Documentation

- ONTOLOGY.md — entity/edge type reference
- ACTIVE_STACK.md — pipeline stages + services
- hardening.md — copied from ~/Projects/security-hardening-2026-01-28.md

---

## Implementation Order

```
Week 1: Foundation
├── Copy hardening doc
├── Create DuckDB schema + chunk_store.py
├── Create LadybugDB schema + graph.py
├── Implement ATTACH bridge
└── Write config/edge_types.json (empty, user fills via onboard)

Week 2: Ingestion
├── Wire ingest_obsidian.py → chunk_store.py
├── Add JSONL queue writer
├── Implement WAL preflight + concurrency rules
└── Run sample-before-scale (30 entities)

Week 3: Triplet Extraction
├── Build extract.py with evidence enforcement
├── Add temporal confidence model
├── Create scripts/onboard.py (interactive prompt)
├── Update README with edge type examples
└── Test against fixture_corpus

Week 4: Harness
├── Symlink hooks from agentic-rag-harness
├── Configure .mcp/config.json
├── Wire context-sections.json
├── Test 7 hooks against real session
└── codetopo + smoke test in Makefile

Week 5: Validation
├── Create fixture_corpus with ground_truth.json
├── Run SME tests (rag-status)
├── Fix any rejection rate issues
└── Document ONTOLOGY.md + ACTIVE_STACK.md
```

---

## Skills Updates Needed (Manual)

### duckdb-rag skill
1. **LOAD vss prerequisite** (around line 276) — must load vss before CREATE INDEX ... USING HNSW
2. **Two-handle RRF limitation** (around line 346) — FTS and HNSW handles differ in practice
3. **HNSW UPDATE blocked** (anti-patterns) — DELETE + INSERT only for re-embed

### kg-ingestion skill
1. **Corroboration = SUPPORTS edge type** (around line 373) — explicit typed edges, not similarity function
2. **CONFLICTS_WITH for contradictions** — explicit edge extraction with evidence quote required
3. **Deduplication by ID/slug** — exact match, not fuzzy name or embedding distance