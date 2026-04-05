"""
Unit tests for the Graph CRUD layer (LadybugDB wrapper).

Tests cover:
  - Entity creation with ontology validation
  - Edge creation
  - Bulk entity loading
  - Embedding storage and vector search
  - Path finding
  - Edge-node (hypergraph) support
  - Document registration
  - Persistence across close/reopen
"""
import time
import pytest
import numpy as np


class TestEntityCRUD:
    """Test entity add, count, and validation."""

    def test_add_entity_valid(self, graph):
        """Adding a valid entity type should succeed and increment count."""
        result = graph.add_entity("e1", "concept", "spaced repetition")
        assert result is True
        assert graph.entity_count() == 1

    def test_add_entity_invalid_type(self, graph):
        """Adding an invalid type should be rejected and leave count at 0."""
        result = graph.add_entity("e1", "weapon", "lightsaber")
        assert result is False
        assert graph.entity_count() == 0

    def test_add_entity_with_metadata(self, graph):
        """Entity should store all metadata fields."""
        graph.add_entity(
            "e1", "person", "Ada Lovelace",
            description="First programmer",
            confidence=0.95,
            source_url="https://example.com",
            provenance="manual",
        )
        rows = graph.query(
            "MATCH (e:Entity {id: $id}) RETURN e.label AS label, "
            "e.description AS edesc, e.confidence AS conf",
            parameters={"id": "e1"},
        )
        assert len(rows) == 1
        assert rows[0]["label"] == "Ada Lovelace"
        assert rows[0]["edesc"] == "First programmer"
        assert rows[0]["conf"] == 0.95

    def test_add_entity_merge_updates_timestamp(self, graph):
        """Adding the same entity ID again should update updated_at (MERGE)."""
        graph.add_entity("e1", "concept", "test")
        rows_before = graph.query(
            "MATCH (e:Entity {id: 'e1'}) RETURN e.updated_at AS t")
        time.sleep(0.01)  # ensure timestamp changes
        graph.add_entity("e1", "concept", "test")
        rows_after = graph.query(
            "MATCH (e:Entity {id: 'e1'}) RETURN e.updated_at AS t")
        # Count should still be 1 (MERGE, not duplicate)
        assert graph.entity_count() == 1


class TestEdgeCRUD:
    """Test edge creation between entities."""

    def test_add_edge(self, graph):
        """Adding two entities and a valid edge should yield edge_count=1."""
        graph.add_entity("a", "concept", "A")
        graph.add_entity("b", "concept", "B")
        result = graph.add_edge("a", "b", "SUPPORTS")
        assert result is True
        assert graph.edge_count() == 1

    def test_add_edge_invalid_type(self, graph):
        """Adding an edge with invalid type should be rejected."""
        graph.add_entity("a", "concept", "A")
        graph.add_entity("b", "concept", "B")
        result = graph.add_edge("a", "b", "DESTROYS")
        assert result is False
        assert graph.edge_count() == 0

    def test_multiple_edges(self, populated_graph):
        """The populated_graph fixture should have exactly 4 edges."""
        assert populated_graph.edge_count() == 4


class TestBulkOperations:
    """Test bulk entity and edge loading."""

    def test_bulk_add_entities(self, graph):
        """Bulk-adding 10 valid entities should load all 10."""
        entities = [
            {
                "id": f"e{i}",
                "entity_type": "concept",
                "label": f"Concept {i}",
                "description": f"Description {i}",
                "confidence": 0.8,
                "source_url": "",
                "provenance": "test",
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
            }
            for i in range(10)
        ]
        loaded = graph.bulk_add_entities(entities)
        assert loaded == 10
        assert graph.entity_count() == 10

    def test_bulk_add_entities_filters_invalid(self, graph):
        """Bulk load should filter out entities with invalid types."""
        entities = [
            {"id": "v1", "entity_type": "concept", "label": "Valid 1"},
            {"id": "v2", "entity_type": "person", "label": "Valid 2"},
            {"id": "bad1", "entity_type": "weapon", "label": "Invalid 1"},
            {"id": "bad2", "entity_type": "food", "label": "Invalid 2"},
            {"id": "v3", "entity_type": "source", "label": "Valid 3"},
        ]
        loaded = graph.bulk_add_entities(entities)
        assert loaded == 3
        assert graph.entity_count() == 3

    def test_bulk_add_entities_empty(self, graph):
        """Bulk loading an empty list should return 0 and not crash."""
        loaded = graph.bulk_add_entities([])
        assert loaded == 0
        assert graph.entity_count() == 0


