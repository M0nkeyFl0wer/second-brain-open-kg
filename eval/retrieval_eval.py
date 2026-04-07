#!/usr/bin/env python3
"""Retrieval evaluation for vault-rag knowledge graph.

Measures Recall@K across five query categories:
1. Factual retrieval  — comparable to LongMemEval/LoCoMo benchmarks
2. Multi-hop path     — can path search find chains between distant entities?
3. Contradiction      — do CONTRADICTS edges surface conflicting claims?
4. Gap detection      — does topology flag missing connections?
5. Thematic/global    — do community summaries beat flat search for broad queries?

Usage:
    python eval/retrieval_eval.py                  # Run all categories
    python eval/retrieval_eval.py --category path  # Run one category
    python eval/retrieval_eval.py --verbose        # Show per-query details
    python eval/retrieval_eval.py --k 10           # Recall@10 instead of @5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

_API_BASE = "http://127.0.0.1:7720"
DEFAULT_K = 5


# ---------------------------------------------------------------------------
# Query definitions — 20 queries across 5 categories (4 each)
# ---------------------------------------------------------------------------

@dataclass
class EvalQuery:
    """A single evaluation query with expected results."""
    category: str
    query: str
    mode: str  # semantic, graph, hybrid, path
    expected: list[str]  # substrings that should appear in top-K result texts/paths
    description: str = ""
    cypher: str | None = None  # for graph-native checks (contradiction, gap)


QUERIES: list[EvalQuery] = [
    # ── Category 1: Factual Retrieval ──────────────────────────────────
    # Comparable to LongMemEval — "can you find the right memory?"
    EvalQuery(
        category="factual",
        query="what database does vault-rag use for the knowledge graph",
        mode="hybrid",
        expected=["ladybug", "ldb", "graph"],
        description="Core infrastructure fact",
    ),
    EvalQuery(
        category="factual",
        query="how is the overnight enrichment schedule configured",
        mode="hybrid",
        expected=["enrich", "timer", "systemd"],
        description="Operational knowledge — enrichment pipeline",
    ),
    EvalQuery(
        category="factual",
        query="what entity types does the ontology define",
        mode="hybrid",
        expected=["person", "project", "concept", "ontology"],
        description="Schema knowledge — entity type vocabulary",
    ),
    EvalQuery(
        category="factual",
        query="how does the context strategy system filter results",
        mode="hybrid",
        expected=["context", "strateg", "filter", "task_type"],
        description="Retrieval architecture knowledge",
    ),

    # ── Category 2: Multi-hop Path ─────────────────────────────────────
    # Unique to graph-based systems — chain reasoning across typed edges
    EvalQuery(
        category="path",
        query="how does topology analysis connect to retrieval quality",
        mode="path",
        expected=["topology", "retrieval", "gap", "bridge"],
        description="Two-hop: topology → gap detection → retrieval improvement",
    ),
    EvalQuery(
        category="path",
        query="relationship between extraction quality and graph health",
        mode="path",
        expected=["extract", "entity", "graph", "health"],
        description="Multi-hop: extractor → entities → edges → graph metrics",
    ),
    EvalQuery(
        category="path",
        query="how do enrichment patterns affect overnight schedule outcomes",
        mode="path",
        expected=["enrichment", "pattern", "schedule", "overnight"],
        description="Cross-domain path: lifecycle → scheduler → results",
    ),
    EvalQuery(
        category="path",
        query="connection between ontology validation and false bridges",
        mode="path",
        expected=["ontology", "valid", "bridge", "false"],
        description="Causal chain: bad types → wrong edges → false bridges",
    ),

    # ── Category 3: Contradiction Detection ────────────────────────────
    # Unique — can the system surface conflicting claims?
    EvalQuery(
        category="contradiction",
        query="sqlite alternative tests whether hybrid graph database approach is necessary",
        mode="hybrid",
        expected=["sqlite", "hybrid", "graph", "alternative"],
        description="Known tension: SQLite-only vs hybrid graph DB approaches",
        cypher=(
            "MATCH (e1:Entity)-[r:ENTITY_TO_ENTITY {edge_type: 'CONTRADICTS'}]->(e2:Entity) "
            "RETURN e1.name, e2.name LIMIT 10"
        ),
    ),
    EvalQuery(
        category="contradiction",
        query="security input validation vs command injection prevention tradeoffs",
        mode="hybrid",
        expected=["security", "input", "valid", "command"],
        description="Known CONTRADICTS edges: security concepts in tension",
    ),
    EvalQuery(
        category="contradiction",
        query="conflicting claims about deployment architecture",
        mode="hybrid",
        expected=["deploy", "host", "server"],
        description="Cross-project deployment contradictions",
    ),
    EvalQuery(
        category="contradiction",
        query="tensions in graph schema design decisions",
        mode="hybrid",
        expected=["schema", "consolidat", "table", "edge"],
        description="Schema evolution: 22 tables → 8, old vs new",
    ),

    # ── Category 4: Gap Detection ──────────────────────────────────────
    # Unique — does topology find what's missing?
    EvalQuery(
        category="gap",
        query="what topics lack cross-references in the knowledge graph",
        mode="hybrid",
        expected=["gap", "disconnect", "component", "bridge"],
        description="Topology should surface disconnected communities",
        cypher=(
            "MATCH (e:Entity) WHERE NOT (e)-[:ENTITY_TO_ENTITY]->() "
            "AND NOT ()-[:ENTITY_TO_ENTITY]->(e) "
            "RETURN e.name, e.entity_type LIMIT 20"
        ),
    ),
    EvalQuery(
        category="gap",
        query="which projects have no knowledge graph entities",
        mode="graph",
        expected=["project", "entity", "missing"],
        description="Coverage gap — projects without graph representation",
    ),
    EvalQuery(
        category="gap",
        query="areas where LINKS_TO edges are missing between related notes",
        mode="hybrid",
        expected=["link", "note", "connect"],
        description="Structural gap — notes that should be linked but aren't",
    ),
    EvalQuery(
        category="gap",
        query="synthesis opportunities between unconnected topic clusters",
        mode="path",
        expected=["synthes", "cluster", "communit", "gap"],
        description="Creative gap — topology synthesis suggestions",
    ),

    # ── Category 5: Thematic/Global ────────────────────────────────────
    # Community-level reasoning, broad questions — tests mode=global
    EvalQuery(
        category="global",
        query="surveillance and privacy themes across the knowledge base",
        mode="global",
        expected=["surveil", "privacy", "monitor", "panoptic"],
        description="Cross-cutting theme that spans multiple projects",
    ),
    EvalQuery(
        category="global",
        query="content engine architecture patterns shared across projects",
        mode="global",
        expected=["content", "engine", "strong coast", "elephant"],
        description="Architectural pattern that recurs across projects",
    ),
    EvalQuery(
        category="global",
        query="graph database design decisions and their rationale",
        mode="global",
        expected=["graph", "database", "decision", "ladybug"],
        description="Decision archaeology — why things are the way they are",
    ),
    EvalQuery(
        category="global",
        query="topology and persistent homology applications",
        mode="global",
        expected=["topology", "homolog", "ripser", "betti"],
        description="Mathematical framework theme across the system",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation logic
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    query: EvalQuery
    hit: bool
    matched_terms: list[str]
    missed_terms: list[str]
    top_results: list[str]
    latency_ms: float
    error: str | None = None


@dataclass
class CategoryScore:
    category: str
    total: int
    hits: int
    recall: float
    avg_latency_ms: float
    results: list[QueryResult] = field(default_factory=list)


def search_api(query: str, mode: str, limit: int, api_base: str = "") -> list[dict]:
    """Call the vault-rag search API."""
    base = api_base or _API_BASE
    resp = requests.post(
        f"{base}/search",
        json={"q": query, "mode": mode, "limit": limit},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def cypher_api(cypher: str, api_base: str = "") -> str:
    """Call the vault-rag graph/cypher API."""
    base = api_base or _API_BASE
    resp = requests.post(
        f"{base}/graph",
        json={"cypher": cypher},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def evaluate_query(eq: EvalQuery, k: int) -> QueryResult:
    """Run a single query and check if expected terms appear in top-K results."""
    t0 = time.monotonic()

    try:
        results = search_api(eq.query, eq.mode, limit=k, api_base=_API_BASE)
    except Exception as e:
        return QueryResult(
            query=eq, hit=False, matched_terms=[], missed_terms=eq.expected,
            top_results=[], latency_ms=0, error=str(e),
        )

    latency = (time.monotonic() - t0) * 1000

    # Collect all text from results for matching
    result_texts = []
    for r in results:
        text = f"{r.get('text', '')} {r.get('path', '')}".lower()
        result_texts.append(text)

    combined = " ".join(result_texts)

    matched = [t for t in eq.expected if t.lower() in combined]
    missed = [t for t in eq.expected if t.lower() not in combined]

    # Hit = at least half of expected terms found
    hit = len(matched) >= max(1, len(eq.expected) // 2)

    top_paths = [r.get("path", "?") for r in results[:3]]

    return QueryResult(
        query=eq, hit=hit, matched_terms=matched, missed_terms=missed,
        top_results=top_paths, latency_ms=latency,
    )


def run_eval(
    categories: list[str] | None = None,
    k: int = DEFAULT_K,
    verbose: bool = False,
) -> dict[str, CategoryScore]:
    """Run the full evaluation suite."""

    queries = QUERIES
    if categories:
        queries = [q for q in queries if q.category in categories]

    scores: dict[str, CategoryScore] = {}

    for eq in queries:
        result = evaluate_query(eq, k)

        if eq.category not in scores:
            scores[eq.category] = CategoryScore(
                category=eq.category, total=0, hits=0, recall=0.0, avg_latency_ms=0.0,
            )

        cat = scores[eq.category]
        cat.total += 1
        cat.hits += int(result.hit)
        cat.results.append(result)

        if verbose:
            status = "HIT" if result.hit else "MISS"
            print(f"  [{status}] {eq.description}")
            print(f"         query: {eq.query}")
            print(f"         matched: {result.matched_terms}")
            if result.missed_terms:
                print(f"         missed:  {result.missed_terms}")
            print(f"         top: {result.top_results}")
            print(f"         latency: {result.latency_ms:.0f}ms")
            if result.error:
                print(f"         ERROR: {result.error}")
            print()

    # Compute final scores
    for cat in scores.values():
        cat.recall = cat.hits / cat.total if cat.total > 0 else 0.0
        latencies = [r.latency_ms for r in cat.results if not r.error]
        cat.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

    return scores


def print_report(scores: dict[str, CategoryScore], k: int) -> None:
    """Print the evaluation report."""
    print()
    print(f"Vault-RAG Retrieval Eval — Recall@{k}")
    print("=" * 60)

    total_hits = 0
    total_queries = 0

    category_order = ["factual", "path", "contradiction", "gap", "global"]
    for cat_name in category_order:
        if cat_name not in scores:
            continue
        cat = scores[cat_name]
        total_hits += cat.hits
        total_queries += cat.total

        bar = "█" * cat.hits + "░" * (cat.total - cat.hits)
        pct = cat.recall * 100

        # Comparable note for factual
        note = ""
        if cat_name == "factual":
            note = "  (LongMemEval baseline: 96.6%)"
        elif cat_name in ("path", "contradiction", "gap"):
            note = "  (no published baseline)"

        print(f"  {cat_name:<16} {bar} {cat.hits}/{cat.total}  R@{k}={pct:5.1f}%  avg={cat.avg_latency_ms:.0f}ms{note}")

    overall = total_hits / total_queries * 100 if total_queries > 0 else 0
    print(f"  {'─' * 56}")
    print(f"  {'OVERALL':<16}       {total_hits}/{total_queries}  R@{k}={overall:5.1f}%")
    print()

    # Export JSON for tracking over time
    export = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "k": k,
        "overall_recall": round(overall / 100, 4),
        "categories": {
            name: {
                "recall": round(cat.recall, 4),
                "hits": cat.hits,
                "total": cat.total,
                "avg_latency_ms": round(cat.avg_latency_ms, 1),
            }
            for name, cat in scores.items()
        },
    }

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_file = results_dir / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(export, indent=2))
    print(f"  Results saved to {out_file}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    global _API_BASE

    parser = argparse.ArgumentParser(description="Vault-RAG retrieval evaluation")
    parser.add_argument("--category", "-c", help="Run specific category only")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Recall@K (default: 5)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-query details")
    parser.add_argument("--api", default=_API_BASE, help="API base URL")
    args = parser.parse_args()

    _API_BASE = args.api

    # Verify API is reachable (use search endpoint — /stats can hang)
    try:
        requests.post(
            f"{_API_BASE}/search",
            json={"q": "ping", "limit": 1, "mode": "semantic"},
            timeout=10,
        )
    except Exception:
        print(f"ERROR: Vault-RAG API not reachable at {_API_BASE}")
        print("Start it with: systemctl --user start knowledge-graph-api")
        sys.exit(1)

    categories = [args.category] if args.category else None

    print(f"\nRunning retrieval eval against {_API_BASE} ...")
    if categories:
        print(f"  Categories: {categories}")
    print()

    scores = run_eval(categories=categories, k=args.k, verbose=args.verbose)
    print_report(scores, args.k)


if __name__ == "__main__":
    main()
