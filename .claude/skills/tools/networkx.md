---
name: networkx
description: Reference skill for NetworkX graph analysis — centrality, community detection, shortest paths, bridge detection, graph construction, conversions, and integration with LadybugDB/RyuGraph. Use when writing graph analysis code, building topology pipelines, computing centrality metrics, detecting communities, or converting between graph formats.
---

# NetworkX Reference Guide

Reference for writing correct, idiomatic NetworkX code. NetworkX is the fallback for algorithms that LadybugDB/RyuGraph doesn't have natively — betweenness centrality, bridge detection, persistent homology prep, and any algorithm not in the `algo` extension.

**Rule of thumb:** Use LadybugDB's native algorithms (PageRank, WCC, SCC, Louvain, K-Core) when possible. Fall back to NetworkX for betweenness centrality, bridge detection, cycle analysis, and anything requiring the full 73-category algorithm library.

**Docs:** https://networkx.org/documentation/stable/

---

## Graceful Import Pattern

All projects use this — never assume NetworkX is available:

```python
try:
    import networkx as nx
    _networkx_available = True
except ImportError:
    _networkx_available = False
    logger.info("networkx not installed, graph analysis features disabled")

# Guard before use
if not _networkx_available:
    return {"bridges": [], "betweenness": {}, "nx_available": False}
```

---

## Graph Construction

### From Scratch

```python
G = nx.Graph()           # Undirected
G = nx.DiGraph()         # Directed
G = nx.MultiGraph()      # Undirected, parallel edges
G = nx.MultiDiGraph()    # Directed, parallel edges

# Add nodes with attributes
G.add_node("Docker", entity_type="infrastructure", weight=1.0)
G.add_nodes_from([
    ("FastAPI", {"entity_type": "tool"}),
    ("Redis", {"entity_type": "infrastructure"})
])

# Add edges with attributes
G.add_edge("FastAPI", "Redis", weight=0.8, rel_type="REQUIRES")
G.add_edges_from([
    ("Docker", "FastAPI", {"weight": 1.0, "rel_type": "SUPPORTS"}),
    ("Docker", "Redis", {"weight": 0.9, "rel_type": "SUPPORTS"})
])
```

### From LadybugDB / RyuGraph Query Results

```python
# Option A: get_as_networkx() (if available on your driver)
result = conn.execute("""
    MATCH (a:Entity)-[r:SUPPORTS|DERIVES_FROM|RELATED]->(b:Entity)
    RETURN a.name, b.name, type(r) AS edge_type, r.weight
""")
G = result.get_as_networkx()

# Option B: Manual construction (more control, always works)
result = conn.execute("""
    MATCH (a:Entity)-[r:SUPPORTS|DERIVES_FROM|RELATED]->(b:Entity)
    RETURN a.name, a.entity_type, b.name, b.entity_type, type(r) AS rel, r.weight
""")
G = nx.Graph()
for row in result.get_all():
    a_name, a_type, b_name, b_type, rel, weight = row
    G.add_node(a_name, entity_type=a_type)
    G.add_node(b_name, entity_type=b_type)
    G.add_edge(a_name, b_name, weight=weight or 1.0, rel_type=rel)
```

### From Edge Types with Filtering

```python
# Build graph from specific edge types only
EDGE_TYPES = ["RELATED", "SUPPORTS", "DERIVES_FROM", "IMPLEMENTS", "REQUIRES"]
result = conn.execute("""
    MATCH (a:Entity)-[r]->(b:Entity)
    WHERE type(r) IN $types
    RETURN a.name, a.entity_type, b.name, b.entity_type, type(r) AS rel, r.weight
""", parameters={"types": EDGE_TYPES})

G = nx.Graph()
for a_name, a_type, b_name, b_type, rel, weight in result.get_all():
    G.add_node(a_name, entity_type=a_type)
    G.add_node(b_name, entity_type=b_type)
    G.add_edge(a_name, b_name, weight=weight or 1.0, rel_type=rel)
```

---

## Centrality Algorithms

### Betweenness Centrality (Primary Use Case)

LadybugDB doesn't have this natively — always use NetworkX:

```python
# Node betweenness — identifies bridges/bottlenecks
betweenness = nx.betweenness_centrality(G, weight="weight", normalized=True)
top_bridges = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:20]

# Edge betweenness — identifies critical connections
edge_betweenness = nx.edge_betweenness_centrality(G, weight="weight")

# Approximate (faster for large graphs, k samples)
approx_betweenness = nx.betweenness_centrality(G, k=100, weight="weight")
```

### Other Centrality Measures

```python
# Degree centrality (simple, fast)
degree_cent = nx.degree_centrality(G)

# Closeness centrality
closeness = nx.closeness_centrality(G, distance="weight")

# Eigenvector centrality (like PageRank but undirected)
eigen = nx.eigenvector_centrality(G, max_iter=1000, weight="weight")

# PageRank (use LadybugDB's native version when possible)
pagerank = nx.pagerank(G, alpha=0.85, weight="weight")

# Harmonic centrality (handles disconnected graphs better than closeness)
harmonic = nx.harmonic_centrality(G, distance="weight")

# VoteRank (seed spreader identification)
spreaders = nx.voterank(G, number_of_nodes=10)
```

