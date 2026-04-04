---
name: ripser
description: Reference skill for Ripser persistent homology — computing topological features (H0 connected components, H1 holes/loops) from distance matrices, interpreting persistence diagrams, detecting coverage gaps, and integrating with NetworkX and knowledge graphs. Use when computing persistent homology, analyzing topological structure of graphs or point clouds, detecting coverage gaps in content strategy, or building topology health reports.
---

# Ripser Persistent Homology Reference

Compute persistent homology to detect topological features in data — connected components (H0), loops/holes (H1), and voids (H2). In our stack, Ripser answers: "where are the structural gaps?" in knowledge graphs, content coverage, and code architecture.

**Docs:** https://ripser.scikit-tda.org | **PyPI:** `pip install ripser`

---

## Graceful Import Pattern

Every project uses this — Ripser is always optional:

```python
try:
    from ripser import ripser as _ripser_fn
    _ripser_available = True
except ImportError:
    _ripser_available = False
    logger.info("ripser not installed, persistent homology disabled")

try:
    import numpy as np
    _numpy_available = True
except ImportError:
    _numpy_available = False

# Guard before use
if not _ripser_available or not _numpy_available:
    return {
        "ripser_available": False,
        "h1_computed": False,
        "h0_significant": [],
        "h1_significant": [],
        "h1_persistent": [],
    }
```

Both `ripser_available` and `h1_computed` keys must appear in topology reports.

---

## Core API

### ripser() Function

```python
from ripser import ripser

result = ripser(
    X,                      # Input data (point cloud or distance matrix)
    maxdim=1,               # Max homology dimension (0=components, 1=loops, 2=voids)
    thresh=np.inf,          # Max filtration value (cuts off computation)
    coeff=2,                # Coefficient field (2 = Z/2Z, default)
    distance_matrix=False,  # True if X is a precomputed distance matrix
    do_cocycles=False,      # Compute representative cocycles
    n_perm=None,            # Subsample size for greedy permutation (speed vs accuracy)
    metric="euclidean",     # Distance metric (if X is a point cloud)
)

# Returns dict:
# result["dgms"]    — list of persistence diagrams, one per dimension
# result["dperm2all"] — permutation-to-all distances (if n_perm set)
# result["idx_perm"]  — permutation indices (if n_perm set)
# result["r_cover"]   — covering radius (if n_perm set)
```

### Scikit-learn Interface

```python
from ripser import Rips

rips = Rips(maxdim=1, thresh=np.inf, coeff=2)
diagrams = rips.fit_transform(X)
rips.plot(diagrams)
```

---

## Persistence Diagrams

Each diagram is an `(n, 2)` NumPy array where each row is `[birth, death]`:

```python
dgms = result["dgms"]
h0 = dgms[0]  # Connected components: shape (n_components, 2)
h1 = dgms[1]  # Loops/holes: shape (n_loops, 2)

# Persistence = death - birth (how "significant" the feature is)
# High persistence = real topological feature
# Low persistence = noise

for birth, death in h1:
    persistence = death - birth
    if persistence > PERSISTENCE_HIGH:
        print(f"Significant hole: born={birth:.3f}, died={death:.3f}, persistence={persistence:.3f}")
```

### Interpreting Features

| Dimension | Name | What It Means | In Knowledge Graphs |
|-----------|------|---------------|-------------------|
| H0 | Connected components | Clusters that aren't linked | Disconnected entity clusters — missing RELATED edges |
| H1 | Loops / holes | Cycles in the topology | Coverage gaps — topics that should connect but don't |
| H2 | Voids | Enclosed cavities | Rare; indicates missing triangulation in dense regions |

### Infinite Death Values

H0 always has one feature with `death = inf` (the overall connected component). Filter it:

```python
# Filter out infinite features
h0_finite = h0[np.isfinite(h0[:, 1])]
h1_finite = h1[np.isfinite(h1[:, 1])] if len(h1) > 0 else h1
```

---

## Standard Persistence Thresholds

Consistent across all projects:

```python
PERSISTENCE_HIGH = 0.6    # Definitely a real feature — investigate
PERSISTENCE_MEDIUM = 0.3  # Probably real — worth noting
PERSISTENCE_LOW = 0.1     # Possibly noise — monitor
```

### Classifying Features

```python
def classify_features(dgms, dim=1):
    """Classify persistence features by significance."""
    if dim >= len(dgms) or len(dgms[dim]) == 0:
        return {"significant": [], "moderate": [], "noise": []}

    features = dgms[dim]
    finite = features[np.isfinite(features[:, 1])]

    significant = []
    moderate = []
    noise = []

    for birth, death in finite:
        persistence = death - birth
        feature = {"birth": float(birth), "death": float(death), "persistence": float(persistence)}
        if persistence >= PERSISTENCE_HIGH:
            significant.append(feature)
        elif persistence >= PERSISTENCE_MEDIUM:
            moderate.append(feature)
        elif persistence >= PERSISTENCE_LOW:
            noise.append(feature)

    return {"significant": significant, "moderate": moderate, "noise": noise}
```

