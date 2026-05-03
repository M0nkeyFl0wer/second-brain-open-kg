"""
Nightly enrichment script — LLM pass to extract triplets from recent notes.

Schedule: runs every 4 hours via systemd timer (duckdb has no pg_cron).
Can also be run manually: python scripts/enrich.py

What it does:
1. Find notes modified since last enrichment run
2. Chunk and embed them (if not already)
3. Extract triplets (entity-relationship-entity with evidence)
4. Write to graph (entities + edges)
5. Log enrichment results to enrichment.log

Enrichment is epistemically sovereign — no engagement feedback,
no audience data flows back into the KG (per kg-ingestion principle).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from second_brain.chunk_store import ChunkStore
from second_brain.graph import GraphWriter, PipelineError
from second_brain.ontology import (
    slugify,
    validate_edge,
)
from second_brain.extract import extract_triplets_from_text

VAULT_PATH = Path.home() / "obsidian-vault"
DATA_DIR = Path(__file__).parent.parent / "data"
CHUNK_STORE_PATH = DATA_DIR / "chunks.duckdb"
GRAPH_DB_PATH = DATA_DIR / "brain.ldb"
LAST_RUN_FILE = DATA_DIR / "enrichment_last_run.txt"
ENRICHMENT_LOG = DATA_DIR / "enrichment.log"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "edge_types.json"

# LLM config (Ollama)
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen3:14b"


def get_last_run_time() -> datetime:
    """Get timestamp of last successful enrichment run."""
    if LAST_RUN_FILE.exists():
        with open(LAST_RUN_FILE) as f:
            ts = f.read().strip()
            return datetime.fromisoformat(ts)
    # First run: process all notes
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def set_last_run_time(ts: datetime) -> None:
    """Update last run timestamp."""
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_RUN_FILE, "w") as f:
        f.write(ts.isoformat())


def log(msg: str) -> None:
    """Log to enrichment.log with timestamp."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    ENRICHMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ENRICHMENT_LOG, "a") as f:
        f.write(f"[{stamp}] {msg}\n")
    print(f"[enrich] {msg}")


