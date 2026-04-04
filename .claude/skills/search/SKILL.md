# /search — Knowledge Graph Search

Search the knowledge graph by keyword, semantic similarity, hybrid (RRF), hidden connections, or path traversal.

## When to use

- User asks to find something in their knowledge graph
- User wants to discover connections between ideas
- User asks "what do I know about X"
- User asks "how does X relate to Y" (path mode)
- User asks "what am I missing" or "hidden connections" (hidden mode)

## Usage

```bash
# Keyword search (exact substring match on labels)
python scripts/search_cli.py -q "spaced repetition"

# Semantic search (by meaning, not keywords)
python scripts/search_cli.py -q "techniques for remembering" --mode semantic

# Hybrid search (RRF fusion of keyword + semantic — best general purpose)
python scripts/search_cli.py -q "learning" --mode hybrid

# Hidden connections (semantically similar but unlinked)
python scripts/search_cli.py -q "meditation" --mode hidden

# Path between two entities
python scripts/search_cli.py --path "meditation" "creativity"

# Filter by entity type
python scripts/search_cli.py -q "Feynman" --type person

# Limit results
python scripts/search_cli.py -q "learning" --mode hybrid -l 20
```

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--query`, `-q` | required (unless --path) | Search query text |
| `--path`, `-p` | — | Two entity labels to find paths between |
| `--mode`, `-m` | `keyword` | `keyword`, `semantic`, `hybrid`, `hidden` |
| `--type`, `-t` | — | Filter by entity type (concept, person, source, etc.) |
| `--limit`, `-l` | 10 | Maximum results |

## Search Modes

| Mode | Algorithm | Best for |
|------|-----------|----------|
| `keyword` | Cypher CONTAINS on labels | Finding specific named entities |
| `semantic` | Cosine similarity via HNSW/brute-force | Finding related ideas by meaning |
| `hybrid` | Reciprocal Rank Fusion (keyword + semantic) | Best general-purpose search |
| `hidden` | Vector-similar but graph-unlinked pairs | Discovering connections you missed |

## Output

- Entity list with type, confidence/score, source
- Path mode: chain of entities with edge types and confidence
- Hidden mode: unlinked entities ranked by embedding distance
