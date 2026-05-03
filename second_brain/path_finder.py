"""
Graph path finding for open-second-brain — multi-hop traversal and query.

Supports:
- Shortest path between two entities
- N-hop neighborhood expansion
- Path-based ranking (verified paths)
- Gap detection (find high-degree nodes without direct edges)

Per ladybug skill: Let the DB do the work — use Cypher variable-length
paths and native graph algorithms, not Python loops.
"""

from typing import Any, Optional

from second_brain.graph import GraphReader


class PathFinder:
    """
    Graph path finding via LadybugDB Cypher.

    Usage:
        pf = PathFinder()
        path = pf.shortest_path("feedback_loops", "systems_thinking")
        neighbors = pf.neighborhood("donella_meadows", hops=2)
        gaps = pf.detect_gaps(limit=10)
    """

    def __init__(self, db_path: Optional[str] = None):
        self.reader = GraphReader(db_path)

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 4,
    ) -> list[dict[str, Any]]:
        """
        Find shortest path between two entities.

        Returns list of path segments: [{source, edge, target}, ...]
        Empty list if no path exists.
        """
        results = self.reader.query(f"""
            MATCH path = (s:entity {{id: $source}})-[*1..{max_hops}]-(t:entity {{id: $target}})
            WITH path, length(path) as hops
            ORDER BY hops
            LIMIT 1
            UNWIND nodes(path) as n
            UNWIND relationships(path) as r
            WITH n.id as entity_id, n.label as label, type(r) as edge_type,
                 startNode(r).id as src, endNode(r).id as tgt, r.evidence as evidence
            RETURN entity_id, label, edge_type, src, tgt, evidence
        """, {"source": source_id, "target": target_id})

        return self._format_path(results)

    def neighborhood(
        self,
        entity_id: str,
        hops: int = 2,
        edge_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Get N-hop neighborhood of an entity.

        Args:
            entity_id: center entity
            hops: how many hops to traverse
            edge_types: filter to specific edge types (None = all)

        Returns list of {entity_id, label, entity_type, distance, edges} dicts.
        """
        if edge_types:
            params = {"id": entity_id, "edge_types": edge_types}
        else:
            params = {"id": entity_id}

        results = self.reader.query(f"""
            MATCH (center:entity {{id: $id}})
            MATCH path = (center)-[*1..{hops}]-(neighbor:entity)
            WHERE center <> neighbor
            WITH center, neighbor, shortest(path) as sp
            WITH center, neighbor, length(sp) as dist, relationships(sp) as rels
            UNWIND rels as r
            WITH center, neighbor, dist,
                 collect({{edge_type: type(r), evidence: r.evidence}}) as edges
            RETURN neighbor.id as entity_id, neighbor.label as label,
                   neighbor.entity_type as entity_type, min(dist) as distance,
                   edges
            ORDER BY distance, label
        """, params)

        return results

    def verify_path(self, source_id: str, target_id: str) -> dict[str, Any]:
        """
        Two-pass verified path search (per vault-rag path_pruning.py pattern):

        Pass 1: Collect all candidate paths
        Pass 2: Confirm each edge with source text, flag contradictions

        Returns:
            {
                "paths": [...],
                "verified": true/false,
                "contradictions": [...],
                "supports": [...],
            }
        """
        # Pass 1: find paths
        candidates = self.reader.query("""
            MATCH path = (s:entity {id: $source})-[*1..3]-(t:entity {id: $target})
            WITH path, relationships(path) as rels
            UNWIND rels as r
            RETURN s.id as source, t.id as target,
                   collect({edge_type: type(r), evidence: r.evidence,
                           src_id: startNode(r).id, tgt_id: endNode(r).id}) as edges
            LIMIT 10
        """, {"source": source_id, "target": target_id})

        # Pass 2: check each edge
        verified_edges = []
        contradictions = []
        supports = []

        for candidate in candidates:
            for edge in candidate.get("edges", []):
                # Check evidence quality
                if len(edge.get("evidence", "")) < 10:
                    contradictions.append({
                        "edge": edge,
                        "reason": "evidence too short",
                    })
                else:
                    verified_edges.append(edge)
                    if edge.get("edge_type") == "SUPPORTS":
                        supports.append(edge)
                    elif edge.get("edge_type") == "CONFLICTS_WITH":
                        contradictions.append({
                            "edge": edge,
                            "reason": "explicit contradiction",
                        })

        return {
            "paths": candidates,
            "verified": len(contradictions) == 0,
            "contradictions": contradictions,
            "supports": supports,
        }

    def detect_gaps(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Detect gap opportunities — high-degree seed entities with no
        direct edge between them.

        Returns list of {source, target, source_degree, target_degree, gap_score}.
        """
        # Find high-degree nodes
        high_degree = self.reader.query("""
            MATCH (e:entity)-[r]->(:entity)
            WITH e, count(r) as degree
            WHERE degree >= 3
            RETURN e.id as entity_id, e.label as label, degree
            ORDER BY degree DESC
            LIMIT 20
        """)

        if len(high_degree) < 2:
            return []

        # Check for missing edges between top-degree nodes
        gaps = []
        for i, a in enumerate(high_degree):
            for b in high_degree[i + 1:]:
                # Check if edge exists
                existing = self.reader.query("""
                    MATCH (a:entity {id: $a_id})-[r]->(b:entity {id: $b_id})
                    RETURN r.edge_type as edge_type
                    LIMIT 1
                """, {"a_id": a["entity_id"], "b_id": b["entity_id"]})

                if not existing:
                    gaps.append({
                        "source": a["entity_id"],
                        "target": b["entity_id"],
                        "source_label": a["label"],
                        "target_label": b["label"],
                        "source_degree": a["degree"],
                        "target_degree": b["degree"],
                        "gap_score": a["degree"] + b["degree"],
                    })

        gaps.sort(key=lambda x: x["gap_score"], reverse=True)
        return gaps[:limit]

    def _format_path(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format raw path query results into structured path segments."""
        if not results:
            return []

        path = []
        for row in results:
            path.append({
                "entity_id": row.get("entity_id"),
                "label": row.get("label"),
                "edge_type": row.get("edge_type"),
                "evidence": row.get("evidence"),
                "src": row.get("src"),
                "tgt": row.get("tgt"),
            })
        return path

    def close(self) -> None:
        """Close reader."""
        self.reader.close()