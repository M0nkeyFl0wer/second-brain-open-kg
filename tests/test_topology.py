"""
Unit tests for graph topology analysis.

Tests cover:
  - Empty graph handling (no crash)
  - Community detection on populated graph
  - Gap detection between disconnected clusters
  - Betweenness centrality on bridge nodes
  - Skeleton extraction for visualization
"""
import pytest
import networkx as nx


class TestRunTopology:
    """Test the main run_topology function against LadybugDB graphs."""

    def test_run_topology_empty_graph(self, graph):
        """Topology analysis on an empty graph should return a zeroed report."""
        from second_brain.topology import run_topology
        report = run_topology(graph)
        assert report.node_count == 0
        assert report.edge_count == 0
        assert report.community_count == 0
        assert report.gaps == []
        assert report.bridges == []
        assert report.top_betweenness == []

    def test_run_topology_with_data(self, populated_graph):
        """Topology on a populated graph should detect nodes and edges."""
        from second_brain.topology import run_topology
        report = run_topology(populated_graph)
        assert report.node_count == 6  # 6 entities in populated_graph
        assert report.edge_count == 4  # 4 RELATES_TO edges
        # Should detect at least 1 community (could be 1 if all connected)
        assert report.community_count >= 1


class TestBuildNetworkXGraph:
    """Test conversion from LadybugDB to NetworkX."""

    def test_build_networkx_graph(self, populated_graph):
        """NetworkX graph should mirror the LadybugDB entity/edge counts."""
        from second_brain.topology import build_networkx_graph
        G = build_networkx_graph(populated_graph)
        assert G.number_of_nodes() == 6
        assert G.number_of_edges() == 4


class TestCommunityGaps:
    """Test gap detection between disconnected knowledge clusters."""

    def test_find_community_gaps(self, graph):
        """Two disconnected clusters with MIN_COMMUNITY_SIZE nodes each
        should be flagged as a gap."""
        # Cluster A: 3 interconnected concepts
        graph.add_entity("a1", "concept", "Cluster A Node 1")
        graph.add_entity("a2", "concept", "Cluster A Node 2")
        graph.add_entity("a3", "concept", "Cluster A Node 3")
        graph.add_edge("a1", "a2", "SUPPORTS")
        graph.add_edge("a2", "a3", "SUPPORTS")
        graph.add_edge("a1", "a3", "SUPPORTS")

        # Cluster B: 3 interconnected concepts (disconnected from A)
        graph.add_entity("b1", "concept", "Cluster B Node 1")
        graph.add_entity("b2", "concept", "Cluster B Node 2")
        graph.add_entity("b3", "concept", "Cluster B Node 3")
        graph.add_edge("b1", "b2", "SUPPORTS")
        graph.add_edge("b2", "b3", "SUPPORTS")
        graph.add_edge("b1", "b3", "SUPPORTS")

        from second_brain.topology import run_topology
        report = run_topology(graph)
        # Should detect 2 components
        assert report.component_count >= 2
        # With MIN_COMMUNITY_SIZE=3, both clusters qualify and their
        # disconnection should be flagged as a gap
        if report.community_count >= 2:
            assert len(report.gaps) >= 1
            # Gap should be HIGH priority (0 cross-edges)
            assert report.gaps[0]["priority"] == "HIGH"


class TestBetweenness:
    """Test betweenness centrality calculations on synthetic graphs."""

    def test_betweenness_on_bridge(self):
        """In A-B-C chain, B should have the highest betweenness centrality."""
        G = nx.Graph()
        # Create a simple chain: A - B - C
        # Add more nodes to make betweenness meaningful (>10 nodes needed
        # for the run_topology code path, but we test on raw NetworkX here)
        G.add_edge("A", "B")
        G.add_edge("B", "C")

        bc = nx.betweenness_centrality(G)
        # B is the only bridge, should have highest betweenness
        assert bc["B"] > bc["A"]
        assert bc["B"] > bc["C"]

    def test_betweenness_star_topology(self):
        """In a star graph, the center should have highest betweenness."""
        G = nx.star_graph(5)  # Node 0 at center, 1-5 on edges
        bc = nx.betweenness_centrality(G)
        center_bc = bc[0]
        for node in range(1, 6):
            assert center_bc >= bc[node]


class TestSkeletonExtraction:
    """Test edge reduction for visualization."""

    def test_extract_skeleton_reduces_edges(self):
        """A dense graph should have fewer edges after skeleton extraction."""
        from second_brain.topology import extract_skeleton

        # Create a dense graph (complete graph with 20 nodes = 190 edges)
        G = nx.complete_graph(20)
        # Add node attributes like the real graph would
        for node in G.nodes():
            G.nodes[node]["label"] = f"Node {node}"
            G.nodes[node]["type"] = "concept"

        max_edges = 50
        S = extract_skeleton(G, max_edges=max_edges)
        assert S.number_of_edges() <= max_edges
        assert S.number_of_edges() < G.number_of_edges()
        # All original nodes should still be present
        assert S.number_of_nodes() == G.number_of_nodes()

    def test_extract_skeleton_small_graph_unchanged(self):
        """A graph with fewer edges than max_edges should be returned as-is."""
        from second_brain.topology import extract_skeleton

        G = nx.path_graph(5)  # 4 edges
        S = extract_skeleton(G, max_edges=200)
        assert S.number_of_edges() == G.number_of_edges()
        assert S.number_of_nodes() == G.number_of_nodes()

    def test_extract_skeleton_preserves_data(self):
        """Edge attributes should be preserved in the skeleton."""
        from second_brain.topology import extract_skeleton

        G = nx.complete_graph(10)
        for u, v in G.edges():
            G.edges[u, v]["type"] = "SUPPORTS"
            G.edges[u, v]["weight"] = 1.5

        S = extract_skeleton(G, max_edges=15)
        for u, v, data in S.edges(data=True):
            assert data["type"] == "SUPPORTS"
            assert data["weight"] == 1.5
