# /ingest — Obsidian Vault Ingestion

Ingest notes from an Obsidian vault into the knowledge graph. Parses frontmatter, wikilinks, tags. Runs three-phase extraction (deterministic, spaCy NER, LLM). Bulk loads entities, computes embeddings, rebuilds HNSW indexes.

## When to use

- User says "ingest my vault", "add my notes", "scan obsidian", "update the graph"
- After user adds new notes to their vault
- When user wants to re-process all notes (use --force)

## Usage

```bash
# Ingest new/modified notes only (idempotent)
python scripts/ingest_obsidian.py

# Specify vault path
python scripts/ingest_obsidian.py --vault ~/path/to/vault

# Force re-ingest everything
python scripts/ingest_obsidian.py --force
```

## Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--vault`, `-v` | `config.VAULT_PATH` | Path to Obsidian vault |
| `--force`, `-f` | false | Re-ingest all notes, not just new ones |

## Output

- Number of notes processed
- Entities extracted per note (with edge counts)
- Wikilinks and tags detected
- Total entities, edges, documents in graph
- Ontology rejection summary (types not in ONTOLOGY.md)

## Requires

- Ollama running with `nomic-embed-text` and extraction model
- VAULT_PATH configured in `second_brain/config.py` (or passed via --vault)

## Notes

- Skips `.obsidian/`, `.trash/`, `templates/`, `.git/`
- Notes identified by vault-relative path hash — moving a file creates a new entity
- Tags become `concept` entities, wikilinks become `ASSOCIATED_WITH` edges
- After ingestion, HNSW vector indexes are rebuilt automatically
