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

# Path to your Obsidian vault (required for vault ingestion)
VAULT_PATH = ""  # e.g., "~/obsidian-vault" or "~/Documents/SecondBrain"

# Where daily reflections are written
BRIEFING_DIR = Path("reflections")

# Directories to skip when scanning the vault
VAULT_IGNORE_DIRS = {".obsidian", ".trash", ".git", "templates", "node_modules"}

# =============================================================================
# PRIVACY MODE
# =============================================================================

# "local"  — All extraction via Ollama. Nothing leaves your machine.
# "hybrid" — Embeddings local. Extraction via remote LLM with ZDR.
# "remote" — Everything via remote API. Not recommended for personal notes.

PRIVACY_MODE = "local"

# =============================================================================
# LOCAL MODELS
# =============================================================================

EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768

LOCAL_EXTRACTION_MODEL = "llama3.2:3b"  # or "mistral", "gemma2"

# =============================================================================
# REMOTE MODELS (only used in "hybrid" and "remote" modes)
# =============================================================================

REMOTE_API_BASE = ""
REMOTE_MODEL = ""
# API key: set via environment variable SECONDBRAIN_API_KEY

# =============================================================================
# EXTRACTION
# =============================================================================

MIN_CONFIDENCE = 0.5
MAX_ENTITIES_PER_DOC = 200
DEDUP_THRESHOLD = 0.92

# =============================================================================
# HIDDEN CONNECTIONS
# =============================================================================

# Minimum cosine similarity to flag as a hidden connection
HIDDEN_CONNECTION_THRESHOLD = 0.7

# Number of nearest neighbors to check per entity
HIDDEN_CONNECTION_CANDIDATES = 20

# =============================================================================
# ANALYSIS
# =============================================================================

AUTO_ANALYSIS = False
PRUNE_AGE_DAYS = 14  # Longer for personal notes — ideas take time
MIN_COMMUNITY_SIZE = 3  # Smaller communities matter in personal graphs
MAX_CROSS_EDGES_FOR_GAP = 2
TOP_BETWEENNESS = 10

# =============================================================================
# DAILY REFLECTION
# =============================================================================

BRIEFING_SECTIONS = [
    "new_ideas",              # Entities added in last 24h
    "conflicting_beliefs",    # CONFLICTS_WITH edges found
    "knowledge_gaps",         # Community pairs with low cross-connection
    "hidden_connections",     # Semantically similar but unlinked entities
    "surprising_bridges",     # High betweenness on low-frequency entities
    "underdeveloped_ideas",   # Entities needing more connections
]
