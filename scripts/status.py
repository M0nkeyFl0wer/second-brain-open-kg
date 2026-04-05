#!/usr/bin/env python3
"""
Knowledge graph health status — quick terminal dashboard.
Shows entity/edge counts, ontology health (ICR/CI/IPR), community count,
hidden connections count, type distribution, and last ingestion time.

Usage: python scripts/status.py
"""
import sys
import time
from datetime import datetime

sys.path.insert(0, ".")

from second_brain.graph import Graph
from second_brain.ontology import Ontology


def format_bar(value: float, width: int = 20) -> str:
    """Render a progress bar: ████████░░░░"""
    filled = int(value * width)
    return "█" * filled + "░" * (width - filled)


def health_color(value: float, thresholds: tuple = (0.8, 0.5)) -> str:
    """Return health label based on thresholds."""
    good, warn = thresholds
    if value >= good:
        return "healthy"
    elif value >= warn:
        return "warning"
    return "CRITICAL"


def main():
    ontology = Ontology()
    graph = Graph(ontology=ontology)
    try:
        entities = graph.entity_count()
        edges = graph.edge_count()
        docs = graph.document_count()

        # Edge-node and community counts
        edge_nodes = 0
        communities = 0
        try:
            r = graph.query("MATCH (en:EdgeNode) RETURN count(en) AS cnt")
            edge_nodes = r[0]["cnt"] if r else 0
        except Exception:
            pass
        try:
            r = graph.query("MATCH (c:CommunityMeta) RETURN count(c) AS cnt")
            communities = r[0]["cnt"] if r else 0
        except Exception:
            pass

        # Last ingestion time
        last_ingested = None
        try:
            r = graph.query(
                "MATCH (d:Document) RETURN d.ingested_at AS t ORDER BY t DESC LIMIT 1")
            if r and r[0]["t"]:
                last_ingested = datetime.fromtimestamp(r[0]["t"])
        except Exception:
            pass

        # Type distribution
        type_dist = graph.query(
            "MATCH (e:Entity) RETURN e.entity_type AS type, count(e) AS cnt ORDER BY cnt DESC")

        # Edge type distribution
        edge_dist = graph.query(
            "MATCH ()-[r:RELATES_TO]->() RETURN r.edge_type AS type, count(r) AS cnt ORDER BY cnt DESC")

        # Ontology health metrics
        declared_types = set(ontology.entity_type_names)
        declared_edges = set(ontology.edge_type_names)
        populated_types = set(r["type"] for r in type_dist) if type_dist else set()
        populated_edges = set(r["type"] for r in edge_dist) if edge_dist else set()

        icr = len(populated_types & declared_types) / len(declared_types) if declared_types else 0
        ipr = len(populated_edges & declared_edges) / len(declared_edges) if declared_edges else 0
        ci = 0
        ci_dominant = ""
        if type_dist and entities > 0:
            ci = type_dist[0]["cnt"] / entities
            ci_dominant = type_dist[0]["type"]

        # Hidden connections count
        hidden_count = 0
        try:
            from second_brain.hidden_connections import find_hidden_connections
            hidden = find_hidden_connections(graph, top_n=100)
            hidden_count = len(hidden)
        except Exception:
            pass

        # =========================================================================
        # Render
        # =========================================================================

        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║              KNOWLEDGE GRAPH STATUS                     ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║  Entities:          {entities:>8}                           ║")
        print(f"║  Edges:             {edges:>8}                           ║")
        print(f"║  Documents:         {docs:>8}                           ║")
        print(f"║  Edge-nodes:        {edge_nodes:>8}                           ║")
        print(f"║  Communities:       {communities:>8}                           ║")
        print(f"║  Hidden connections:{hidden_count:>8}                           ║")
        if last_ingested:
            print(f"║  Last ingestion:    {last_ingested.strftime('%Y-%m-%d %H:%M'):>20}       ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print("║  ONTOLOGY HEALTH                                       ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║  ICR (type coverage):  {format_bar(icr)} {icr:.2f} {health_color(icr):>8} ║")
        print(f"║  IPR (edge coverage):  {format_bar(ipr)} {ipr:.2f} {health_color(ipr):>8} ║")

        # CI uses inverted thresholds (lower is better)
        ci_health = "healthy" if ci < 0.3 else ("warning" if ci < 0.5 else "CRITICAL")
        print(f"║  CI  (imbalance):     {format_bar(ci)} {ci:.2f} {ci_health:>8} ║")
        if ci_dominant:
            print(f"║       dominant: {ci_dominant:<20}                   ║")

        # Unpopulated types
        unpop_types = declared_types - populated_types
        unpop_edges = declared_edges - populated_edges
        if unpop_types:
            print(f"║  Unused types: {', '.join(sorted(unpop_types)):<40} ║")
        if unpop_edges:
            edge_str = ', '.join(sorted(unpop_edges))
            if len(edge_str) > 40:
                edge_str = edge_str[:37] + "..."
            print(f"║  Unused edges: {edge_str:<40} ║")

        print("╠══════════════════════════════════════════════════════════╣")
        print("║  TYPE DISTRIBUTION                                     ║")
        print("╠══════════════════════════════════════════════════════════╣")
        if type_dist:
            for r in type_dist[:8]:
                pct = r["cnt"] / entities * 100 if entities else 0
                bar = "█" * int(pct / 3)
                print(f"║  {r['type']:15} {r['cnt']:>6} ({pct:5.1f}%) {bar:<18} ║")
        else:
            print("║  (empty graph — ingest some documents first)           ║")

        if edge_dist:
            print("╠══════════════════════════════════════════════════════════╣")
            print("║  EDGE DISTRIBUTION                                     ║")
            print("╠══════════════════════════════════════════════════════════╣")
            for r in edge_dist[:8]:
                pct = r["cnt"] / edges * 100 if edges else 0
                bar = "█" * int(pct / 3)
                print(f"║  {r['type']:15} {r['cnt']:>6} ({pct:5.1f}%) {bar:<18} ║")

        print("╚══════════════════════════════════════════════════════════╝")
        print()
    finally:
        graph.close()


if __name__ == "__main__":
    main()
