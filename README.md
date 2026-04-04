# open-second-brain

A personal knowledge graph that lives on top of your Obsidian vault. Ingest your notes, extract concepts and connections, find hidden links between ideas, and get a daily reflection on what your graph knows. Runs entirely on your machine.

**No cloud required. No accounts. Your thoughts stay yours.**

### Built With

[![LadybugDB](https://img.shields.io/badge/LadybugDB-0.15.3-orange?style=flat-square&logo=data:image/svg+xml;base64,)](https://ladybugdb.com)
[![NetworkX](https://img.shields.io/badge/NetworkX-3.6-blue?style=flat-square)](https://networkx.org)
[![Ollama](https://img.shields.io/badge/Ollama-local_AI-black?style=flat-square)](https://ollama.com)
[![spaCy](https://img.shields.io/badge/spaCy-NLP-09a3d5?style=flat-square)](https://spacy.io)

<a href="https://ladybugdb.com"><img src="https://ladybugdb.com/img/logo.svg" alt="LadybugDB" height="50"></a>&nbsp;&nbsp;&nbsp;
<a href="https://networkx.org"><img src="https://networkx.org/documentation/stable/_static/networkx_logo.svg" alt="NetworkX" height="50"></a>&nbsp;&nbsp;&nbsp;
<a href="https://ollama.com"><img src="https://ollama.com/public/ollama.png" alt="Ollama" height="50"></a>

> ### Why This Exists
>
> This project was inspired by [*An Alternative Trajectory for Generative AI*](https://arxiv.org/abs/2603.14147) (Belova, Kansal, Liang, Xiao & Jha — Princeton, 2026), which argues that the current path of scaling monolithic LLMs is physically and economically unsustainable. Their alternative: **domain-specific superintelligence** — small, specialized models grounded in knowledge graphs, ontologies, and formal logic, organized as composable "societies" rather than a single giant model.
>
> The paper's core insight is that intelligence comes from manipulating relational symbolic structures, not just pattern-matching over massive corpora. Knowledge graphs aren't just retrieval tools — they're the **structural scaffolding** for reasoning, verification, and synthetic training data. Every fact traces back to a source. Every reasoning step is auditable. Every connection is explicit.
>
> Reading this paper introduced me to the idea of **verification with topology** — using graph structure itself (persistent homology, community detection, betweenness centrality) to validate knowledge rather than trusting LLM confidence scores. The decentralized, modular, local-first approach resonated deeply. This project is part of a broader effort to build tools that put knowledge graph intelligence in the hands of individuals, not data centers.
>
> *"Rather than a single generalist LLM monolith, we envision a future built on specialized small language models."* — Belova et al.

## What This Does

You have an Obsidian vault full of notes — reading notes, project ideas, journal entries, questions, insights. You link some of them with `[[wikilinks]]`, but most connections live only in your head.

This toolkit:

1. **Ingests** your Obsidian vault (markdown, wikilinks, frontmatter, tags)
2. **Extracts** concepts, people, sources, insights, and the relationships between them
3. **Builds** a searchable knowledge graph with semantic embeddings
4. **Discovers** hidden connections — ideas that are semantically similar but you never linked
5. **Reflects** daily with a markdown summary: new ideas, conflicting beliefs, knowledge gaps

---

## Getting Started — 4 Commands

### If you use Obsidian

```bash
git clone https://github.com/M0nkeyFl0wer/second-brain-open-kg.git
cd second-brain-open-kg
bash setup.sh
python scripts/ingest_obsidian.py --vault ~/your-obsidian-vault
```

Parses your entire vault — frontmatter, `[[wikilinks]]`, `#tags`, and body text. Notes become entities, links become edges, tags become concepts.

### If you don't use Obsidian

Works with any pile of documents. Drop files in the `ingest/` folder and run:

```bash
git clone https://github.com/M0nkeyFl0wer/second-brain-open-kg.git
cd second-brain-open-kg
bash setup.sh
mkdir ingest
cp ~/Documents/research/*.pdf ~/Documents/notes/*.txt ~/saved-articles/*.html ingest/
python scripts/ingest_folder.py
```

Supports `.txt`, `.md`, `.pdf`, `.html`. PDFs need `pdftotext` (`sudo apt install poppler-utils` on Linux, `brew install poppler` on Mac). No special formatting required — the extraction pipeline handles raw, unstructured text.

### Then search it

```bash
python scripts/search_cli.py -q "your topic" --mode hybrid
```

Everything runs locally. No API keys. No accounts. No data leaves your machine.

---

## Detailed Setup

### Prerequisites

- **Python 3.10 or later** (check: `python3 --version`)
- **[Ollama](https://ollama.com)** installed and running (handles all AI locally)
- **An Obsidian vault** (or any folder of markdown files)

### Step 1: Install

```bash
git clone https://github.com/M0nkeyFl0wer/second-brain-open-kg.git
cd second-brain-open-kg
bash setup.sh
```

`setup.sh` creates a virtual environment, installs all Python packages, downloads the spaCy language model, and pulls the Ollama models (nomic-embed-text for embeddings, llama3.2 for extraction). Takes about 5 minutes depending on your internet speed.

### Step 2: Verify

```bash
python -m second_brain.check
```

```
open-second-brain system check
========================================
  LadybugDB: 0.15.3
  PyArrow: 23.0.1
  spaCy: 3.8.14
  spaCy model: en_core_web_sm OK
  NetworkX: 3.6.1
  Ollama: OK (2 models)
  Embedding model: nomic-embed-text OK

Ontology: Ontology(8 entity types, 9 edge types)
  All checks passed.
```

If anything says NOT INSTALLED or MISSING, the check tells you exactly what to run.

### Step 3: Point at Your Vault

Either pass it on the command line:

```bash
python scripts/ingest_obsidian.py --vault ~/obsidian-vault
```

Or set it permanently in `second_brain/config.py`:

```python
VAULT_PATH = "~/obsidian-vault"
```

### Step 4: Ingest

```bash
python scripts/ingest_obsidian.py
```

Output:

```
Scanning vault: ~/obsidian-vault
Found 247 notes.

[1/247] concepts/spaced-repetition.md
  Extracted: 8 entities, 3 edges
[2/247] reading/make-it-stick.md
  Extracted: 12 entities, 5 edges
...

Bulk loading 1,847 entities...
  Loaded: 1,847
Computing entity embeddings...
Rebuilding vector indexes...

==================================================
Ingestion complete in 312.4s.
  Notes processed:     247
  Total entities:      1,847
  Total edges:         423
```

### Search Your Knowledge

```bash
# Keyword search
python scripts/search_cli.py -q "spaced repetition"

# Semantic search — finds related concepts by meaning
python scripts/search_cli.py -q "techniques for remembering things" --mode semantic

# Hybrid search — combines keyword and semantic via Reciprocal Rank Fusion
python scripts/search_cli.py -q "learning" --mode hybrid

# Hidden connections — ideas that are similar but you never linked
python scripts/search_cli.py -q "meditation" --mode hidden

# Find paths between concepts
python scripts/search_cli.py --path "meditation" "creativity"
```

**Hidden connections** are the key feature. They surface ideas like:

```
Hidden connections for: meditation

  [concept        ] neuroplasticity
                    distance: 0.187 | unlinked
  [practice       ] deep work sessions
                    distance: 0.223 | unlinked
  [concept        ] default mode network
                    distance: 0.251 | unlinked
```

These are concepts in your vault that are semantically close to "meditation" but have zero graph edges connecting them. Your brain hasn't linked them yet — but the math says they belong together.

### Analyze Your Knowledge Structure

```bash
python scripts/run_analysis.py
```

```
KNOWLEDGE GRAPH ANALYSIS
============================================================
  Entities:              1,847
  Edges:                 423
  Connected components:  89
  Largest component:     312 nodes
  Communities (Louvain): 23

KNOWLEDGE GAPS: 5
------------------------------------------------------------
  [HIGH] "cognitive science" cluster ↔ "productivity" cluster
         45 entities ↔ 38 entities | cross-edges: 0
         → How do your ideas about cognitive science and productivity relate?

SURPRISING BRIDGES: 3
------------------------------------------------------------
  "sleep architecture" (concept)
    Betweenness: 0.312 | Degree: 4
    → Bridges different areas of your thinking
```

### Daily Reflection

```bash
python scripts/daily_briefing.py
```

Generates `reflections/2026-04-04.md`:

```markdown
# Daily Reflection — 2026-04-04

## New Ideas (last 24h): 12
  5 concept, 3 insight, 2 source, 2 question

## Conflicting Beliefs
  "deliberate practice requires focus" contradicts
  "creativity requires unfocused mind-wandering"

## Knowledge Gaps
  Your ideas about [meditation, mindfulness, attention]
  and [neuroplasticity, learning, memory] are not yet connected.

## Hidden Connections
  "spaced repetition" ↔ "compound interest" (distance: 0.18)
  → Similar structure: both involve small repeated inputs
    compounding over time

## Ideas Needing Development: 8 underdeveloped
  - flow state (concept)
  - Richard Feynman (person)
```

---

## How It Works

### The Five Layers

#### 1. Obsidian Integration

Your vault is the source of truth. The ingestion pipeline reads every `.md` file and extracts:

- **YAML frontmatter** — title, tags, type, source, created date
- **`[[wikilinks]]`** — explicit connections you've made between notes
- **`#tags`** — both frontmatter and inline tags become concept entities
- **Body text** — fed through three-phase extraction

Skips `.obsidian/`, `.trash/`, `templates/`, and other non-content directories. Re-ingestion is idempotent — notes are identified by their vault-relative path hash.

#### 2. Three-Phase Extraction

Every note goes through:

**Phase 1 — Deterministic** (instant, free):
- Regex patterns for dates and structured references
- Confidence: 0.85-0.90

**Phase 2 — spaCy NER** (fast, local):
- Named entity recognition: people, organizations, locations
- Maps to PKG types: PERSON → person, ORG → source, GPE → place
- Confidence: 0.70

**Phase 3 — LLM** (slower, local via Ollama):
- Extracts concepts, insights, questions, and typed relationships
- Constrained by ontology — only produces types listed in ONTOLOGY.md
- Confidence: 0.60

#### 3. Semantic Spacetime Schema

Simple relationships use direct edges:

```
"meditation" --[SUPPORTS]--> "focus"
"Make It Stick" --[LEARNED_FROM]--> "spaced repetition"
```

Complex or multi-way relationships use **edge-nodes** — first-class nodes that represent the relationship itself:

```
"spaced repetition" --[CONNECTS]--> (similar_edge: "both compound over time") --[BINDS]--> "compound interest"
```

Four edge-node types from Semantic Spacetime theory:
- **similar_edge** — "X is like Y" (analogy, proximity)
- **contains_edge** — "X contains Y" (hierarchy, composition)
- **property_edge** — "X has property Y" (state, attribute)
- **leads_to_edge** — "X leads to Y" (causality, sequence)

Edge-nodes support hypergraphs (one relationship linking 3+ concepts) and metagraphs (thoughts about thoughts) without schema changes.

#### 4. Hidden Connections

The killer feature. For each entity with an embedding:
1. HNSW vector index finds nearest neighbors in embedding space
2. Filter out entities already connected via any edge
3. Remaining pairs = hidden connections (similar meaning, no link)

This is how you discover that "meditation" and "neuroplasticity" belong together even though you never made a `[[wikilink]]` between them.

#### 5. Community Summaries ("Zoom Out")

LadybugDB's native Louvain algorithm groups your entities into communities. For each community:
1. Top-5 entities by degree become the summary
2. Summary is embedded as a FLOAT[768] vector
3. Stored as CommunityMeta nodes with their own HNSW index

When you ask a broad question ("what do I know about learning?"), the system searches community summaries first — answering with themes rather than individual facts.

---

## Ontology

Your knowledge types, defined in `ONTOLOGY.md`:

### Entity Types

| Type | What it captures |
|------|-----------------|
| `concept` | Ideas, topics, principles, beliefs |
| `person` | Authors, mentors, friends, historical figures |
| `source` | Books, articles, podcasts, courses |
| `project` | Personal projects, initiatives |
| `insight` | Original thoughts, realizations, synthesis |
| `question` | Open questions, uncertainties |
| `practice` | Habits, methods, routines |
| `place` | Locations with personal meaning |

### Edge Types

| Type | Meaning |
|------|---------|
| `LEARNED_FROM` | Where you learned something |
| `INSPIRED_BY` | What sparked a thought |
| `CONFLICTS_WITH` | Contradicting beliefs |
| `SUPPORTS` | Reinforcing ideas |
| `PART_OF` | Hierarchy or composition |
| `PRACTICED_IN` | Where you apply a method |
| `ASKED_ABOUT` | What a question investigates |
| `ANSWERS` | What resolves a question |
| `ASSOCIATED_WITH` | Catch-all (use sparingly) |

Edit `ONTOLOGY.md` to match your thinking style. The system rejects entities that don't match — the rejection log tells you when to expand.

---

## Search Modes

| Mode | How it works | Best for |
|------|-------------|----------|
| `keyword` | Exact substring match on labels | Finding specific entities |
| `semantic` | Cosine similarity of embeddings | Finding related ideas by meaning |
| `hybrid` | Reciprocal Rank Fusion across keyword + semantic | Best general-purpose search |
| `hidden` | Vector-similar but graph-unlinked pairs | Discovering connections you missed |

---

## Privacy

**Default: fully local.** Everything runs on your machine via Ollama.

| Component | Where it runs |
|-----------|--------------|
| Your notes | Stay on disk (never copied to cloud) |
| Entity extraction | Ollama on your CPU/GPU |
| Embeddings | Ollama (nomic-embed-text, local) |
| Knowledge graph | LadybugDB directory on disk |
| Vector search | LadybugDB native HNSW index |
| Community detection | LadybugDB native Louvain |
| Analysis | Python (NetworkX) on your CPU |
| Daily reflections | Written to local markdown |

Optional hybrid mode sends non-sensitive text to a remote LLM for better extraction quality. Your graph, embeddings, and analysis always stay local.

---

## Configuration

All settings in `second_brain/config.py`:

```python
VAULT_PATH = "~/obsidian-vault"          # Your vault location
GRAPH_DIR = Path("data/graph.lbug")      # Graph database
BRIEFING_DIR = Path("reflections")       # Daily reflections output
EMBEDDING_MODEL = "nomic-embed-text"     # 768-dim local embeddings
LOCAL_EXTRACTION_MODEL = "llama3.2:3b"   # Local LLM for extraction
HIDDEN_CONNECTION_THRESHOLD = 0.3        # Max distance for hidden links
MIN_COMMUNITY_SIZE = 3                   # Min entities per community
PRUNE_AGE_DAYS = 14                      # Flag underdeveloped ideas after
```

---

## MCP Integration (AI Assistants)

The MCP server exposes your knowledge graph to AI assistants (Claude Code, etc.) via three high-level tools:

```bash
python -m second_brain.mcp_server
```

**`memory_write`** — Capture a thought. Auto-classifies, extracts entities, links to graph.

**`memory_zoom_out`** — Broad questions answered via community summaries.

**`memory_search`** — Hybrid search with graph expansion.

Configure in Claude Code's MCP settings to give your assistant persistent memory across sessions.

---

## The Stack

| Tool | Purpose |
|------|---------|
| [LadybugDB](https://ladybugdb.com) 0.15.3 | Graph database + vector storage + native algorithms (Louvain, PageRank, WCC) |
| [PyArrow](https://arrow.apache.org) | Bulk Parquet ingestion (25x faster) |
| [spaCy](https://spacy.io) | Named entity recognition (Phase 2) |
| [NetworkX](https://networkx.org) | Betweenness centrality, bridge detection, persistent homology |
| [Ollama](https://ollama.com) | Local AI: embeddings (nomic-embed-text) + extraction (llama3.2) |
| [MCP](https://modelcontextprotocol.io) | AI assistant integration (optional) |

### Why LadybugDB?

- **Embedded** — no server, one directory = one brain
- **Native vectors** — FLOAT[768] + HNSW index, no separate vector DB
- **Native algorithms** — Louvain, PageRank, WCC run inside the DB
- **Bulk loading** — COPY FROM Parquet, 25x faster than row-by-row
- **Cypher** — industry-standard query language

---

## Architecture

```
Obsidian Vault (*.md)
    │
    ▼
obsidian.py                ← Parse frontmatter, wikilinks, tags
    │
    ▼
extract.py                 ← Three-phase: regex → spaCy → LLM
    │
    ▼
graph.py                   ← LadybugDB: entities + edges + vectors + edge-nodes
    │
    ├─► vector index       (HNSW on Entity.embedding)
    ├─► FTS index          (BM25 on Entity.label/description)
    └─► algo extension     (native Louvain, PageRank, WCC)
         │
    ┌────┼────────────────┐
    ▼    ▼                ▼
search  hidden_connections  community_summaries
(RRF    (vector-similar    (Louvain → summary
hybrid)  but unlinked)      → embed → CommunityMeta)
    │         │                    │
    └─────────┼────────────────────┘
              ▼
    topology.py + briefing.py
    (gaps, bridges,       (Daily Reflection
     homology)             markdown)
```

### Database Schema

```
Entity (id, entity_type, label, description, confidence,
        source_url, provenance, timestamps, embedding[768], layer)

EdgeNode (id, semantic_type, label, weight, confidence,
          provenance, created_at, expired_at)

CommunityMeta (id, community_id, size, summary, top_entities,
               computed_at, embedding[768])

Document (id, path, title, ingested_at, chunk_count)
Chunk (id, doc_id, text, chunk_index, created_at, embedding[768])

RELATES_TO    Entity → Entity    (edge_type, weight, confidence, expired_at)
CONNECTS      Entity → EdgeNode  (role)
BINDS         EdgeNode → Entity  (role)
MENTIONED_IN  Entity → Document
CHUNK_OF      Chunk → Document
```

---

## Recipes

### Ingest a new batch of notes

```bash
# Only processes notes not already in the graph
python scripts/ingest_obsidian.py

# Force re-ingest everything
python scripts/ingest_obsidian.py --force
```

### Find what connects two ideas

```bash
python scripts/search_cli.py --path "meditation" "creativity"
```

### Discover hidden links for a concept

```bash
python scripts/search_cli.py -q "stoicism" --mode hidden
```

### Weekly reflection

```bash
python scripts/run_analysis.py    # Full topology analysis
python scripts/daily_briefing.py  # Generate reflection
```

### Check ontology health

```bash
python scripts/validate_ontology.py
```

### Query the graph at a point in time

```python
# What edges existed before October?
from second_brain.graph import Graph
g = Graph()
results = g.query("""
    MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
    WHERE r.created_at <= $cutoff AND r.expired_at = 0
    RETURN a.label, r.edge_type, b.label
    ORDER BY r.created_at DESC LIMIT 20
""", parameters={"cutoff": 1727740800})
```

### Back up your graph

```bash
tar czf brain-backup-$(date +%Y%m%d).tar.gz data/ reflections/ ONTOLOGY.md
```

---

## Troubleshooting

### "Ollama: NOT RUNNING"

```bash
ollama serve
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```

### "spaCy model: MISSING"

```bash
source .venv/bin/activate && python -m spacy download en_core_web_sm
```

### Ingestion is slow

Most time is LLM extraction (Phase 3). Use a smaller model:

```python
LOCAL_EXTRACTION_MODEL = "llama3.2:1b"  # in config.py
```

### Too many entities of one type

Run `validate_ontology.py`. If CI > 0.5, add better exotypical examples to ONTOLOGY.md for the dominant type.

### HNSW index blocks embedding updates

Vector indexes block SET operations. After bulk embedding, call:

```python
graph.rebuild_vector_indexes()
```

---

## Claude Code Skills

If you use [Claude Code](https://claude.ai/code), this repo ships with skills that wrap every script as a slash command:

| Skill | Command | What it does |
|-------|---------|-------------|
| `/ingest` | `python scripts/ingest_obsidian.py` | Scan vault, extract, embed, load |
| `/search` | `python scripts/search_cli.py` | Keyword, semantic, hybrid, hidden, path |
| `/analyze` | `python scripts/run_analysis.py` | Topology: gaps, bridges, communities, homology |
| `/briefing` | `python scripts/daily_briefing.py` | Daily Reflection markdown |
| `/validate` | `python scripts/validate_ontology.py` | Ontology health: ICR, CI, IPR |
| `/hidden` | `hidden_connections.py` | Find semantically similar but unlinked ideas |
| `/communities` | `community_summaries.py` | Louvain → embed → zoom-out queries |

### Reusable Tool Skills

The repo also includes reference skills for the underlying tools. These are portable — useful for anyone building knowledge graph tooling with Claude Code:

```
.claude/skills/tools/
├── ladybug.md       — LadybugDB: Cypher, Python API, extensions, HNSW, FTS
├── ladybug-rag.md   — Graph RAG: vector + BM25 + graph hybrid retrieval
├── networkx.md      — Centrality, communities, bridges, shortest paths
└── ripser.md        — Persistent homology for topological gap detection
```

These skills teach Claude Code how to write correct LadybugDB Cypher, use HNSW vector indexes, build NetworkX graphs from query results, and interpret persistence diagrams. Drop them in any project's `.claude/skills/` directory.

---

## File Reference

```
open-second-brain/
├── ONTOLOGY.md                         # Entity + edge types (you edit this)
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── setup.sh                            # One-command setup
├── second_brain/
│   ├── __init__.py                     # Package init
│   ├── config.py                       # All configuration
│   ├── ontology.py                     # ONTOLOGY.md parser + validator
│   ├── graph.py                        # LadybugDB: schema, CRUD, vectors, edge-nodes
│   ├── embed.py                        # Ollama embedding wrapper
│   ├── extract.py                      # Three-phase extraction pipeline
│   ├── obsidian.py                     # Vault reader: frontmatter, wikilinks, tags
│   ├── hidden_connections.py           # Semantically similar but unlinked pairs
│   ├── community_summaries.py          # Louvain communities + embedded summaries
│   ├── topology.py                     # NetworkX analysis + skeleton export
│   ├── briefing.py                     # Daily Reflection generator
│   ├── queries.py                      # All Cypher patterns (centralized)
│   ├── check.py                        # Dependency verification
│   └── mcp_server.py                   # MCP tools for AI assistants
├── scripts/
│   ├── ingest_obsidian.py              # Main entry: vault → graph
│   ├── ingest_folder.py                # Generic document ingestion
│   ├── search_cli.py                   # Search: keyword/semantic/hybrid/hidden/path
│   ├── run_analysis.py                 # Topology analysis
│   ├── daily_briefing.py               # Generate daily reflection
│   └── validate_ontology.py            # Ontology health (ICR/CI/IPR)
├── .claude/skills/
│   ├── ingest/SKILL.md                 # /ingest slash command
│   ├── search/SKILL.md                 # /search slash command
│   ├── analyze/SKILL.md                # /analyze slash command
│   ├── briefing/SKILL.md               # /briefing slash command
│   ├── validate/SKILL.md               # /validate slash command
│   ├── hidden/SKILL.md                 # /hidden slash command
│   ├── communities/SKILL.md            # /communities slash command
│   └── tools/                          # Reusable reference skills
│       ├── ladybug.md                  #   LadybugDB API + Cypher
│       ├── ladybug-rag.md              #   Graph RAG patterns
│       ├── networkx.md                 #   Centrality, communities, paths
│       └── ripser.md                   #   Persistent homology
├── docs/
│   └── privacy-guide.md                # Privacy mode comparison
├── data/                               # Graph database (gitignored)
└── reflections/                        # Generated reflections (gitignored)
```

---

## Contributing

Issues and PRs welcome. Keep it simple — this is a tool for thinking, not a framework.

## License

MIT

## Contact

Built by [Ben West](https://benwest.blog).