---

## Bridge Detection

Critical for knowledge graph health — identifies single points of failure:

```python
# Find bridges (edges whose removal disconnects the graph)
bridges = list(nx.bridges(G))

# For directed graphs, use edge connectivity
if G.is_directed():
    bridges = [(u, v) for u, v in G.edges()
               if not nx.has_path(G, u, v) or nx.minimum_edge_cut(G, u, v) == 1]

# Bridge detection with context
for u, v in nx.bridges(G):
    u_degree = G.degree(u)
    v_degree = G.degree(v)
    print(f"Bridge: {u} ({u_degree} connections) -- {v} ({v_degree} connections)")
```

---

## Community Detection

### Louvain (Primary — also available natively in LadybugDB)

```python
from networkx.algorithms.community import louvain_communities

communities = louvain_communities(G, seed=42, weight="weight", resolution=1.0)
for i, community in enumerate(communities):
    members = sorted(community)
    subgraph = G.subgraph(members)
    density = nx.density(subgraph)
    print(f"Community {i}: {len(members)} members, density={density:.3f}")
```

### Label Propagation (Fast, Non-deterministic)

```python
from networkx.algorithms.community import label_propagation_communities
communities = list(label_propagation_communities(G))
```

### Girvan-Newman (Hierarchical, Slow)

```python
from networkx.algorithms.community import girvan_newman
comp = girvan_newman(G)
first_level = next(comp)  # First split
```

### Modularity Score

```python
from networkx.algorithms.community import modularity
score = modularity(G, communities, weight="weight")
```

---

## Connected Components

```python
# Undirected
components = list(nx.connected_components(G))
largest = max(components, key=len)
num_components = nx.number_connected_components(G)

# Isolates (zero-degree nodes)
orphans = list(nx.isolates(G))

# Is connected?
if not nx.is_connected(G):
    # Work with largest component
    G_largest = G.subgraph(max(nx.connected_components(G), key=len)).copy()

# Directed: strongly/weakly connected
if G.is_directed():
    scc = list(nx.strongly_connected_components(G))
    wcc = list(nx.weakly_connected_components(G))
```

---

## Shortest Paths

```python
# Single pair
path = nx.shortest_path(G, source="Docker", target="Redis", weight="weight")
length = nx.shortest_path_length(G, source="Docker", target="Redis", weight="weight")

# All shortest paths between two nodes
all_paths = list(nx.all_shortest_paths(G, "Docker", "Redis", weight="weight"))

# From one source to all targets
paths = nx.single_source_shortest_path(G, "Docker", cutoff=3)
lengths = dict(nx.single_source_shortest_path_length(G, "Docker", cutoff=3))

# Check path existence first
if nx.has_path(G, source, target):
    path = nx.shortest_path(G, source, target)

# Dijkstra (explicit, weighted)
path, length = nx.single_source_dijkstra(G, "Docker", target="Redis", weight="weight")

# A* with heuristic
path = nx.astar_path(G, source, target, heuristic=my_heuristic, weight="weight")
```

---

## Cycles and Structure

```python
# Simple cycles (directed graphs)
cycles = list(nx.simple_cycles(G))

# Cycle basis (undirected)
basis = nx.cycle_basis(G)

# K-core decomposition
core_numbers = nx.core_number(G)
k3_core = nx.k_core(G, k=3)

# Triangles
triangle_count = nx.triangles(G)
clustering = nx.clustering(G)
avg_clustering = nx.average_clustering(G)

# Density
density = nx.density(G)
```

---

## Subgraph Operations

```python
# Subgraph view (no copy — changes reflect in original)
sub = G.subgraph(node_list)

# Independent copy
sub = G.subgraph(node_list).copy()

# Edge-induced subgraph
sub = G.edge_subgraph(edge_list)

# Ego graph (node + neighbors within radius)
ego = nx.ego_graph(G, "Docker", radius=2)

# Neighborhood
neighbors = list(G.neighbors("Docker"))
degree = G.degree("Docker")
```

---

## Conversions

### To/From NumPy (For Ripser Integration)

```python
# Adjacency matrix → NumPy array
adj_matrix = nx.to_numpy_array(G, weight="weight")

# Distance matrix (for Ripser)
path_lengths = dict(nx.all_pairs_shortest_path_length(G))
n = len(G)
nodes = list(G.nodes())
dist_matrix = np.full((n, n), float(n + 1))  # Default: unreachable
np.fill_diagonal(dist_matrix, 0.0)
for i, u in enumerate(nodes):
    for j, v in enumerate(nodes):
        if v in path_lengths[u]:
            dist_matrix[i][j] = path_lengths[u][v]

# NumPy array → Graph
G = nx.from_numpy_array(adj_matrix)
```

