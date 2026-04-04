"""
Graph topology analysis. Finds structural gaps, contradictions,
surprising connections, and community structure.
No AI needed — just math on the graph structure.
"""
import networkx as nx
from dataclasses import dataclass, field


@dataclass
class TopologyReport:
    """Results of a topology analysis pass."""
    node_count: int = 0
    edge_count: int = 0
    component_count: int = 0
    largest_component_size: int = 0
    isolated_count: int = 0
    communities: dict = field(default_factory=dict)  # node_id → community_id
    community_count: int = 0
    gaps: list = field(default_factory=list)
    bridges: list = field(default_factory=list)
    top_betweenness: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)


def build_networkx_graph(graph) -> nx.Graph:
    """Convert LadybugDB graph to NetworkX for analysis."""
    from .queries import QUERIES
    G = nx.Graph()

    entities = graph.query(QUERIES["all_entities_for_topology"])
    for e in entities:
        G.add_node(e["id"], **e)

    edges = graph.query(QUERIES["all_edges_for_topology"])
    for e in edges:
        G.add_edge(e["src"], e["tgt"], **e)

    return G


def run_topology(graph) -> TopologyReport:
    """Run full topology analysis. Returns structured report."""
    G = build_networkx_graph(graph)
    report = TopologyReport()

    if len(G) == 0:
        return report

    report.node_count = G.number_of_nodes()
    report.edge_count = G.number_of_edges()

    # Connected components
    components = list(nx.connected_components(G))
    report.component_count = len(components)
    report.largest_component_size = max(len(c) for c in components) if components else 0
    report.isolated_count = sum(1 for c in components if len(c) == 1)

    # Community detection (Louvain)
    try:
        from networkx.algorithms.community import louvain_communities
        communities_list = louvain_communities(G, seed=42)
        for i, comm in enumerate(communities_list):
            for node in comm:
                report.communities[node] = i
        report.community_count = len(communities_list)
    except ImportError:
        pass  # NetworkX version doesn't have Louvain

    # Betweenness centrality (on largest component only, sampled for speed)
    if report.largest_component_size > 10:
        largest = max(components, key=len)
        subG = G.subgraph(largest)

        # Sample if graph is large
        k = min(500, len(subG))
        bc = nx.betweenness_centrality(subG, k=k, seed=42)

        # Find high betweenness on low-degree nodes (surprising connectors)
        for node_id, score in sorted(bc.items(), key=lambda x: -x[1])[:20]:
            degree = G.degree(node_id)
            node_data = G.nodes[node_id]
            report.top_betweenness.append({
                "id": node_id,
                "label": node_data.get("label", ""),
                "type": node_data.get("type", ""),
                "betweenness": round(score, 4),
                "degree": degree,
                "surprising": score > 0.05 and degree < 10,
            })

    # Gap detection: community pairs with low cross-edges
    if report.community_count > 1:
        report.gaps = _find_community_gaps(G, report.communities, report.community_count)

    # Contradiction detection
    report.contradictions = _find_contradictions(graph)

    # Bridge detection (on manageable-size graph)
    if report.node_count < 10000:
        try:
            report.bridges = [
                {"source": u, "target": v,
                 "source_label": G.nodes[u].get("label", ""),
                 "target_label": G.nodes[v].get("label", "")}
                for u, v in nx.bridges(G)
            ]
        except nx.NetworkXError:
            pass  # Graph has issues preventing bridge detection

    return report


def _find_community_gaps(G: nx.Graph, communities: dict, num_communities: int) -> list:
    """Find community pairs that should plausibly connect but don't."""
    from . import config

    # Build community sizes
    comm_sizes = {}
    for node, comm_id in communities.items():
        comm_sizes[comm_id] = comm_sizes.get(comm_id, 0) + 1

    # Count cross-community edges
    cross_edges = {}
    for u, v in G.edges():
        cu = communities.get(u)
        cv = communities.get(v)
        if cu is not None and cv is not None and cu != cv:
            pair = (min(cu, cv), max(cu, cv))
            cross_edges[pair] = cross_edges.get(pair, 0) + 1

    # Find gaps: large communities with few cross-edges
    gaps = []
    substantial = [c for c, size in comm_sizes.items()
                   if size >= config.MIN_COMMUNITY_SIZE]

    for i, c1 in enumerate(substantial):
        for c2 in substantial[i + 1:]:
            pair = (min(c1, c2), max(c1, c2))
            count = cross_edges.get(pair, 0)

            if count <= config.MAX_CROSS_EDGES_FOR_GAP:
                # Get representative entities for each community
                c1_nodes = [n for n, c in communities.items() if c == c1]
                c2_nodes = [n for n, c in communities.items() if c == c2]

                # Top by degree within community
                c1_top = sorted(c1_nodes, key=lambda n: G.degree(n), reverse=True)[:3]
                c2_top = sorted(c2_nodes, key=lambda n: G.degree(n), reverse=True)[:3]

                c1_labels = [G.nodes[n].get("label", n) for n in c1_top]
                c2_labels = [G.nodes[n].get("label", n) for n in c2_top]

                gaps.append({
                    "community_a": {"id": c1, "size": comm_sizes[c1], "top_entities": c1_labels},
                    "community_b": {"id": c2, "size": comm_sizes[c2], "top_entities": c2_labels},
                    "cross_edges": count,
                    "priority": "HIGH" if count == 0 else "MEDIUM",
                    "question": (
                        f"How do {c1_labels[0]} and {c2_labels[0]} relate? "
                        f"Your knowledge about [{', '.join(c1_labels)}] and "
                        f"[{', '.join(c2_labels)}] is not yet connected."
                    ),
                })

    return sorted(gaps, key=lambda g: (g["priority"] == "HIGH", -g["cross_edges"]), reverse=True)


