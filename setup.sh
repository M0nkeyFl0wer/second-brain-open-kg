#!/bin/bash
# Setup script for open-second-brain
# Run: bash setup.sh

set -e

echo "=== open-second-brain setup ==="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required. Install from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install Python packages
echo ""
echo "Installing Python packages..."
pip install --quiet --upgrade pip
pip install --quiet real_ladybug pyarrow pandas spacy networkx ripser ollama

# Download spaCy model
echo ""
echo "Downloading language model for NLP extraction..."
python -m spacy download en_core_web_sm --quiet

# Check Ollama
echo ""
if command -v ollama &> /dev/null; then
    echo "Ollama found. Pulling embedding model..."
    ollama pull nomic-embed-text
    echo "Pulling extraction model..."
    ollama pull llama3.2:3b
    echo "Models ready."
else
    echo "WARNING: Ollama not found."
    echo "Install from https://ollama.com/download"
    echo "Then run: ollama pull nomic-embed-text && ollama pull mistral"
fi

# Create directories
echo ""
echo "Creating directories..."
mkdir -p data ingest briefings

# Verify
echo ""
echo "Verifying installation..."
python3 -c "
import real_ladybug; print(f'  LadybugDB: {real_ladybug.__version__}')
import pyarrow; print(f'  PyArrow: {pyarrow.__version__}')
import spacy; print(f'  spaCy: {spacy.__version__}')
import networkx; print(f'  NetworkX: {networkx.__version__}')
try:
    import ripser; print(f'  Ripser: OK')
except: print('  Ripser: not available (optional)')
"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Drop documents into the ingest/ folder"
echo "  2. Run: python scripts/ingest_folder.py"
echo "  3. Run: python scripts/search_cli.py --query 'your search'"
echo "  4. Run: python scripts/run_analysis.py"
echo "  5. Run: python scripts/daily_briefing.py"
echo ""
echo "Edit ONTOLOGY.md to customize entity types for your beat."
echo "Edit second_brain/config.py to configure paths and privacy mode."
