# Idea File: Personal Knowledge Graph with Topological Verification

*In the era of LLM agents, share the idea — not the code. Give this file to your agent and it builds the tool for you.*

<img src="[static/social-card.png](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/docs/1775351442021.png)" alt="LadybugDB-cybernetic" width="100%">

### Built With

[![LadybugDB](https://img.shields.io/badge/LadybugDB-0.15.3-ff6b35?style=for-the-badge)](https://github.com/LadybugDB/ladybug)
[![NetworkX](https://img.shields.io/badge/NetworkX-3.6-2e86c1?style=for-the-badge)](https://github.com/networkx/networkx)
[![Ollama](https://img.shields.io/badge/Ollama-local_AI-000000?style=for-the-badge)](https://github.com/ollama/ollama)
[![spaCy](https://img.shields.io/badge/spaCy-NLP-09a3d5?style=for-the-badge)](https://github.com/explosion/spaCy)
[![vis-network](https://img.shields.io/badge/vis--network-graph_viz-e67e22?style=for-the-badge)](https://github.com/visjs/vis-network)
[![Ripser](https://img.shields.io/badge/Ripser-topology-8e44ad?style=for-the-badge)](https://github.com/scikit-tda/ripser.py)

---

## The Idea

You have a pile of notes, reading highlights, journal entries, project ideas, and saved articles scattered across markdown files. You link some of them manually, but most connections live only in your head. You're missing insights because your brain can't hold the full graph.

**Build a local knowledge graph on top of your notes that:**

1. Extracts entities (concepts, people, sources, insights, questions) using three passes: regex for structure, NLP for names, LLM for relationships
2. Stores everything in an embedded graph database with vector embeddings — no server, no cloud, one directory
3. Finds hidden connections: ideas that are semantically similar but you never linked
4. Detects structural gaps: clusters of knowledge that should connect but don't
5. Generates a daily reflection: new ideas, conflicting beliefs, knowledge gaps, surprising bridges
6. Exposes it all to your AI assistant via MCP so it has persistent memory across sessions

**The key insight:** the graph's *topology* — not the LLM — tells you what's missing. Persistent homology finds holes. Betweenness centrality finds bridges. Community detection finds clusters. Gap detection finds the questions you should be asking. The math is deterministic. No hallucination.

---

## Why This Matters

<img src="static/verifiable-ai-infographic.png" alt="From Probability to Proof: Engineering Verifiable AI with Ontologies and Knowledge Graphs" width="100%">

*From probability to proof: ontology-driven design, graph-based reasoning transparency, and deterministic verification replace black-box similarity search.*

From [*An Alternative Trajectory for Generative AI*](https://arxiv.org/abs/2603.14147) (Belova, Kansal, Liang, Xiao & Jha — Princeton, 2026):

> "Rather than a single generalist LLM monolith, we envision a future built on specialized small language models" grounded in "knowledge graphs, ontologies, and formal logic."

Current AI centralizes intelligence in cloud data centers. This pattern distributes it: your knowledge graph runs on your laptop, your LLM runs locally via [Ollama](https://ollama.com), your reasoning is verified by graph structure — not by trusting a confidence score.

The graph is the scaffold. The topology is the verification. The LLM is just the extraction engine.

---

## The Pattern

<img src="static/graph-analysis-architecture.png" alt="The Architecture of Graph Insights: LadybugDB + NetworkX" width="100%">

*Three layers: [LadybugDB](https://github.com/LadybugDB/ladybug) foundation (schema, columnar storage, vectorized execution) → [NetworkX](https://github.com/networkx/networkx) analysis bridge (betweenness, communities, shortest paths) → Insight layer (hairball→skeleton filtering, interactive exploration, gap discovery).*

### 1. Ontology — Define what matters to you

A markdown file listing entity types and edge types. The system rejects anything not in this file. Start with 8 types and expand when the rejection log tells you to.

```
concept, person, source, project, insight, question, practice, place
```

Each type has boundary examples: what clearly belongs, what's an edge case, and what does NOT belong (to prevent the "everything becomes concept" problem).

### 2. Three-phase extraction

Every document gets three passes:
- **Deterministic:** Regex for dates, amounts, patterns — instant, free, always correct
- **NLP:** spaCy named entity recognition — fast, local, good for people/places/organizations
- **LLM:** Local model via Ollama — slower but finds relationships and types entities against the ontology

Each entity records its provenance (which phase found it) and source (which document). Nothing enters the graph without a paper trail.

### 3. Embedded graph + vectors in one database

Use an embedded graph database (LadybugDB, KuzuDB, or similar) that supports:
- Cypher queries for graph traversal
- FLOAT[768] columns for vector embeddings
- HNSW indexes for fast similarity search
- Native graph algorithms (Louvain, PageRank, WCC)
- Bulk loading from Parquet files (25x faster than row-by-row)

One directory = one brain. Copy it, encrypt it, back it up.

### 4. Semantic Spacetime for complex relationships

Simple relationships are direct edges (SUPPORTS, CONFLICTS_WITH, LEARNED_FROM). Complex ones use edge-nodes — first-class nodes representing the relationship itself:

```
"spaced repetition" →[CONNECTS]→ (similar_edge: "both compound over time") →[BINDS]→ "compound interest"
```

Four types: similar (analogy), contains (hierarchy), property (attribute), leads_to (causality). This supports hypergraphs (3+ entities in one relationship) and metagraphs (thoughts about thoughts) without schema changes.

### 5. Hidden connections engine

For each entity with an embedding:
1. HNSW vector index finds nearest neighbors
2. Filter out entities already connected by any edge
3. Remaining pairs = ideas your brain hasn't linked yet

This is the feature that makes a knowledge graph worth maintaining. Not search — discovery.

### 6. Topology as verification

Graph algorithms run on your knowledge structure — no AI, just math:

| Algorithm | What it finds |
|-----------|--------------|
| Louvain communities | Natural topic clusters |
| Betweenness centrality | Ideas that bridge separate areas of your thinking |
| Bridge detection | Fragile single-point connections |
| Gap detection | Cluster pairs with zero cross-edges = missing knowledge |
| Persistent homology | Topological holes — higher-order structural gaps |

**The gaps are the signal.** Two large communities with zero connections means your knowledge covers two related areas that you haven't bridged. The gap question tells you what to read next.

### 7. Community summaries for "zoom out"

Louvain groups your entities into communities. Summarize each community, embed the summary, store it as a searchable node. Now broad questions ("what do I know about learning?") search community themes instead of scanning every entity.

### 8. MCP integration for AI assistants

Three tools, progressive disclosure (no Cypher exposed):

- **memory_write:** Capture a thought → auto-extract → link to graph → report hidden connections found
- **memory_zoom_out:** Broad questions → search community summaries → return themes
- **memory_search:** Hybrid search → graph expansion → return entities with paths

Your AI assistant gets persistent memory across sessions without managing files.

### 9. Dashboard for seeing your graph

FastAPI at localhost serving:
- Health metrics (ontology coverage, class imbalance, edge coverage)
- Interactive vis-network graph with type filtering and skeleton mode
- Path traversal animation: hop-by-hop visualization of multi-hop reasoning
- Hidden connections list
- Community summaries

The dashboard is how you *see* your thinking. The path animation is how you see the graph *reason*.

---

## What You Need

| Tool | What it does | Get it |
|------|-------------|--------|
| Python 3.10+ | Runtime | [python.org](https://python.org) |
| [Ollama](https://ollama.com) | Local AI — embeddings + extraction, no API key | [GitHub](https://github.com/ollama/ollama) |
| [LadybugDB](https://ladybugdb.com) | Embedded graph DB with Cypher + vectors | [GitHub](https://github.com/LadybugDB/ladybug) · `pip install real_ladybug` |
| [spaCy](https://spacy.io) | Named entity recognition | [GitHub](https://github.com/explosion/spaCy) · `pip install spacy` |
| [NetworkX](https://networkx.org) | Betweenness, bridges, homology prep | [GitHub](https://github.com/networkx/networkx) · `pip install networkx` |
| [Ripser](https://ripser.scikit-tda.org) | Persistent homology (optional) | [GitHub](https://github.com/scikit-tda/ripser.py) · `pip install ripser` |
| [vis-network](https://visjs.github.io/vis-network/) | Interactive graph visualization | [GitHub](https://github.com/visjs/vis-network) · CDN |
| A folder of markdown files | Your notes — [Obsidian](https://obsidian.md) vault or any .md/.txt/.pdf/.html | — |

---

## What Your Agent Should Build

Give this section to your LLM agent as a build prompt:

```
Build a personal knowledge graph toolkit that:

1. Reads markdown files from a folder (parse YAML frontmatter, [[wikilinks]], #tags)
2. Runs three-phase entity extraction (regex → spaCy NER → local LLM via Ollama)
3. Validates all entities against an ONTOLOGY.md file at write time
4. Stores entities + edges + embeddings in LadybugDB (embedded graph DB)
5. Bulk loads via Parquet files (COPY FROM) for speed
6. Creates HNSW vector indexes for semantic search
7. Finds hidden connections (embedding-similar but graph-unlinked pairs)
8. Runs Louvain community detection and pre-computes community summaries
9. Generates a daily reflection markdown with: new ideas, conflicting beliefs,
   knowledge gaps, hidden connections, surprising bridges, underdeveloped ideas
10. Exposes three MCP tools: memory_write, memory_zoom_out, memory_search
11. Serves a web dashboard at localhost with vis-network graph visualization
    and animated path traversal for multi-hop reasoning

All local. No cloud. No API keys. One directory = one brain.
The ontology is a markdown file the user edits.
The topology (not the LLM) tells you what's missing.
```

---

## Reference Implementation

https://github.com/M0nkeyFl0wer/second-brain-open-kg

20 commits, 7,071 lines, fully working. Fork it, or give this idea file to your agent and let it build a fresh one for your use case.

---

## The Bigger Idea

This isn't just a note-taking tool. It's a prototype for how knowledge tools should work:

- **Local-first:** Your data stays on your machine
- **Domain-specific:** Small models trained on your ontology beat giant models guessing
- **Composable:** Each component (extraction, search, topology, visualization) is independent
- **Verifiable:** Graph structure is deterministic — no hallucination in the math
- **Owned:** You own the graph, the ontology, the embeddings, and the insights

The Princeton paper argues for "societies of domain-specific superintelligences" over monolithic AGI. This is one such specialist: a knowledge graph that knows the shape of your thinking and tells you where the holes are.

Build yours. Or give this file to your agent and let it build one for you.

---

*Ben West, April 2026*
*Built with Claude Code + LadybugDB + Ollama*
