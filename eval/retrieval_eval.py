#!/usr/bin/env python3
"""Retrieval evaluation for knowledge graph memory systems.

Measures Recall@K across five query categories:
1. Factual retrieval  -- comparable to LongMemEval/LoCoMo
2. Multi-hop path     -- can path search find chains between distant entities?
3. Contradiction      -- do conflicting edges get surfaced?
4. Gap detection      -- does topology flag missing connections?
5. Thematic/global    -- do community summaries beat flat search?

This eval is designed to be adapted for any memory system. Swap in your
own queries and expected terms, point it at any search API or local graph,
get category-level scores.

Usage:
    python eval/retrieval_eval.py                  # Run all categories
    python eval/retrieval_eval.py --category path  # Run one category
    python eval/retrieval_eval.py --verbose        # Show per-query details
    python eval/retrieval_eval.py --k 10           # Recall@10 instead of @5

Requires: a running search API (default http://127.0.0.1:7700/search)
or adapt search_api() for your system's interface.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

_API_BASE = "http://127.0.0.1:7700"
DEFAULT_K = 5


# ---------------------------------------------------------------------------
# Query definitions -- 20 queries across 5 categories (4 each)
#
# ADAPT THESE for your own knowledge graph. Each query has:
#   - category: which capability it tests
#   - query: the natural language search
#   - mode: search mode (semantic, graph, hybrid, path, global)
#   - expected: substrings that should appear in top-K results
#   - description: what this query tests
#
# A query is a HIT if at least half of expected terms appear in the
# combined text of the top-K results.
# ---------------------------------------------------------------------------

@dataclass
class EvalQuery:
    category: str
    query: str
    mode: str
    expected: list[str]
    description: str = ""


# Example queries for a personal knowledge graph.
# Replace these with queries relevant to YOUR graph.
QUERIES: list[EvalQuery] = [
    # -- Category 1: Factual Retrieval -----------------------------------
    EvalQuery(
        category="factual",
        query="what database does the knowledge graph use",
        mode="hybrid",
        expected=["ladybug", "graph", "database"],
        description="Core infrastructure fact",
    ),
    EvalQuery(
        category="factual",
        query="how is ingestion configured",
        mode="hybrid",
        expected=["ingest", "obsidian", "extract"],
        description="Pipeline knowledge",
    ),
    EvalQuery(
        category="factual",
        query="what entity types does the ontology define",
        mode="hybrid",
        expected=["concept", "person", "source", "project"],
        description="Schema knowledge",
    ),
    EvalQuery(
        category="factual",
        query="how does semantic search work in this system",
        mode="hybrid",
        expected=["vector", "embedding", "search", "similar"],
        description="Retrieval architecture",
    ),

    # -- Category 2: Multi-hop Path --------------------------------------
    EvalQuery(
        category="path",
        query="how does topology connect to retrieval quality",
        mode="path",
        expected=["topology", "retrieval", "gap", "connect"],
        description="Two-hop: topology -> gaps -> retrieval",
    ),
    EvalQuery(
        category="path",
        query="relationship between extraction and graph health",
        mode="path",
        expected=["extract", "entity", "graph", "health"],
        description="Multi-hop: extractor -> entities -> graph",
    ),
    EvalQuery(
        category="path",
        query="how do insights connect to open questions",
        mode="path",
        expected=["insight", "question", "answer", "connect"],
        description="Ontology path: insight ANSWERS question",
    ),
    EvalQuery(
        category="path",
        query="connection between practices and projects",
        mode="path",
        expected=["practice", "project", "applied", "method"],
        description="Ontology path: practice PRACTICED_IN project",
    ),

    # -- Category 3: Contradiction Detection -----------------------------
    EvalQuery(
        category="contradiction",
        query="conflicting ideas or beliefs in the graph",
        mode="hybrid",
        expected=["conflict", "contradict", "tension"],
        description="Should surface CONFLICTS_WITH edges",
    ),
    EvalQuery(
        category="contradiction",
        query="concepts that disagree with each other",
        mode="graph",
        expected=["concept", "disagree", "conflict"],
        description="Graph-mode contradiction surfacing",
    ),
    EvalQuery(
        category="contradiction",
        query="what ideas have I changed my mind about",
        mode="hybrid",
        expected=["change", "revise", "conflict", "update"],
        description="Temporal contradiction: old belief vs new",
    ),
    EvalQuery(
        category="contradiction",
        query="tensions between my beliefs",
        mode="hybrid",
        expected=["tension", "belief", "conflict"],
        description="Cognitive tension from CONFLICTS_WITH",
    ),

    # -- Category 4: Gap Detection ---------------------------------------
    EvalQuery(
        category="gap",
        query="what topics have no connections in the graph",
        mode="hybrid",
        expected=["gap", "isolated", "missing", "connect"],
        description="Structural gaps: disconnected entities",
    ),
    EvalQuery(
        category="gap",
        query="what questions remain unanswered",
        mode="hybrid",
        expected=["question", "unanswered", "open"],
        description="Knowledge gaps: questions without ANSWERS edges",
    ),
    EvalQuery(
        category="gap",
        query="which concepts lack supporting evidence",
        mode="graph",
        expected=["concept", "evidence", "source", "support"],
        description="Provenance gap: concepts without LEARNED_FROM",
    ),
    EvalQuery(
        category="gap",
        query="areas where ideas should connect but don't",
        mode="hybrid",
        expected=["connect", "gap", "related", "missing"],
        description="Synthesis gap from community detection",
    ),

    # -- Category 5: Thematic/Global -------------------------------------
    EvalQuery(
        category="global",
        query="what are the main themes across all my notes",
        mode="global",
        expected=["theme", "topic", "concept", "cluster"],
        description="Community-level themes",
    ),
    EvalQuery(
        category="global",
        query="broad patterns in my knowledge graph",
        mode="global",
        expected=["pattern", "graph", "knowledge", "connect"],
        description="Structural patterns across communities",
    ),
    EvalQuery(
        category="global",
        query="what topics do I know the most about",
        mode="global",
        expected=["topic", "entity", "concept", "count"],
        description="Coverage analysis",
    ),
    EvalQuery(
        category="global",
        query="how do my different projects relate to each other",
        mode="global",
        expected=["project", "relate", "connect", "share"],
        description="Cross-project thematic analysis",
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


def search_api(query: str, mode: str, limit: int) -> list[dict]:
    """Call the search API. Adapt this for your system's interface."""
    resp = requests.post(
        f"{_API_BASE}/search",
        json={"q": query, "mode": mode, "limit": limit},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def evaluate_query(eq: EvalQuery, k: int) -> QueryResult:
    """Run a single query and check if expected terms appear in top-K results."""
    t0 = time.monotonic()

    try:
        results = search_api(eq.query, eq.mode, limit=k)
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

    for cat in scores.values():
        cat.recall = cat.hits / cat.total if cat.total > 0 else 0.0
        latencies = [r.latency_ms for r in cat.results if not r.error]
        cat.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

    return scores


def print_report(scores: dict[str, CategoryScore], k: int) -> None:
    """Print the evaluation report."""
    print()
    print(f"Knowledge Graph Retrieval Eval -- Recall@{k}")
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

        bar = "+" * cat.hits + "." * (cat.total - cat.hits)
        pct = cat.recall * 100

        note = ""
        if cat_name == "factual":
            note = "  (standard benchmark territory)"
        elif cat_name in ("path", "contradiction", "gap"):
            note = "  (no published baseline)"

        print(f"  {cat_name:<16} {bar} {cat.hits}/{cat.total}  R@{k}={pct:5.1f}%  avg={cat.avg_latency_ms:.0f}ms{note}")

    overall = total_hits / total_queries * 100 if total_queries > 0 else 0
    print(f"  {'=' * 56}")
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


def main():
    global _API_BASE

    parser = argparse.ArgumentParser(description="Knowledge graph retrieval evaluation")
    parser.add_argument("--category", "-c", help="Run specific category only")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Recall@K (default: 5)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-query details")
    parser.add_argument("--api", default=_API_BASE, help="API base URL")
    args = parser.parse_args()

    _API_BASE = args.api

    # Verify API is reachable
    try:
        requests.post(
            f"{_API_BASE}/search",
            json={"q": "ping", "limit": 1, "mode": "semantic"},
            timeout=10,
        )
    except Exception:
        print(f"ERROR: Search API not reachable at {_API_BASE}")
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
