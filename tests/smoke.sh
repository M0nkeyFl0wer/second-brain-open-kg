#!/bin/bash
# Smoke test — quick check that the full pipeline runs without crashing.
# Requires Ollama running with nomic-embed-text and llama3.2:3b.
set -e
echo "=== Smoke test ==="
python -m second_brain.check
mkdir -p ingest
echo "Test document about spaced repetition and learning techniques." > ingest/smoke_test.txt
python scripts/ingest_folder.py
python scripts/search_cli.py -q "test" --limit 1
python scripts/run_analysis.py
python scripts/daily_briefing.py
python scripts/validate_ontology.py
python scripts/status.py
rm -f ingest/smoke_test.txt
echo "=== All smoke tests passed ==="
