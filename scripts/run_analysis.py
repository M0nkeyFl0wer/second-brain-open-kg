#!/usr/bin/env python3
"""
Run topology analysis on the personal knowledge graph and output a report.

Analyzes the structure of your captured ideas: how they cluster, where gaps
exist between idea groups, which concepts bridge different areas of thinking,
and where beliefs conflict.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, ".")

from second_brain.graph import Graph
from second_brain.topology import run_topology, run_persistent_homology, build_networkx_graph


def main():
    graph = Graph()

    entities = graph.entity_count()
    edges = graph.edge_count()

    if entities == 0:
        print("Graph is empty. Ingest some documents first.")
        return

    print(f"Running topology analysis on {entities} entities, {edges} edges...\n")

    report = run_topology(graph)

    # Print summary
    print("=" * 60)
    print("KNOWLEDGE GRAPH ANALYSIS")
    print("=" * 60)
    print(f"  Entities:              {report.node_count}")
    print(f"  Edges:                 {report.edge_count}")
    print(f"  Connected components:  {report.component_count}")
    print(f"  Largest component:     {report.largest_component_size} nodes")
    print(f"  Isolated nodes:        {report.isolated_count}")
    print(f"  Communities (Louvain): {report.community_count}")
    print()

    # Knowledge gaps — community pairs with sparse cross-connections
    if report.gaps:
        print(f"KNOWLEDGE GAPS: {len(report.gaps)}")
        print("-" * 60)
        for gap in report.gaps[:10]:
            ca = gap["community_a"]
            cb = gap["community_b"]
            print(f"  [{gap['priority']}] {ca['top_entities'][0]} ↔ {cb['top_entities'][0]}")
            print(f"         {ca['size']} entities ↔ {cb['size']} entities | "
                  f"cross-edges: {gap['cross_edges']}")
            print(f"         → {gap['question']}")
            print()

    # Surprising bridges — high betweenness on low-degree entities
    surprising = [b for b in report.top_betweenness if b.get("surprising")]
    if surprising:
        print(f"SURPRISING BRIDGES: {len(surprising)}")
        print("-" * 60)
        for s in surprising[:10]:
            print(f"  {s['label']} ({s['type']})")
            print(f"    Betweenness: {s['betweenness']} | Degree: {s['degree']}")
            print(f"    → Bridges different areas of your thinking")
            print()

    # Contradictions
    if report.contradictions:
        print(f"CONTRADICTIONS: {len(report.contradictions)}")
        print("-" * 60)
        for c in report.contradictions[:5]:
            print(f"  \"{c['claim_a']}\"")
            print(f"  contradicts")
            print(f"  \"{c['claim_b']}\"")
            print()

    # Bridges — structurally fragile single-point connections
    if report.bridges:
        print(f"BRIDGES (fragile connections): {len(report.bridges)}")
        print("-" * 60)
        for b in report.bridges[:10]:
            print(f"  {b['source_label']} ↔ {b['target_label']}")
        print()

    # Persistent homology (optional topological features)
    print("PERSISTENT HOMOLOGY")
    print("-" * 60)
    G = build_networkx_graph(graph)
    homology = run_persistent_homology(G)
    if homology.get("available"):
        print(f"  H0 features (components): {homology['h0_features']}")
        print(f"  H1 features (holes):      {homology['h1_features']}")
        print(f"  H1 persistent (signal):   {homology['h1_persistent']}")
        if homology.get("h1_details"):
            print()
            print("  Top persistent H1 features (reasoning gaps):")
            for h in homology["h1_details"][:5]:
                print(f"    birth: {h['birth']}, death: {h['death']}, "
                      f"persistence: {h['persistence']}")
    else:
        print(f"  {homology.get('reason', 'Not available')}")

    # Save JSON report
    report_path = Path(f"analysis-report-{datetime.now().strftime('%Y-%m-%d')}.json")
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "entities": report.node_count,
        "edges": report.edge_count,
        "components": report.component_count,
        "largest_component": report.largest_component_size,
        "isolated": report.isolated_count,
        "communities": report.community_count,
        "gaps": report.gaps[:20],
        "surprising_bridges": surprising[:10],
        "contradictions": report.contradictions[:10],
        "bridges": len(report.bridges),
        "homology": homology,
    }
    report_path.write_text(json.dumps(report_data, indent=2))
    print(f"\nFull report saved to {report_path}")


if __name__ == "__main__":
    main()