def _find_contradictions(graph) -> list:
    """Find CONTRADICTS edges in the graph."""
    from .queries import QUERIES
    return graph.query(QUERIES["contradictions"],
                       parameters={"limit": 20})


def run_persistent_homology(G: nx.Graph, max_nodes: int = 500) -> dict:
    """
    Run persistent homology on the graph to find topological features.
    Requires ripser: pip install ripser
    Returns birth/death pairs for H0 and H1 features.
    """
    try:
        import numpy as np
        from ripser import ripser
        from scipy.sparse.csgraph import shortest_path
    except ImportError:
        return {"available": False, "reason": "ripser not installed (pip install ripser)"}

    if len(G) == 0:
        return {"available": True, "h0_features": 0, "h1_features": 0}

    # Sample if too large
    if len(G) > max_nodes:
        nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:max_nodes]
        G = G.subgraph(nodes)

    # Build distance matrix (shortest path lengths)
    adj = nx.adjacency_matrix(G).toarray().astype(float)
    adj[adj == 0] = np.inf
    np.fill_diagonal(adj, 0)
    dist = shortest_path(adj, directed=False)
    dist[dist == np.inf] = dist[dist != np.inf].max() + 1  # cap infinite distances

    # Run Ripser
    result = ripser(dist, maxdim=1, distance_matrix=True)
    diagrams = result["dgms"]

    h0 = diagrams[0] if len(diagrams) > 0 else []
    h1 = diagrams[1] if len(diagrams) > 1 else []

    # Filter to persistent features (long-lived)
    h1_persistent = [(b, d) for b, d in h1 if d - b > 0.5]

    return {
        "available": True,
        "h0_features": len(h0),
        "h1_features": len(h1),
        "h1_persistent": len(h1_persistent),
        "h1_details": [
            {"birth": round(float(b), 3), "death": round(float(d), 3),
             "persistence": round(float(d - b), 3)}
            for b, d in sorted(h1_persistent, key=lambda x: -(x[1] - x[0]))[:10]
        ],
    }


def extract_skeleton(G: nx.Graph, max_edges: int = 200) -> nx.Graph:
    """
    Reduce a dense graph to a readable skeleton for visualization.
    Removes edges in order of decreasing betweenness until max_edges remain,
    preserving the structural backbone while eliminating visual "hairball" noise.

    The skeleton retains:
    - All nodes (no entities are hidden)
    - High-betweenness edges (structural bridges)
    - Community-internal edges with highest weight
    """
    if G.number_of_edges() <= max_edges:
        return G.copy()

    # Compute edge betweenness
    edge_bc = nx.edge_betweenness_centrality(G)

    # Sort edges: keep highest betweenness (structural bridges) first
    edges_ranked = sorted(edge_bc.items(), key=lambda x: -x[1])

    # Build skeleton: take top edges by betweenness
    skeleton = nx.Graph()
    skeleton.add_nodes_from(G.nodes(data=True))

    for (u, v), _ in edges_ranked[:max_edges]:
        skeleton.add_edge(u, v, **G.edges[u, v])

    return skeleton


def export_skeleton_json(graph, max_edges: int = 200) -> dict:
    """
    Export a visualization-ready skeleton of the graph as JSON.
    Returns {nodes: [...], edges: [...]} suitable for D3, vis-network, etc.
    """
    G = build_networkx_graph(graph)
    S = extract_skeleton(G, max_edges=max_edges)

    nodes = []
    for node_id, data in S.nodes(data=True):
        nodes.append({
            "id": node_id,
            "label": data.get("label", node_id),
            "type": data.get("type", ""),
            "degree": S.degree(node_id),
        })

    edges = []
    for u, v, data in S.edges(data=True):
        edges.append({
            "source": u,
            "target": v,
            "type": data.get("type", ""),
            "weight": data.get("weight", 1.0),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "original_edges": G.number_of_edges(),
        "skeleton_edges": S.number_of_edges(),
        "reduction": round(1 - S.number_of_edges() / max(G.number_of_edges(), 1), 2),
    }
