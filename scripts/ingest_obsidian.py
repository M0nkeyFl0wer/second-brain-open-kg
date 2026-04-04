#!/usr/bin/env python3
"""
Ingest notes from an Obsidian vault into the knowledge graph.
Parses wikilinks, frontmatter, tags. Runs three-phase extraction.
Idempotent — only processes new or modified notes.
"""
import sys
import time
import argparse

sys.path.insert(0, ".")

from second_brain.graph import Graph
from second_brain.extract import Extractor
from second_brain.embed import embed_text
from second_brain.ontology import Ontology
from second_brain.obsidian import scan_vault, chunk_text
from second_brain import config


def main():
    parser = argparse.ArgumentParser(description="Ingest Obsidian vault")
    parser.add_argument("--vault", "-v", default=config.VAULT_PATH,
                        help="Path to Obsidian vault")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Re-ingest all notes (ignore existing)")
    args = parser.parse_args()

    if not args.vault:
        print("No vault path configured.")
        print("Set VAULT_PATH in second_brain/config.py or use --vault")
        return

    print(f"Scanning vault: {args.vault}")
    notes = scan_vault(args.vault)
    print(f"Found {len(notes)} notes.\n")

    if not notes:
        return

    ontology = Ontology()
    graph = Graph(ontology=ontology)
    extractor = Extractor(ontology)

    # Check which notes are already ingested
    if not args.force:
        existing = set()
        for doc in graph.query("MATCH (d:Document) RETURN d.id AS id"):
            existing.add(doc["id"])
        new_notes = [n for n in notes if n["doc_id"] not in existing]
        if len(new_notes) < len(notes):
            print(f"Skipping {len(notes) - len(new_notes)} already-ingested notes.")
        notes = new_notes

    if not notes:
        print("All notes already ingested. Use --force to re-ingest.")
        return

    all_entities = []
    all_edges = []
    t_start = time.time()

    for i, note in enumerate(notes, 1):
        print(f"[{i}/{len(notes)}] {note['relative_path']}")

        # Register document
        graph.add_document(note["doc_id"], note["path"], note["title"])

        # Run extraction on body text
        result = extractor.extract_from_text(
            note["body"], source_url=note["path"], doc_id=note["doc_id"])
        print(f"  Extracted: {len(result['entities'])} entities, "
              f"{len(result['edges'])} edges")

        # Add wikilinks as edges (note-to-note connections)
        if note["wikilinks"]:
            print(f"  Wikilinks: {len(note['wikilinks'])}")

        # Add tags as entities
        for tag in note["tags"]:
            tag_entity = {
                "id": f"tag_{tag}",
                "entity_type": "concept",
                "label": tag,
                "description": f"Tag: #{tag}",
                "confidence": 0.8,
                "source_url": note["path"],
                "provenance": "obsidian_tag",
            }
            result["entities"].append(tag_entity)

        all_entities.extend(result["entities"])
        all_edges.extend(result["edges"])

    # Bulk load entities
    if all_entities:
        print(f"\nBulk loading {len(all_entities)} entities...")
        loaded = graph.bulk_add_entities(all_entities)
        print(f"  Loaded: {loaded}")

        # Embed entity descriptions
        print("Computing entity embeddings...")
        for entity in all_entities:
            embed_str = f"{entity['label']}: {entity.get('description', '')}"
            try:
                emb = embed_text(embed_str)
                graph.set_embedding(entity["id"], emb)
            except Exception as e:
                print(f"  Embedding failed for {entity['label']}: {e}")

    if all_edges:
        print(f"Loading {len(all_edges)} edges...")
        loaded = graph.bulk_add_edges(all_edges)
        print(f"  Loaded: {loaded}")

    # Rebuild HNSW vector indexes after bulk embedding
    print("Rebuilding vector indexes...")
    graph.rebuild_vector_indexes()

    # Summary
    elapsed = time.time() - t_start
    print(f"\n{'=' * 50}")
    print(f"Ingestion complete in {elapsed:.1f}s.")
    print(f"  Notes processed:     {len(notes)}")
    print(f"  Total entities:      {graph.entity_count()}")
    print(f"  Total edges:         {graph.edge_count()}")
    print(f"  Total documents:     {graph.document_count()}")
    print(f"\nNext steps:")
    print(f"  Search:    python scripts/search_cli.py -q 'your query'")
    print(f"  Analyze:   python scripts/run_analysis.py")
    print(f"  Reflect:   python scripts/daily_briefing.py")

    # Ontology rejections
    rejections = ontology.get_rejection_counts()
    if rejections:
        print(f"\nOntology rejections:")
        for type_name, count in list(rejections.items())[:10]:
            print(f"  {type_name}: {count}")
        print(f"  Tip: Consider adding frequently rejected types to ONTOLOGY.md")

    graph.close()


if __name__ == "__main__":
    main()