### To/From Pandas

```python
# Edge list → DataFrame
df = nx.to_pandas_edgelist(G)

# DataFrame → Graph
G = nx.from_pandas_edgelist(df, source="source", target="target",
                             edge_attr=["weight", "rel_type"])

# Adjacency → DataFrame
adj_df = nx.to_pandas_adjacency(G)
```

### To/From SciPy Sparse

```python
sparse = nx.to_scipy_sparse_array(G, weight="weight")
G = nx.from_scipy_sparse_array(sparse)
```

### To/From Dict

```python
# For serialization
d = nx.to_dict_of_dicts(G)
G = nx.from_dict_of_dicts(d)

# Edge list
edges = nx.to_edgelist(G)
G = nx.from_edgelist(edges)
```

---

## Distance Matrix Construction (For Ripser)

The standard pattern across all projects for preparing graph data for persistent homology:

```python
def build_distance_matrix(G, metric="shortest_path"):
    """Build distance matrix from NetworkX graph for Ripser input."""
    nodes = list(G.nodes())
    n = len(nodes)

    if metric == "shortest_path":
        path_lengths = dict(nx.all_pairs_shortest_path_length(G))
        dist_matrix = np.full((n, n), float(n + 1))
        np.fill_diagonal(dist_matrix, 0.0)
        for i, u in enumerate(nodes):
            for j, v in enumerate(nodes):
                if v in path_lengths.get(u, {}):
                    dist_matrix[i][j] = path_lengths[u][v]

    elif metric == "cosine":
        # From node feature vectors (e.g., embeddings)
        from scipy.spatial.distance import cosine
        features = np.array([G.nodes[n].get("embedding", []) for n in nodes])
        dist_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                d = cosine(features[i], features[j])
                dist_matrix[i][j] = d
                dist_matrix[j][i] = d

    return dist_matrix, nodes
```

---

## Graph Properties and Metrics

```python
# Basic stats
n_nodes = G.number_of_nodes()
n_edges = G.number_of_edges()
density = nx.density(G)
avg_degree = sum(dict(G.degree()).values()) / n_nodes

# Connectivity
is_connected = nx.is_connected(G)
n_components = nx.number_connected_components(G)

# Diameter (only on connected graphs)
if nx.is_connected(G):
    diameter = nx.diameter(G)
    radius = nx.radius(G)
    center = nx.center(G)

# Small-world metrics
avg_clustering = nx.average_clustering(G)
avg_path_length = nx.average_shortest_path_length(G) if nx.is_connected(G) else None
sigma = nx.sigma(G, niter=10, seed=42)  # Small-world coefficient (slow)
omega = nx.omega(G, niter=10, seed=42)  # Small-world omega (slow)

# Degree distribution
degree_seq = sorted([d for n, d in G.degree()], reverse=True)
```

---

## Topology Pipeline Pattern (Graph → Metrics → Ripser)

The standard flow across projects:

```python
def topology_report(conn):
    """Full topology analysis: graph metrics + persistent homology."""

    # 1. Build graph from database
    result = conn.execute("""
        MATCH (a:Entity)-[r]->(b:Entity)
        RETURN a.name, a.entity_type, b.name, b.entity_type, type(r), r.weight
    """)
    G = nx.Graph()
    for a, a_type, b, b_type, rel, weight in result.get_all():
        G.add_node(a, entity_type=a_type)
        G.add_node(b, entity_type=b_type)
        G.add_edge(a, b, weight=weight or 1.0, rel_type=rel)

    report = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": nx.density(G),
        "components": nx.number_connected_components(G),
        "isolates": len(list(nx.isolates(G))),
    }

    # 2. Centrality (betweenness — not in LadybugDB)
    betweenness = nx.betweenness_centrality(G, weight="weight")
    report["top_bridges"] = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]

    # 3. Bridge detection
    report["bridges"] = list(nx.bridges(G))

    # 4. Community detection
    from networkx.algorithms.community import louvain_communities
    communities = louvain_communities(G, seed=42)
    report["communities"] = len(communities)
    report["largest_community"] = max(len(c) for c in communities)

    # 5. Persistent homology (via Ripser — see ripser skill)
    # dist_matrix, nodes = build_distance_matrix(G)
    # report["homology"] = compute_persistence(dist_matrix)

    return report
```

---

## Anti-Patterns

1. **Using NetworkX for algorithms LadybugDB has natively** — PageRank, WCC, SCC, Louvain, K-Core are all in the `algo` extension
2. **Loading entire graph into NetworkX** — query only the subgraph you need
3. **Forgetting weight parameter** — most algorithms default to unweighted; pass `weight="weight"` explicitly
4. **Mutating subgraph views** — `G.subgraph(nodes)` returns a view, not a copy. Use `.copy()` if you need to modify
5. **Computing diameter on disconnected graphs** — check `nx.is_connected(G)` first
6. **Not seeding random algorithms** — Louvain, label propagation, etc. should use `seed=42` for reproducibility
