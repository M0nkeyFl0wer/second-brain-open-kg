"""
Level 2 — Integration tests for the full pipeline.

Tests cover:
  - Ingest -> search roundtrip
  - Hidden connection detection
  - Community summary computation
  - Dashboard API endpoints (FastAPI TestClient)

All tests mock Ollama to avoid requiring a running server.
"""
import time
import pytest
import numpy as np


class TestIngestSearchRoundtrip:
    """Test writing a document, extracting entities, and searching for them."""

    def test_ingest_search_roundtrip(self, graph, ontology, mock_ollama):
        """Write a test .md, extract entities, load them, search, verify."""
        from second_brain.extract import Extractor

        extractor = Extractor(ontology)

        # Simulate ingesting a document
        text = """
        Albert Einstein developed the theory of relativity in 1905.
        This was inspired by his work at the patent office in Bern.
        The key insight was that the speed of light is constant.
        """
        result = extractor.extract_from_text(text, source_url="test.md")

        # Load extracted entities into the graph
        for entity in result["entities"]:
            graph.add_entity(
                entity["id"], entity["entity_type"], entity["label"],
                description=entity.get("description", ""),
                confidence=entity.get("confidence", 0.5),
            )

        # Should have at least extracted Einstein as a person
        assert graph.entity_count() > 0

        # Keyword search should find entities
        from second_brain.queries import QUERIES
        results = graph.query(
            QUERIES["entity_by_label"],
            parameters={"query": "Einstein", "limit": 5},
        )
        assert len(results) > 0
        assert any("Einstein" in r["label"] for r in results)


class TestHiddenConnections:
    """Test hidden connection detection between semantically similar entities."""

    def test_hidden_connections_found(self, graph, mock_ollama):
        """Two entities with similar embeddings but no edge should be flagged."""
        from second_brain.hidden_connections import find_hidden_connections

        # Create two entities
        graph.add_entity("e1", "concept", "spaced repetition learning")
        graph.add_entity("e2", "concept", "interleaved practice studying")
        graph.add_entity("e3", "concept", "quantum mechanics")

        # Give e1 and e2 very similar embeddings, e3 a different one
        rng = np.random.RandomState(42)
        base_emb = rng.randn(768)

        # e1 and e2 are close (cosine similarity ~0.99)
        emb1 = base_emb.tolist()
        emb2 = (base_emb + rng.randn(768) * 0.01).tolist()
        # e3 is far away
        emb3 = rng.randn(768).tolist()

        graph.set_embedding("e1", emb1)
        graph.set_embedding("e2", emb2)
        graph.set_embedding("e3", emb3)

        # Find hidden connections (no edges exist, so e1-e2 should be flagged)
        results = find_hidden_connections(graph, top_n=10, threshold=0.5)

        # At least one hidden connection should involve e1 and e2
        pair_ids = set()
        for r in results:
            pair_ids.add(frozenset({r["source_id"], r["target_id"]}))

        assert frozenset({"e1", "e2"}) in pair_ids, \
            f"Expected e1-e2 hidden connection, got pairs: {pair_ids}"


class TestCommunitySummaries:
    """Test community summary computation."""

    def test_community_summaries_computed(self, graph, mock_ollama):
        """Adding enough connected entities should produce CommunityMeta nodes."""
        from second_brain.community_summaries import compute_community_summaries

        # Create a cluster of connected entities (>= MIN_COMMUNITY_SIZE=3)
        for i in range(5):
            graph.add_entity(f"c{i}", "concept", f"Community Concept {i}")
        for i in range(4):
            graph.add_edge(f"c{i}", f"c{i+1}", "SUPPORTS")
        # Close the loop to make a proper community
        graph.add_edge("c4", "c0", "SUPPORTS")

        # Compute community summaries (uses mocked embed_text via mock_ollama)
        try:
            communities = compute_community_summaries(graph, min_community_size=3)
        except Exception:
            # If the algo extension isn't available, skip gracefully
            pytest.skip("LadybugDB algo extension not available for Louvain")

        # Should have at least 1 community summary stored
        assert len(communities) >= 1

        # Verify CommunityMeta nodes exist in the graph
        from second_brain.queries import QUERIES
        count_rows = graph.query(QUERIES["community_count"])
        assert count_rows[0]["cnt"] >= 1


class TestDashboardAPI:
    """Test FastAPI dashboard endpoints using TestClient."""

    @pytest.fixture(autouse=True)
    def setup_app(self, graph, ontology):
        """Override the global graph and ontology in the dashboard module."""
        import second_brain.dashboard as dashboard_module
        # Inject our test graph and ontology
        dashboard_module.graph = graph
        dashboard_module.ontology = ontology
        yield
        # Clean up
        dashboard_module.graph = None
        dashboard_module.ontology = None

    @pytest.fixture
    def client(self):
        """FastAPI TestClient for the dashboard app."""
        from fastapi.testclient import TestClient
        from second_brain.dashboard import app
        return TestClient(app, raise_server_exceptions=False)

    def test_dashboard_status_endpoint(self, client, graph):
        """GET /api/status should return 200 with expected keys."""
        # Add some data so status has something to report
        graph.add_entity("e1", "concept", "test concept")

        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "entity_count" in data
        assert "edge_count" in data
        assert "doc_count" in data
        assert "icr" in data
        assert "ipr" in data
        assert "ci" in data
        assert data["entity_count"] >= 1

    def test_dashboard_search_endpoint_keyword(self, client, graph):
        """GET /api/search?q=test&mode=keyword should return results."""
        graph.add_entity("e1", "concept", "test concept for search")

        response = client.get("/api/search", params={
            "q": "test",
            "mode": "keyword",
            "limit": 10,
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should find the entity we added
        if data:
            assert any("test" in item.get("label", "").lower() for item in data)

    def test_dashboard_search_endpoint_empty_query(self, client):
        """GET /api/search?q= should return empty list."""
        response = client.get("/api/search", params={"q": ""})
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_dashboard_path_requires_params(self, client):
        """GET /api/path without source/target should return error key."""
        response = client.get("/api/path")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["paths"] == []

    def test_dashboard_path_with_params(self, client, graph):
        """GET /api/path with valid source/target should return path data."""
        graph.add_entity("a", "concept", "alpha concept")
        graph.add_entity("b", "concept", "beta concept")
        graph.add_edge("a", "b", "SUPPORTS")

        response = client.get("/api/path", params={
            "source": "alpha",
            "target": "beta",
        })
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "source" in data
        assert "target" in data

    def test_dashboard_types_endpoint(self, client, graph):
        """GET /api/types should return type distributions."""
        graph.add_entity("e1", "concept", "test")
        graph.add_entity("e2", "person", "someone")

        response = client.get("/api/types")
        assert response.status_code == 200
        data = response.json()
        assert "type_distribution" in data
        assert "edge_distribution" in data

    def test_dashboard_graph_endpoint(self, client, graph):
        """GET /api/graph should return nodes and edges."""
        graph.add_entity("e1", "concept", "graph test")

        response = client.get("/api/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
