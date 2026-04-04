# /ingest-folder — Document Folder Ingestion

Ingest unstructured documents from a folder into the knowledge graph. For users who don't use Obsidian — works with any pile of text files, PDFs, markdown, or HTML.

## When to use

- User has documents that aren't in an Obsidian vault
- User says "ingest these files", "add these PDFs", "process this folder"
- User has a mix of .txt, .md, .pdf, .html files

## Usage

```bash
# Drop files into ingest/ folder, then run
cp ~/Documents/*.pdf ~/notes/*.txt ingest/
python scripts/ingest_folder.py
```

## Supported Formats

| Format | How it's read |
|--------|--------------|
| `.txt` | Direct read |
| `.md` | Direct read (no frontmatter parsing — use ingest_obsidian.py for that) |
| `.pdf` | Via `pdftotext` (install: `sudo apt install poppler-utils`) |
| `.html` | Stripped of tags, text extracted |

## Output

- Entities extracted per document (three-phase: regex, spaCy, LLM)
- Bulk loaded into graph with embeddings
- Ontology rejection summary

## Notes

- Place files in `ingest/` directory (created automatically if missing)
- Each file identified by content hash — re-running skips already-ingested files
- For Obsidian vaults with wikilinks and frontmatter, use `/ingest` instead
