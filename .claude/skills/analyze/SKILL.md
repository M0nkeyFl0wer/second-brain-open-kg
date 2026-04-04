# /analyze — Knowledge Graph Topology Analysis

Run structural analysis on the knowledge graph: connected components, Louvain communities, betweenness centrality, bridge detection, gap detection, and persistent homology.

## When to use

- User asks "analyze my graph", "what's the structure", "find gaps"
- User wants to see knowledge gaps (community pairs with low cross-edges)
- User asks about surprising connections or bridges in their thinking
- After significant ingestion to understand new graph structure

## Usage

```bash
python scripts/run_analysis.py
```

## Output

```
KNOWLEDGE GRAPH ANALYSIS
============================================================
  Entities:              1,847
  Edges:                 423
  Connected components:  89
  Largest component:     312 nodes
  Communities (Louvain): 23

KNOWLEDGE GAPS: 5
  [HIGH] "cognitive science" ↔ "productivity" (0 cross-edges)
  → How do your ideas about these topics relate?

SURPRISING BRIDGES: 3
  "sleep architecture" (concept) — Betweenness: 0.312
  → Bridges different areas of your thinking

BRIDGES (fragile connections): 16
PERSISTENT HOMOLOGY (if Ripser installed)
```

Also saves a JSON report: `analysis-report-YYYY-MM-DD.json`

## Algorithms Used

| Algorithm | What it finds | Engine |
|-----------|--------------|--------|
| Connected components | Isolated clusters | NetworkX |
| Louvain communities | Dense subgroups | NetworkX (native algo fallback) |
| Betweenness centrality | Structural bridges | NetworkX |
| Bridge detection | Single-point-of-failure edges | NetworkX |
| Gap detection | Community pairs with low cross-edges | Custom |
| Persistent homology | Topological holes | Ripser (optional) |

## Notes

- No AI involved — purely deterministic graph math
- Gaps are the signal: two large communities with zero cross-edges = missing knowledge
- Surprising bridges: high betweenness on low-degree entities = quiet connectors