---

## Distance Matrix Construction

### From Cosine Distance (Performance / Embedding Space)

Used by elephant-room, cpaws-strong-coast for content topology:

```python
from scipy.spatial.distance import cosine

def build_cosine_distance_matrix(vectors):
    """Build distance matrix from feature vectors using cosine distance."""
    n = len(vectors)
    dist_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = cosine(vectors[i], vectors[j])
            # Handle NaN from zero vectors
            if np.isnan(d):
                d = 1.0
            dist_matrix[i][j] = d
            dist_matrix[j][i] = d
    return dist_matrix
```

### From Shortest Path Lengths (Graph Topology)

Used by codetopo, vault-rag for structural analysis:

```python
import networkx as nx

def build_graph_distance_matrix(G):
    """Build distance matrix from shortest path lengths in a graph."""
    nodes = list(G.nodes())
    n = len(nodes)
    node_idx = {node: i for i, node in enumerate(nodes)}

    path_lengths = dict(nx.all_pairs_shortest_path_length(G))
    dist_matrix = np.full((n, n), float(n + 1))  # Unreachable default
    np.fill_diagonal(dist_matrix, 0.0)

    for u in nodes:
        for v, length in path_lengths.get(u, {}).items():
            i, j = node_idx[u], node_idx[v]
            dist_matrix[i][j] = length

    return dist_matrix, nodes
```

### From Edge Weights (Weighted Graph)

```python
def build_weighted_distance_matrix(G, weight_key="weight"):
    """Distance = inverse of edge weight (stronger connection = shorter distance)."""
    nodes = list(G.nodes())
    n = len(nodes)
    node_idx = {node: i for i, node in enumerate(nodes)}

    # Dijkstra with weight
    dist_matrix = np.full((n, n), np.inf)
    np.fill_diagonal(dist_matrix, 0.0)

    for source in nodes:
        lengths = nx.single_source_dijkstra_path_length(G, source, weight=weight_key)
        for target, length in lengths.items():
            dist_matrix[node_idx[source]][node_idx[target]] = length

    # Replace inf with max finite value + 1 (Ripser needs finite values or thresh)
    max_finite = dist_matrix[np.isfinite(dist_matrix)].max()
    dist_matrix[~np.isfinite(dist_matrix)] = max_finite + 1

    return dist_matrix, nodes
```

---

## Standard Topology Report Pattern

The full pipeline from graph → distance matrix → Ripser → report:

```python
def compute_persistence(dist_matrix, maxdim=1):
    """Run Ripser on a distance matrix and extract features."""
    if not _ripser_available:
        return {"ripser_available": False, "h1_computed": False}

    result = _ripser_fn(dist_matrix, maxdim=maxdim, distance_matrix=True)
    dgms = result["dgms"]

    h0 = classify_features(dgms, dim=0)
    h1 = classify_features(dgms, dim=1) if maxdim >= 1 else {"significant": [], "moderate": [], "noise": []}

    return {
        "ripser_available": True,
        "h1_computed": maxdim >= 1,
        "h0_significant": h0["significant"],
        "h0_count": len(dgms[0]),
        "h1_significant": h1["significant"],
        "h1_persistent": h1["significant"] + h1["moderate"],
        "h1_count": len(dgms[1]) if maxdim >= 1 else 0,
        "raw_dgms": dgms,  # For plotting
    }
```

### Full Topology Report (Graph → Report)

```python
def topology_report(conn):
    """Complete topology pipeline: DB → Graph → Metrics → Homology."""

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

    if G.number_of_nodes() < 3:
        return {"error": "Too few nodes for topology analysis", "nodes": G.number_of_nodes()}

    # 2. Graph metrics (NetworkX)
    report = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": nx.density(G),
        "components": nx.number_connected_components(G),
        "bridges": list(nx.bridges(G)),
        "isolates": list(nx.isolates(G)),
    }

    # 3. Work on largest connected component
    if not nx.is_connected(G):
        largest_cc = max(nx.connected_components(G), key=len)
        G_connected = G.subgraph(largest_cc).copy()
    else:
        G_connected = G

    # 4. Distance matrix
    dist_matrix, nodes = build_graph_distance_matrix(G_connected)

    # 5. Persistent homology
    homology = compute_persistence(dist_matrix, maxdim=1)
    report.update(homology)
    report["topology_nodes"] = nodes  # Which nodes were analyzed

    return report
```

---

## Content Coverage Gap Detection

Used by elephant-room and cpaws-strong-coast. H1 features in content performance space indicate topics that should exist but don't:

