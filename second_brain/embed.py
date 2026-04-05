"""
Embedding computation via Ollama. Runs locally, nothing leaves the machine.
Includes timeout protection — if Ollama hangs (model loading, GPU OOM),
calls fail after 30 seconds rather than blocking forever.
"""
import logging

import ollama

from . import config

logger = logging.getLogger(__name__)

# Timeout in seconds for embedding calls. Ollama can hang during model
# loading or GPU out-of-memory. 30s is generous for a single embed call.
EMBED_TIMEOUT = 30


def embed_text(text: str) -> list[float]:
    """Compute embedding for a text string using local Ollama.
    Raises RuntimeError if Ollama is unreachable or times out."""
    try:
        response = ollama.embed(
            model=config.EMBEDDING_MODEL, input=text,
            options={"timeout": EMBED_TIMEOUT})
        return response["embeddings"][0]
    except Exception as e:
        logger.warning("Embedding failed: %s", e)
        raise


def embed_batch(texts: list[str], batch_size: int = 50) -> list[list[float]]:
    """
    Compute embeddings for multiple texts.
    Batches internally to avoid overwhelming Ollama on large sets.
    Raises on first failure — caller should handle partial results.
    """
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            response = ollama.embed(
                model=config.EMBEDDING_MODEL, input=batch,
                options={"timeout": EMBED_TIMEOUT})
            all_embeddings.extend(response["embeddings"])
        except Exception as e:
            logger.warning("Batch embedding failed at offset %d: %s", i, e)
            raise
    return all_embeddings
