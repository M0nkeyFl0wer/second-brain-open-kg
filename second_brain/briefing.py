"""
Daily reflection generator for a personal knowledge graph.

Produces a markdown summary of structural observations: new ideas captured,
conflicting beliefs, knowledge gaps between idea clusters, hidden connections,
surprising bridges, and underdeveloped ideas needing attention.

No AI opinions — just what the graph structure reveals about your thinking.
"""
import time
from datetime import datetime, timedelta
from pathlib import Path
from .graph import Graph
from .topology import run_topology, run_persistent_homology, build_networkx_graph
from . import config


def generate_briefing(graph: Graph, output_dir: Path = None) -> str:
    """Generate a daily reflection markdown file from graph structure."""
    output_dir = output_dir or config.BRIEFING_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    report = run_topology(graph)

    sections = []
    sections.append(f"# Daily Reflection — {today}\n")
    sections.append(f"Graph: {report.node_count} entities, {report.edge_count} edges, "
                    f"{report.community_count} communities, {report.component_count} components\n")

    # --- New Ideas (last 24h) ---
    # Surfaces entities added recently so you can see what's fresh in your thinking.
    if "new_ideas" in config.BRIEFING_SECTIONS:
        cutoff = int(time.time()) - 86400
        new_entities = graph.query("""
            MATCH (e:Entity) WHERE e.created_at > $cutoff
            RETURN e.entity_type AS type, count(e) AS cnt
            ORDER BY cnt DESC
        """, parameters={"cutoff": cutoff})

        total_new = sum(e["cnt"] for e in new_entities)
        if total_new > 0:
            sections.append(f"## New Ideas (last 24h): {total_new}\n")
            for e in new_entities:
                sections.append(f"  {e['cnt']} {e['type']}")
            sections.append("")
        else:
            sections.append("## New Ideas (last 24h): None\n")

    # --- Conflicting Beliefs ---
    # Finds CONFLICTS_WITH edges — places where your recorded ideas disagree.
    if "conflicting_beliefs" in config.BRIEFING_SECTIONS:
        conflicts = graph.query("""
            MATCH (a:Entity)-[r:CONFLICTS_WITH]->(b:Entity)
            RETURN a.label AS claim_a, b.label AS claim_b,
                   a.source AS source_a, b.source AS source_b
            LIMIT 10
        """)

        if conflicts:
            sections.append(f"## Conflicting Beliefs: {len(conflicts)}\n")
            for c in conflicts[:5]:
                sections.append(f"  **\"{c['claim_a']}\"**")
                if c.get("source_a"):
                    sections.append(f"  (source: {c['source_a']})")
                sections.append(f"  conflicts with")
                sections.append(f"  **\"{c['claim_b']}\"**")
                if c.get("source_b"):
                    sections.append(f"  (source: {c['source_b']})")
                sections.append("")

    # --- Knowledge Gaps ---
    # Detects community pairs with sparse cross-connections — areas of your
    # thinking that may be related but aren't yet linked.
    if "knowledge_gaps" in config.BRIEFING_SECTIONS and report.gaps:
        sections.append(f"## Knowledge Gaps: {len(report.gaps)}\n")
        for gap in report.gaps[:5]:
            ca = gap["community_a"]
            cb = gap["community_b"]
            priority = gap["priority"]
            entity_a = ca['top_entities'][0]
            entity_b = cb['top_entities'][0]
            sections.append(f"  **{priority}**: \"{entity_a}\" cluster "
                          f"({ca['size']} entities) ↔ "
                          f"\"{entity_b}\" cluster "
                          f"({cb['size']} entities)")
            sections.append(f"  Cross-connections: {gap['cross_edges']}")
            sections.append(f"  → How do your ideas about {entity_a} and {entity_b} relate?")
            sections.append("")

    # --- Hidden Connections ---
    # Pulls from the hidden_connections module if available — these are entities
    # that are semantically similar but not yet linked in the graph.
    if "hidden_connections" in config.BRIEFING_SECTIONS:
        try:
            from .hidden_connections import find_hidden_connections
            hidden = find_hidden_connections(graph)
            if hidden:
                sections.append(f"## Hidden Connections: {len(hidden)}\n")
                for h in hidden[:5]:
                    sections.append(f"  **{h['source_label']}** ↔ **{h['target_label']}**")
                    if h.get("distance") is not None:
                        sections.append(f"  Distance: {h['distance']:.3f}")
                    sections.append("")
        except ImportError:
            # hidden_connections module not yet implemented — skip silently
            pass

    # --- Surprising Bridges ---
    # Entities with high betweenness centrality relative to their degree —
    # they connect different areas of your thinking in unexpected ways.
    if "surprising_bridges" in config.BRIEFING_SECTIONS:
        surprising = [b for b in report.top_betweenness if b.get("surprising")]
        if surprising:
            sections.append(f"## Surprising Bridges: {len(surprising)}\n")
            for s in surprising[:5]:
                sections.append(f"  **{s['label']}** ({s['type']})")
                sections.append(f"  Betweenness: {s['betweenness']} | "
                              f"Degree: {s['degree']}")
                sections.append(f"  → This connects different areas of your thinking.")
                sections.append("")

    # --- Ideas Needing Development ---
    # Unlinked entities older than the prune threshold — ideas you captured
    # but haven't connected to anything else yet.
    if "underdeveloped_ideas" in config.BRIEFING_SECTIONS:
        prune_cutoff = int(time.time()) - (config.PRUNE_AGE_DAYS * 86400)
        unlinked = graph.query("""
            MATCH (e:Entity)
            WHERE NOT (e)-[:RELATES_TO]-()
              AND NOT (e)-[:MENTIONED_IN]-()
              AND e.created_at < $cutoff
            RETURN e.label AS label, e.entity_type AS type
            LIMIT 20
        """, parameters={"cutoff": prune_cutoff})

        if unlinked:
            sections.append(f"## Ideas Needing Development: {len(unlinked)} "
                          f"unlinked (older than {config.PRUNE_AGE_DAYS} days)\n")
            for e in unlinked[:10]:
                sections.append(f"  - {e['label']} ({e['type']})")
            if len(unlinked) > 10:
                sections.append(f"  ... and {len(unlinked) - 10} more")
            sections.append("")

    # --- Graph Health ---
    sections.append("## Graph Health\n")
    sections.append(f"  Components: {report.component_count} "
                   f"(largest: {report.largest_component_size} nodes)")
    sections.append(f"  Isolated: {report.isolated_count}")
    sections.append(f"  Communities: {report.community_count}")
    if report.bridges:
        sections.append(f"  Bridges: {len(report.bridges)} "
                       f"(fragile single-point connections)")
    sections.append("")

    # Assemble
    content = "\n".join(sections)

    # Write to briefing directory
    filepath = output_dir / f"{today}.md"
    filepath.write_text(content)

    # Copy to Obsidian vault inbox for easy review
    if config.VAULT_PATH:
        obsidian_path = Path(config.VAULT_PATH).expanduser()
        if obsidian_path.exists():
            inbox = obsidian_path / "00-inbox"
            inbox.mkdir(exist_ok=True)
            (inbox / f"daily-reflection-{today}.md").write_text(content)

    return content
