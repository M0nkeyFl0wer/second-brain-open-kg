#!/usr/bin/env python3
"""Validate ONTOLOGY.md syntax and check graph health against ontology."""
import sys

sys.path.insert(0, ".")

from second_brain.ontology import Ontology
from second_brain.graph import Graph


def main():
    ontology = Ontology()
    print(f"Ontology: {ontology}")
    print(f"  Entity types: {', '.join(ontology.entity_type_names)}")
    print(f"  Edge types: {', '.join(ontology.edge_type_names)}")

    # Check for boundary examples
    missing_examples = []
    for name, et in ontology.entity_types.items():
        if not et.exotypical:
            missing_examples.append(name)
    if missing_examples:
        print(f"\n  Types missing exotypical examples: {', '.join(missing_examples)}")
        print(f"  Tip: Add boundary examples to improve extraction accuracy")

    # Check graph health if it exists
    try:
        graph = Graph(ontology=ontology)
        entities = graph.entity_count()
        edges = graph.edge_count()
        docs = graph.document_count()
        print(f"\nGraph: {entities} entities, {edges} edges, {docs} documents")

        if entities == 0:
            print("  Graph is empty — ingest documents first.")
            graph.close()
            return

        # ICR: Instantiated Class Ratio
        type_dist = graph.query(
            "MATCH (e:Entity) RETURN e.entity_type AS t, count(e) AS c")
        populated = set(r["t"] for r in type_dist)
        declared = set(ontology.entity_type_names)
        icr = len(populated & declared) / len(declared) if declared else 0

        print(f"\n  ICR (type coverage): {icr:.2f}", end="")
        if icr >= 0.8:
            print(" — healthy")
        elif icr >= 0.5:
            print(" — warning (some declared types have no data)")
        else:
            print(" — critical (ontology doesn't match reality)")

        # CI: Class Imbalance
        total = sum(r["c"] for r in type_dist)
        max_row = max(type_dist, key=lambda r: r["c"])
        ci = max_row["c"] / total if total else 0

        print(f"  CI (class imbalance): {ci:.2f}", end="")
        if ci < 0.3:
            print(" — healthy")
        elif ci < 0.5:
            print(f" — warning (dominant: {max_row['t']} at {max_row['c']}/{total})")
        else:
            print(f" — critical (dominant: {max_row['t']} at {max_row['c']}/{total})")

        # IPR: Instantiated Property Ratio (edge types)
        edge_dist = graph.query(
            "MATCH ()-[r:RELATES_TO]->() RETURN r.edge_type AS t, count(r) AS c")
        populated_edges = set(r["t"] for r in edge_dist)
        declared_edges = set(ontology.edge_type_names)
        ipr = (len(populated_edges & declared_edges) / len(declared_edges)
               if declared_edges else 0)

        print(f"  IPR (edge coverage): {ipr:.2f}", end="")
        if ipr >= 0.8:
            print(" — healthy")
        elif ipr >= 0.5:
            print(" — warning")
        else:
            print(" — critical")

        # Distribution details
        print(f"\n  Type distribution:")
        for r in sorted(type_dist, key=lambda r: -r["c"]):
            pct = r["c"] / total * 100
            bar = "█" * int(pct / 2)
            print(f"    {r['t']:15} {r['c']:5} ({pct:5.1f}%) {bar}")

        # Unpopulated types
        unpop = declared - populated
        if unpop:
            print(f"\n  Unpopulated types: {', '.join(sorted(unpop))}")

        # Unpopulated edges
        unpop_edges = declared_edges - populated_edges
        if unpop_edges:
            print(f"  Unpopulated edges: {', '.join(sorted(unpop_edges))}")

        graph.close()

    except Exception as e:
        print(f"\nNo graph found (expected on first run): {e}")


if __name__ == "__main__":
    main()