def get_edge_types() -> list[str]:
    """Load enabled edge types from config."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = json.load(f)
            return config.get("edge_types", [])
    return []


def get_recent_notes(since: datetime) -> list[Path]:
    """Find notes modified since last enrichment run."""
    if not VAULT_PATH.exists():
        log(f"Vault not found: {VAULT_PATH}")
        return []

    notes = []
    for md in VAULT_PATH.rglob("*.md"):
        mtime = datetime.fromtimestamp(md.stat().st_mtime, tz=timezone.utc)
        if mtime > since:
            notes.append(md)
    return notes


def enrich_note(
    note_path: Path,
    chunk_store: ChunkStore,
    writer: GraphWriter,
    edge_types: list[str],
) -> dict[str, int]:
    """
    Enrich a single note: chunk → embed → extract triplets → write to graph.

    Returns {entities_written, edges_written, chunks_created}.
    """
    results = {"entities": 0, "edges": 0, "chunks": 0}

    # Read note content
    with open(note_path) as f:
        content = f.read().strip()

    if not content:
        return results

    title = note_path.stem
    source_uri = str(note_path)

    # Chunk the note (split by paragraphs)
    chunks = chunk_text(content, title, source_uri)

    # Check which chunks already have embeddings
    existing_chunks = []
    for chunk in chunks:
        existing = chunk_store.get_chunk_by_id(chunk["id"])
        if existing and existing.get("embedded_at"):
            existing_chunks.append(chunk)

    # Skip fully embedded notes
    if len(existing_chunks) == len(chunks):
        log(f"  {note_path.name}: already current ({len(chunks)} chunks)")
        return results

    # Write new chunks
    for chunk in chunks:
        results["chunks"] += 1

    # Extract triplets via LLM
    all_entities = []
    all_edges = []

    for chunk in chunks:
        triplets = extract_triplets_from_text(
            chunk["body"],
            edge_types=edge_types,
            model=OLLAMA_MODEL,
            host=OLLAMA_HOST,
        )
        all_entities.extend(triplets.get("entities", []))
        all_edges.extend(triplets.get("edges", []))

    # Deduplicate entities by slug
    seen = {}
    for entity in all_entities:
        sid = slugify(entity["label"])
        if sid not in seen or entity.get("confidence", 0) > seen[sid].get("confidence", 0):
            seen[sid] = entity
    unique_entities = list(seen.values())

    # Validate edges (domain/range check)
    valid_edges = []
    for edge in all_edges:
        # Look up entity types
        source_type = _resolve_entity_type(edge.get("source"), unique_entities)
        target_type = _resolve_entity_type(edge.get("target"), unique_entities)
        is_valid, err = validate_edge(edge.get("type", ""), source_type, target_type)
        if is_valid:
            valid_edges.append(edge)

    # Write entities
    for entity in unique_entities:
        if writer.write_entity({
            "id": slugify(entity["label"]),
            "label": entity["label"],
            "entity_type": entity.get("type", "concept"),
            "meta": {"source": source_uri},
        }):
            results["entities"] += 1

    # Write edges
    for edge in valid_edges:
        source_id = slugify(edge.get("source", ""))
        target_id = slugify(edge.get("target", ""))
        if writer.write_edge({
            "source": source_id,
            "target": target_id,
            "type": edge.get("type"),
            "evidence": edge.get("evidence", ""),
            "confidence": edge.get("confidence", 0.5),
            "extraction": "LLM",
        }):
            results["edges"] += 1

    log(f"  {note_path.name}: {results['entities']} entities, {results['edges']} edges, {results['chunks']} chunks")
    return results


def _resolve_entity_type(label: str, entities: list[dict]) -> str:
    """Resolve the entity_type for a label from the entity list."""
    for e in entities:
        if e.get("label") == label:
            return e.get("type", "concept")
    return "concept"


def chunk_text(content: str, title: str, source_uri: str) -> list[dict[str, Any]]:
    """
    Split note content into chunks by paragraph.

    Returns list of chunk dicts with id, doc_id, source_uri, body, chunk_index.
    """
    import uuid
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks = []
    for i, para in enumerate(paragraphs):
        chunk_id = str(uuid.uuid5(uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"), f"{source_uri}:{i}"))
        chunks.append({
            "id": chunk_id,
            "doc_id": slugify(title),
            "source_uri": source_uri,
            "title": title,
            "body": para,
            "chunk_index": i,
        })
    return chunks


def main() -> None:
    """Run enrichment pass on all notes modified since last run."""
    log("=== Starting enrichment pass ===")

    start = datetime.now(timezone.utc)
    edge_types = get_edge_types()

    if not edge_types:
        log("No edge types configured. Skipping (run onboard.py first).")
        return

    last_run = get_last_run_time()
    log(f"Processing notes modified since {last_run.isoformat()}")

    recent_notes = get_recent_notes(last_run)
    log(f"Found {len(recent_notes)} notes to process")

    if not recent_notes:
        log("No new notes to process")
        set_last_run_time(start)
        return

    # Initialize stores
    chunk_store = ChunkStore(CHUNK_STORE_PATH)
    writer = GraphWriter(GRAPH_DB_PATH)

    try:
        writer.init_schema()

        total_entities = 0
        total_edges = 0
        total_chunks = 0
        errors = 0

        for note_path in recent_notes:
            try:
                result = enrich_note(note_path, chunk_store, writer, edge_types)
                total_entities += result["entities"]
                total_edges += result["edges"]
                total_chunks += result["chunks"]
            except PipelineError as ex:
                log(f"  Pipeline error on {note_path.name}: {ex}")
                errors += 1
            except Exception as ex:
                log(f"  Error on {note_path.name}: {ex}")
                errors += 1

        writer.checkpoint()
        set_last_run_time(start)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        log(f"=== Enrichment complete: {total_entities} entities, {total_edges} edges, {total_chunks} chunks in {elapsed:.1f}s ({errors} errors) ===")

    finally:
        writer.close()
        chunk_store.close()


if __name__ == "__main__":
    main()