"""
Configuration for open-second-brain.
Edit this file to match your setup. Defaults are fully local — no cloud needed.
"""
from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================

# Where the graph database lives (LadybugDB directory)
GRAPH_DIR = Path("data/graph.lbug")

# Embedding dimension (nomic-embed-text output)
EMBEDDING_DIM = 768

# Where documents go for ingestion
INGEST_DIR = Path("ingest")

# Where daily briefings are written
BRIEFING_DIR = Path("briefings")

# Optional: path to your Obsidian vault for briefing delivery
# Leave empty to skip Obsidian integration
OBSIDIAN_VAULT = ""  # e.g., "~/obsidian-vault/investigations"

# =============================================================================
# PRIVACY MODE
# =============================================================================

# "local"  — All extraction via Ollama. Nothing leaves your machine.
#            Best for: sensitive sources, confidential material, default use
#
# "hybrid" — Embeddings local. Entity extraction via remote LLM with
#            zero-data-retention (ZDR). Better quality on complex documents.
#            Best for: non-sensitive public records, published material
#
# "remote" — Everything via remote API. Not recommended for sensitive material.
#            Best for: bulk processing of public datasets only

PRIVACY_MODE = "local"

# =============================================================================
# LOCAL MODELS (used in "local" and "hybrid" modes)
# =============================================================================

# Embedding model (runs via Ollama, ~60ms per chunk)
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768

# Local extraction model (runs via Ollama, used in "local" mode)
LOCAL_EXTRACTION_MODEL = "llama3.2:3b"  # or "mistral", "gemma2"

# =============================================================================
# REMOTE MODELS (only used in "hybrid" and "remote" modes)
# =============================================================================

# Remote API for extraction (only if PRIVACY_MODE != "local")
# Use providers with zero-data-retention (ZDR) policies.
# See docs/privacy-guide.md for provider recommendations.
REMOTE_API_BASE = ""      # e.g., "https://api.anthropic.com/v1"
REMOTE_MODEL = ""         # e.g., "claude-haiku-4-5-20251001"
# API key: set via environment variable NEWSROOM_API_KEY, never hardcode here

# =============================================================================
# EXTRACTION
# =============================================================================

# Minimum confidence for extracted entities (0.0-1.0)
MIN_CONFIDENCE = 0.5

# Maximum entities per document (safety limit)
MAX_ENTITIES_PER_DOC = 200

# Deduplication threshold (cosine similarity above this = likely duplicate)
DEDUP_THRESHOLD = 0.92

# =============================================================================
# ANALYSIS
# =============================================================================

# Run analysis automatically after ingestion
AUTO_ANALYSIS = False

# Pruning: flag unlinked entities older than this many days
PRUNE_AGE_DAYS = 7

# Gap detection: minimum community size to consider for gap analysis
MIN_COMMUNITY_SIZE = 5

# Gap detection: maximum cross-edges for a pair to be flagged as a gap
MAX_CROSS_EDGES_FOR_GAP = 3

# Betweenness centrality: top N entities to flag as structurally important
TOP_BETWEENNESS = 10

# =============================================================================
# DAILY BRIEFING
# =============================================================================

# Include these sections in the daily briefing
BRIEFING_SECTIONS = [
    "new_entities",          # Entities added in last 24h
    "contradictions",        # CONTRADICTS edges found
    "structural_gaps",       # Community pairs with low cross-connection
    "surprising_connections", # High betweenness on low-frequency entities
    "unlinked_entities",     # Entities needing attention
]
