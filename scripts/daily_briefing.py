#!/usr/bin/env python3
"""Generate a daily briefing from the knowledge graph."""
import sys
sys.path.insert(0, ".")

from second_brain.graph import Graph
from second_brain.briefing import generate_briefing

def main():
    graph = Graph()
    
    entities = graph.entity_count()
    edges = graph.edge_count()
    
    if entities == 0:
        print("Graph is empty. Ingest some documents first:")
        print("  python scripts/ingest_folder.py")
        return
    
    print(f"Analyzing graph ({entities} entities, {edges} edges)...")
    content = generate_briefing(graph)
    print(content)
    print(f"\nBriefing saved to briefings/ directory.")

if __name__ == "__main__":
    main()