```python
def detect_coverage_gaps(performance_matrix, topic_names, maxdim=1):
    """
    performance_matrix: (n_topics, n_metrics) array of performance scores
    H1 features = coverage gaps in the content strategy
    """
    # Normalize
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    normalized = scaler.fit_transform(performance_matrix)

    # Impute NaN
    np.nan_to_num(normalized, copy=False, nan=0.0)

    # Cosine distance
    dist_matrix = build_cosine_distance_matrix(normalized)

    # Run Ripser
    result = _ripser_fn(dist_matrix, maxdim=maxdim, distance_matrix=True)
    dgms = result["dgms"]

    # H1 features = coverage gaps
    gaps = []
    if maxdim >= 1 and len(dgms[1]) > 0:
        for birth, death in dgms[1]:
            persistence = death - birth
            if persistence >= PERSISTENCE_MEDIUM:
                gaps.append({
                    "birth": float(birth),
                    "death": float(death),
                    "persistence": float(persistence),
                    "severity": "high" if persistence >= PERSISTENCE_HIGH else "medium",
                })

    return {
        "gaps": gaps,
        "gap_count": len(gaps),
        "h0_components": len(dgms[0]),
        "dist_matrix": dist_matrix,
    }
```

---

## Visualization with Persim

```python
from persim import plot_diagrams

# Basic persistence diagram
dgms = result["dgms"]
plot_diagrams(dgms, show=True)

# With customization
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

plot_diagrams(dgms, ax=axes[0], show=False)
axes[0].set_title("Persistence Diagram")

# Barcode plot (manual — persim doesn't have a built-in barcode)
ax = axes[1]
for i, (birth, death) in enumerate(dgms[1]):
    if np.isfinite(death):
        ax.barh(i, death - birth, left=birth, height=0.8, color="tab:orange")
ax.set_xlabel("Filtration Value")
ax.set_ylabel("Feature Index")
ax.set_title("H1 Barcode (Loops)")

plt.tight_layout()
plt.savefig("persistence.png", dpi=150)
```

### Bottleneck and Wasserstein Distance (Comparing Diagrams)

```python
from persim import bottleneck, wasserstein

# Compare two persistence diagrams (e.g., before/after graph changes)
d_bottleneck = bottleneck(dgms_before[1], dgms_after[1])
d_wasserstein = wasserstein(dgms_before[1], dgms_after[1])

print(f"Bottleneck distance: {d_bottleneck:.4f}")
print(f"Wasserstein distance: {d_wasserstein:.4f}")
```

---

## Severity Escalation Pattern

Used by cpaws-strong-coast across multiple topology passes:

```python
def escalate_severity(findings, pass_count):
    """Escalate severity based on how many passes have flagged the issue."""
    for finding in findings:
        if finding["persistence"] >= PERSISTENCE_HIGH:
            if pass_count >= 3:
                finding["severity"] = "critical"
            elif pass_count >= 2:
                finding["severity"] = "high"
            else:
                finding["severity"] = "medium"
        elif finding["persistence"] >= PERSISTENCE_MEDIUM:
            finding["severity"] = "low" if pass_count < 2 else "medium"
    return findings
```

---

## Performance Considerations

| Data Size | Approach |
|-----------|----------|
| < 500 nodes | Direct: `ripser(dist_matrix, distance_matrix=True)` |
| 500–2000 nodes | Subsample: `ripser(dist_matrix, distance_matrix=True, n_perm=500)` |
| 2000–5000 nodes | Threshold: `ripser(dist_matrix, distance_matrix=True, thresh=2.0)` |
| > 5000 nodes | Both: `ripser(dist_matrix, distance_matrix=True, n_perm=1000, thresh=2.0)` |

### Sparse Distance Matrices

For very large graphs, use sparse format:

```python
from scipy.sparse import csr_matrix

# Only compute distances for connected pairs
sparse_dist = csr_matrix((n, n))
for u, v, data in G.edges(data=True):
    i, j = node_idx[u], node_idx[v]
    d = 1.0 / (data.get("weight", 1.0) + 1e-8)
    sparse_dist[i, j] = d
    sparse_dist[j, i] = d

result = ripser(sparse_dist, maxdim=1, distance_matrix=True)
```

---

## Anti-Patterns

1. **Running Ripser without checking availability** — always use the graceful import pattern
2. **Forgetting `distance_matrix=True`** — without this flag, Ripser treats input as a point cloud and computes its own distances
3. **Using maxdim > 1 on large datasets** — H2 computation is O(n^3); rarely needed for graph analysis
4. **Not filtering infinite death values** — H0 always has one infinite feature; filter before analysis
5. **Raw persistence without thresholds** — always classify features using the standard thresholds
6. **Computing all-pairs shortest paths on disconnected graphs** — work on largest connected component
7. **Missing `ripser_available` and `h1_computed` in report** — required keys per convention
