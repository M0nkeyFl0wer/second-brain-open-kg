"""
Daily briefing generator. Produces a markdown summary of what the graph found.
Contradictions, gaps, surprising connections, new entities, unlinked nodes.
No AI — just structural observations from the graph.
"""
import time
from datetime import datetime, timedelta
from pathlib import Path
from .graph import Graph
from .topology import run_topology, run_persistent_homology, build_networkx_graph
from . import config


def generate_briefing(graph: Graph, output_dir: Path = None) -> str:
    """Generate a daily briefing markdown file."""
    output_dir = output_dir or config.BRIEFING_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    report = run_topology(graph)

    sections = []
    sections.append(f"# Daily Briefing — {today}\n")
    sections.append(f"Graph: {report.node_count} entities, {report.edge_count} edges, "
                    f"{report.community_count} communities, {report.component_count} components\n")

    # --- New entities (last 24h) ---
    if "new_entities" in config.BRIEFING_SECTIONS:
        cutoff = int(time.time()) - 86400
        new_entities = graph.query("""
            MATCH (e:Entity) WHERE e.created_at > $cutoff
            RETURN e.entity_type AS type, count(e) AS cnt
            ORDER BY cnt DESC
        """, parameters={"cutoff": cutoff})

        total_new = sum(e["cnt"] for e in new_entities)
        if total_new > 0:
            sections.append(f"## New Entities (last 24h): {total_new}\n")
            for e in new_entities:
                sections.append(f"  {e['cnt']} {e['type']}")
            sections.append("")
        else:
            sections.append("## New Entities (last 24h): None\n")

    # --- Contradictions ---
    if "contradictions" in config.BRIEFING_SECTIONS and report.contradictions:
        sections.append(f"## Contradictions Found: {len(report.contradictions)}\n")
        for c in report.contradictions[:5]:
            sections.append(f"  **\"{c['claim_a']}\"**")
            if c.get("source_a"):
                sections.append(f"  (source: {c['source_a']})")
            sections.append(f"  contradicts")
            sections.append(f"  **\"{c['claim_b']}\"**")
            if c.get("source_b"):
                sections.append(f"  (source: {c['source_b']})")
            sections.append("")

    # --- Structural gaps ---
    if "structural_gaps" in config.BRIEFING_SECTIONS and report.gaps:
        sections.append(f"## Structural Gaps: {len(report.gaps)}\n")
        for gap in report.gaps[:5]:
            ca = gap["community_a"]
            cb = gap["community_b"]
            priority = gap["priority"]
            sections.append(f"  **{priority}**: \"{ca['top_entities'][0]}\" cluster "
                          f"({ca['size']} entities) ↔ "
                          f"\"{cb['top_entities'][0]}\" cluster "
                          f"({cb['size']} entities)")
            sections.append(f"  Cross-connections: {gap['cross_edges']}")
            sections.append(f"  → {gap['question']}")
            sections.append("")

    # --- Surprising connections ---
    if "surprising_connections" in config.BRIEFING_SECTIONS:
        surprising = [b for b in report.top_betweenness if b.get("surprising")]
        if surprising:
            sections.append(f"## Surprising Connections: {len(surprising)}\n")
            for s in surprising[:5]:
                sections.append(f"  **{s['label']}** ({s['type']})")
                sections.append(f"  Betweenness: {s['betweenness']} | "
                              f"Degree: {s['degree']}")
                sections.append(f"  → High structural importance despite appearing in "
                              f"few documents. Worth investigating.")
                sections.append("")

    # --- Unlinked entities ---
    if "unlinked_entities" in config.BRIEFING_SECTIONS:
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
            sections.append(f"## Entities Needing Attention: {len(unlinked)} "
                          f"unlinked (older than {config.PRUNE_AGE_DAYS} days)\n")
            for e in unlinked[:10]:
                sections.append(f"  - {e['label']} ({e['type']})")
            if len(unlinked) > 10:
                sections.append(f"  ... and {len(unlinked) - 10} more")
            sections.append("")

    # --- Summary stats ---
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

    # Optionally copy to Obsidian vault
    if config.OBSIDIAN_VAULT:
        obsidian_path = Path(config.OBSIDIAN_VAULT).expanduser()
        if obsidian_path.exists():
            inbox = obsidian_path / "00-inbox"
            inbox.mkdir(exist_ok=True)
            (inbox / f"graph-briefing-{today}.md").write_text(content)

    return content
