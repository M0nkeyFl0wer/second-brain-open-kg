#!/usr/bin/env python3
"""Multipass — export mempalace graph data for the 3D palace explorer.

Usage:
    # If mempalace is installed:
    python export_palace.py --palace-path ~/.mempalace/palace > palace.json

    # Then open index.html and load the JSON file.

    # Or pipe directly:
    python export_palace.py --palace-path ~/.mempalace/palace | python -m http.server 8091
"""

import argparse
import json
import sys


def export_from_mempalace(palace_path: str) -> dict:
    """Use mempalace's own build_graph() to export data."""
    try:
        from mempalace.palace_graph import build_graph
        nodes, edges = build_graph(palace_path)
        return {"nodes": nodes, "edges": edges}
    except ImportError:
        print("mempalace not installed. Install with: pip install mempalace", file=sys.stderr)
        sys.exit(1)


def export_from_chromadb(chroma_path: str) -> dict:
    """Build graph directly from ChromaDB collections (no mempalace dependency)."""
    try:
        import chromadb
    except ImportError:
        print("chromadb not installed. Install with: pip install chromadb", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(path=chroma_path)
    nodes = {}
    edges = []

    # Scan all collections for room/wing metadata
    for collection in client.list_collections():
        results = collection.get(include=["metadatas"])
        for meta in (results.get("metadatas") or []):
            if not meta:
                continue
            room = meta.get("room") or meta.get("topic") or "unknown"
            wing = meta.get("wing") or meta.get("project") or "general"
            hall = meta.get("hall") or meta.get("category") or "hall_facts"

            if room not in nodes:
                nodes[room] = {"wings": [], "halls": [], "count": 0, "dates": []}

            if wing not in nodes[room]["wings"]:
                nodes[room]["wings"].append(wing)
            if hall not in nodes[room]["halls"]:
                nodes[room]["halls"].append(hall)
            nodes[room]["count"] += 1

            date = meta.get("date") or meta.get("timestamp") or ""
            if date and date not in nodes[room]["dates"]:
                nodes[room]["dates"].append(date)

    # Detect tunnels: rooms that appear in multiple wings
    for room, meta in nodes.items():
        wings = meta["wings"]
        if len(wings) >= 2:
            for i in range(len(wings)):
                for j in range(i + 1, len(wings)):
                    edges.append({
                        "room": room,
                        "wing_a": wings[i],
                        "wing_b": wings[j],
                        "hall": meta["halls"][0] if meta["halls"] else "general",
                        "count": meta["count"],
                    })

    return {"nodes": nodes, "edges": edges}


def main():
    parser = argparse.ArgumentParser(description="Export mempalace graph for 3D explorer")
    parser.add_argument("--palace-path", help="Path to mempalace palace directory")
    parser.add_argument("--chroma-path", help="Path to ChromaDB directory (no mempalace needed)")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    args = parser.parse_args()

    if args.palace_path:
        data = export_from_mempalace(args.palace_path)
    elif args.chroma_path:
        data = export_from_chromadb(args.chroma_path)
    else:
        parser.error("Provide --palace-path or --chroma-path")

    output = json.dumps(data, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
