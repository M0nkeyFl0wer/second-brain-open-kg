#!/usr/bin/env python3
"""
Ingest documents from the ingest/ folder into the knowledge graph.
Supports: .txt, .md, .pdf, .html
Uses COPY FROM Parquet for bulk entity loading.
"""
import sys
import hashlib
import time
from pathlib import Path

sys.path.insert(0, ".")

from second_brain.graph import Graph
from second_brain.extract import Extractor
from second_brain.embed import embed_text, embed_batch
from second_brain.ontology import Ontology
from second_brain import config


def read_document(path: Path) -> str:
    """Read document content. Handles txt, md, html. PDF needs pdftotext."""
    suffix = path.suffix.lower()

    if suffix in (".txt", ".md"):
        return path.read_text(errors="replace")

    if suffix == ".html":
        try:
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []

                def handle_data(self, data):
                    self.text.append(data)

            parser = TextExtractor()
            parser.feed(path.read_text(errors="replace"))
            return " ".join(parser.text)
        except Exception:
            return path.read_text(errors="replace")

    if suffix == ".pdf":
        try:
            import subprocess
            result = subprocess.run(
                ["pdftotext", str(path), "-"],
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout
        except FileNotFoundError:
            print(f"  Warning: pdftotext not found. Install: sudo apt install poppler-utils")
            return ""
        except Exception as e:
            print(f"  Warning: Could not read PDF {path.name}: {e}")
            return ""

    print(f"  Skipping unsupported format: {path.name}")
    return ""


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for embedding."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def main():
    ingest_dir = getattr(config, "INGEST_DIR", __import__("pathlib").Path("ingest"))
    if not ingest_dir.exists():
        ingest_dir.mkdir(parents=True)
        print(f"Created ingest directory: {ingest_dir}/")
        print(f"Add documents there and run again.")
        return

    files = list(ingest_dir.iterdir())
    supported = [f for f in files
                 if f.is_file() and f.suffix.lower() in (".txt", ".md", ".pdf", ".html")]

    if not supported:
        print(f"No supported documents in {ingest_dir}/")
        print(f"Supported formats: .txt, .md, .pdf, .html")
        return

    print(f"Found {len(supported)} documents to ingest.\n")

    ontology = Ontology()
    graph = Graph(ontology=ontology)
    extractor = Extractor(ontology)

    all_entities = []
    all_edges = []
    total_chunks = 0
    t_start = time.time()

    for i, filepath in enumerate(supported, 1):
        print(f"[{i}/{len(supported)}] {filepath.name}")

        text = read_document(filepath)
        if not text.strip():
            print(f"  Empty or unreadable, skipping.")
            continue

        doc_id = hashlib.sha256(str(filepath).encode()).hexdigest()[:16]
        source_url = str(filepath)

        # Register document
        graph.add_document(doc_id, str(filepath), filepath.stem)

        # Extract entities and relationships
        result = extractor.extract_from_text(
            text, source_url=source_url, doc_id=doc_id)
        print(f"  Extracted: {len(result['entities'])} entities, "
              f"{len(result['edges'])} edges")

        # Compute embeddings for chunks
        chunks = chunk_text(text)
        if chunks:
            embeddings = embed_batch(chunks)
            total_chunks += len(chunks)
            print(f"  Embedded: {len(chunks)} chunks")

            # Store chunk embeddings on the entities they mention
            # (For now, embed entity descriptions directly after bulk load)

        all_entities.extend(result["entities"])
        all_edges.extend(result["edges"])

    # Bulk load entities
    if all_entities:
        print(f"\nBulk loading {len(all_entities)} entities...")
        loaded = graph.bulk_add_entities(all_entities)
        print(f"  Loaded: {loaded}")

        # Embed entity descriptions and store vectors
        print(f"Computing entity embeddings...")
        for entity in all_entities:
            embed_text_str = f"{entity['label']}: {entity.get('description', '')}"
            try:
                emb = embed_text(embed_text_str)
                graph.set_embedding(entity["id"], emb)
            except Exception as e:
                print(f"  Embedding failed for {entity['label']}: {e}")
    else:
        print("\nNo entities extracted.")

    if all_edges:
        print(f"Loading {len(all_edges)} edges...")
        loaded = graph.bulk_add_edges(all_edges)
        print(f"  Loaded: {loaded}")

    # Summary
    elapsed = time.time() - t_start
    print(f"\n{'=' * 50}")
    print(f"Ingestion complete in {elapsed:.1f}s.")
    print(f"  Documents processed: {len(supported)}")
    print(f"  Chunks embedded:     {total_chunks}")
    print(f"  Total entities:      {graph.entity_count()}")
    print(f"  Total edges:         {graph.edge_count()}")
    print(f"  Total documents:     {graph.document_count()}")
    print(f"\nNext steps:")
    print(f"  Search:    python scripts/search_cli.py -q 'your query'")
    print(f"  Analyze:   python scripts/run_analysis.py")
    print(f"  Briefing:  python scripts/daily_briefing.py")

    # Show ontology rejections
    rejections = ontology.get_rejection_counts()
    if rejections:
        print(f"\nOntology rejections (types not in ONTOLOGY.md):")
        for type_name, count in list(rejections.items())[:10]:
            print(f"  {type_name}: {count} rejections")
        print(f"  Tip: Consider adding frequently rejected types to ONTOLOGY.md")

    graph.close()


if __name__ == "__main__":
    main()
