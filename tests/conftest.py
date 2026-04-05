"""
Shared pytest fixtures for the open-second-brain test suite.

Provides:
  - ontology:          Parsed Ontology from a temp copy of ONTOLOGY.md
  - graph:             Fresh LadybugDB graph in a temp directory
  - populated_graph:   Graph with known entities and edges for query tests
  - mock_ollama:       Monkeypatch for ollama.embed and ollama.chat
"""
import pytest
import shutil
import numpy as np
from pathlib import Path


@pytest.fixture
def ontology(tmp_path):
    """Copy ONTOLOGY.md to temp dir and parse it."""
    src = Path(__file__).parent.parent / "ONTOLOGY.md"
    dst = tmp_path / "ONTOLOGY.md"
    shutil.copy(src, dst)
    from second_brain.ontology import Ontology
    return Ontology(str(dst))


@pytest.fixture
def graph(tmp_path, ontology):
    """Fresh LadybugDB graph in a temp directory."""
    from second_brain.graph import Graph
    g = Graph(tmp_path / "test.lbug", ontology)
    yield g
    g.close()


@pytest.fixture
def populated_graph(graph):
    """Graph with known test data — 6 entities and 4 edges."""
    graph.add_entity("p1", "person", "Jane Smith", confidence=0.9)
    graph.add_entity("o1", "source", "Make It Stick", confidence=0.8)
    graph.add_entity("c1", "concept", "spaced repetition", confidence=0.85)
    graph.add_entity("c2", "concept", "compound interest", confidence=0.7)
    graph.add_entity("i1", "insight", "learning compounds like interest")
    graph.add_entity("q1", "question", "does sleep affect memory?")
    graph.add_edge("c1", "o1", "LEARNED_FROM")
    graph.add_edge("c1", "c2", "SUPPORTS")
    graph.add_edge("i1", "c1", "INSPIRED_BY")
    graph.add_edge("q1", "c1", "ASKED_ABOUT")
    return graph


@pytest.fixture
def mock_ollama(monkeypatch):
    """Mock Ollama so tests don't need a running server.

    Patches ollama.embed to return deterministic 768-dim vectors
    and ollama.chat to return empty extraction results.
    """
    def fake_embed(model, input, **kwargs):
        """Return reproducible embeddings seeded by input text."""
        if isinstance(input, list):
            embeddings = []
            for text in input:
                seed = hash(text) % (2**31)
                rng = np.random.RandomState(seed)
                embeddings.append(rng.randn(768).tolist())
            return {"embeddings": embeddings}
        seed = hash(input) % (2**31)
        rng = np.random.RandomState(seed)
        return {"embeddings": [rng.randn(768).tolist()]}

    def fake_chat(model, messages, format=None, **kwargs):
        return {"message": {"content": '{"entities": [], "edges": []}'}}

    monkeypatch.setattr("ollama.embed", fake_embed)
    monkeypatch.setattr("ollama.chat", fake_chat)
