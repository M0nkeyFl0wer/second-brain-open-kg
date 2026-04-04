"""Embedding computation via Ollama. Runs locally, nothing leaves the machine."""
import ollama
from . import config


def embed_text(text: str) -> list[float]:
    """Compute embedding for a text string using local Ollama."""
    response = ollama.embed(model=config.EMBEDDING_MODEL, input=text)
    return response["embeddings"][0]


def embed_batch(texts: list[str], batch_size: int = 50) -> list[list[float]]:
    """
    Compute embeddings for multiple texts.
    Batches internally to avoid overwhelming Ollama on large sets.
    """
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = ollama.embed(model=config.EMBEDDING_MODEL, input=batch)
        all_embeddings.extend(response["embeddings"])
    return all_embeddings