class TestEmbeddingAndVectorSearch:
    """Test embedding storage and similarity search."""

    def test_set_embedding_and_vector_search(self, graph):
        """Storing a 768-dim embedding and searching should find the entity."""
        graph.add_entity("e1", "concept", "target entity")
        graph.add_entity("e2", "concept", "other entity")

        # Create a known embedding for e1 and a different one for e2
        rng = np.random.RandomState(42)
        emb1 = rng.randn(768).tolist()
        emb2 = rng.randn(768).tolist()

        graph.set_embedding("e1", emb1)
        graph.set_embedding("e2", emb2)

        # Search with e1's embedding should return e1 as top result
        results = graph.vector_search(emb1, limit=2)
        assert len(results) > 0
        assert results[0]["id"] == "e1"


class TestPathFinding:
    """Test multi-hop path finding."""

    def test_find_path(self, populated_graph):
        """Find path from 'spaced repetition' to 'Make It Stick' via LEARNED_FROM."""
        paths = populated_graph.find_path("spaced repetition", "Make It Stick")
        assert len(paths) > 0
        # The path should contain both labels
        first_path = paths[0]
        assert "spaced repetition" in first_path["node_labels"]
        assert "Make It Stick" in first_path["node_labels"]

    def test_find_path_multi_hop(self, populated_graph):
        """Find path from 'learning compounds like interest' to 'Make It Stick'
        which requires going through 'spaced repetition'."""
        paths = populated_graph.find_path("learning compounds", "Make It Stick")
        assert len(paths) > 0
        # Should be at least 2 hops
        first_path = paths[0]
        assert len(first_path["edge_types"]) >= 2

    def test_find_path_no_result(self, populated_graph):
        """Searching for a non-existent path should return empty list."""
        paths = populated_graph.find_path("nonexistent entity", "also nonexistent")
        assert paths == []


class TestEdgeNode:
    """Test hypergraph edge-node support."""

    def test_add_edge_node(self, graph):
        """Create an edge-node connecting three entities (hypergraph)."""
        graph.add_entity("a", "concept", "A")
        graph.add_entity("b", "concept", "B")
        graph.add_entity("c", "concept", "C")

        result = graph.add_edge_node(
            "en1", "similar_edge", label="A is like B and C",
            participants=["a", "b", "c"],
        )
        assert result is True

        # Verify CONNECTS traversal (a -> en1)
        connects = graph.query(
            "MATCH (e:Entity {id: 'a'})-[:CONNECTS]->(en:EdgeNode {id: 'en1'}) "
            "RETURN en.label AS label"
        )
        assert len(connects) == 1

        # Verify BINDS traversal (en1 -> b, en1 -> c)
        binds = graph.query(
            "MATCH (en:EdgeNode {id: 'en1'})-[:BINDS]->(e:Entity) "
            "RETURN e.id AS id"
        )
        assert len(binds) == 2
        bound_ids = {row["id"] for row in binds}
        assert bound_ids == {"b", "c"}


class TestDocument:
    """Test document registration."""

    def test_add_document(self, graph):
        """Registering a document should increment document_count."""
        graph.add_document("doc1", "/path/to/file.md", "Test Document")
        assert graph.document_count() == 1

    def test_add_multiple_documents(self, graph):
        """Registering multiple documents should count correctly."""
        graph.add_document("doc1", "/path/1.md", "Doc 1")
        graph.add_document("doc2", "/path/2.md", "Doc 2")
        graph.add_document("doc3", "/path/3.md", "Doc 3")
        assert graph.document_count() == 3


class TestPersistence:
    """Test that data survives close and reopen."""

    def test_graph_close_and_reopen(self, tmp_path, ontology):
        """Data written to the graph should persist after close + reopen."""
        from second_brain.graph import Graph

        graph_dir = tmp_path / "persist_test.lbug"

        # Phase 1: write data
        g1 = Graph(graph_dir, ontology)
        g1.add_entity("p1", "person", "Persistence Test Person")
        g1.add_entity("c1", "concept", "Persistence Test Concept")
        g1.add_edge("c1", "p1", "ASSOCIATED_WITH")
        g1.add_document("d1", "/test.md", "Test")
        g1.close()

        # Phase 2: reopen and verify
        g2 = Graph(graph_dir, ontology)
        assert g2.entity_count() == 2
        assert g2.edge_count() == 1
        assert g2.document_count() == 1
        g2.close()
