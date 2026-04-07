# feat: Multipass -- a multi-pass to the Mem Palace (3D explorer + eval framework + contradiction detection)

> *"Leeloo Dallas, multipass!"*

A multi-pass to the Mem Palace. Because if anyone's earned the right to name a memory system after a palace, it's the person who literally saved the universe with a multipass.

The palace metaphor is genuinely novel. No other system in the [agentic-memory survey](https://github.com/lhl/agentic-memory/blob/main/ANALYSIS-mempalace.md) uses a spatial/navigational metaphor for memory organization. Wings as domains, halls as edge types, rooms as topics, tunnels as cross-domain connections. It's an ontology expressed as architecture rather than declared in a schema file. That makes it intuitive in a way that configuration files never will be.

This issue brings three concrete things: an MVP of a 3D palace visualizer, an eval framework that tests what the palace architecture should be good at, and a working contradiction detection implementation.

## Context

I do data analysis and data viz for clients and have become obsessed with knowledge graph systems that take a complementary approach to your work: semantic ontology with typed edges (SUPPORTS, CONFLICTS_WITH, INSPIRED_BY) in a graph database.

- **[second-brain-open-kg](https://github.com/M0nkeyFl0wer/second-brain-open-kg)**: Early-stage personal knowledge graph for Obsidian vaults. LadybugDB + NetworkX + Ollama, fully local. Actively developed. Ingestion and search work, topology and community summaries are functional but young.

## The benchmark problem (and what to do about it)

Issues #27, #29, and #39 have thoroughly documented the gaps between benchmark claims and benchmark methodology. The [lhl/agentic-memory analysis](https://github.com/lhl/agentic-memory/blob/main/ANALYSIS-mempalace.md) and [dial481/locomo-audit](https://github.com/dial481/locomo-audit) go further, showing that LoCoMo's ground truth itself has ~99 errors making 100% mathematically impossible, and that LongMemEval recall_any@5 is a fundamentally different metric from the end-to-end QA the official leaderboard measures.

These are real problems. But the underlying question is: **what should a memory system actually be evaluated on?**

Standard benchmarks (LongMemEval, LoCoMo, ConvoMem) all test one thing: factual retrieval. "Can you find the specific memory that answers this question?" That's necessary but insufficient. It doesn't test what makes the palace architecture interesting.

The palace's structural primitives (wings, tunnels, halls) enable capabilities that flat memory systems can't do and that standard benchmarks don't test:
- **Tunnels are multi-hop paths.** A room appearing in two wings is a typed cross-domain connection. No other memory system has this primitive.
- **Isolated wings are structural gaps.** A wing with no tunnels is a knowledge silo. The architecture already encodes this. It just needs to be surfaced.
- **Halls could distinguish claim types.** `hall_facts` could split into `hall_supports` and `hall_contradicts` to give the architecture contradiction awareness without any LLM in the loop.

## A retrieval eval that tests what palace architecture enables

We built a [20-question retrieval eval](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/retrieval_eval.py) across five categories. Rerunnable, saves timestamped JSON, designed to be adapted for any memory system:

| Category | What it tests | Palace relevance |
|----------|--------------|-----------------|
| **Factual** | "Find a specific memory" | Baseline. Wing routing helps but this is where every system competes. |
| **Multi-hop path** | "How are X and Y connected?" | Tunnels. This is the palace's unique structural advantage. |
| **Contradiction** | "Surface conflicting claims" | Typed halls could enable this without LLM extraction. |
| **Gap detection** | "What's missing?" | Isolated wings, missing tunnels. Already encoded in the architecture. |
| **Thematic/global** | "What are the broad themes?" | Wings *are* themes. Community detection over tunnel topology. |

Our scores on our own (small, early) graph: factual 100%, path 75%, contradiction 50%, gap 75%, global 75%. We went from 60% to 75% overall in one session by wiring existing infrastructure into the search API and measuring each fix immediately.

**How this addresses the benchmark methodology concerns from #29:**
- We built a separate eval that tests different capabilities. We don't claim LongMemEval or LoCoMo scores.
- Scoring is transparent: substring matching against expected terms in top-K results. No LLM judge, no ambiguous grading.
- Results are timestamped JSON with per-category breakdowns. Fully reproducible.
- The eval tests the *architecture's* capabilities, not the embedding model's retrieval recall.

The framework is designed to be adapted. Swap in mempalace queries and expected terms, point at the MCP search tools, get per-category scores that show what the palace structure actually contributes beyond raw ChromaDB.

## Contradiction detection: a working implementation for #11 and #27

Issue #27 flags that `knowledge_graph.py` has no contradiction detection, only exact-match dedup. Issue #11 requests auto-resolution of conflicting triples. We built the detection side of this.

Our ontology defines a `CONFLICTS_WITH` edge type. [`graph.py:find_contradictions()`](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/second_brain/graph.py) queries these edges for a set of entity IDs and returns both sides with confidence and provenance. About 25 lines of code.

The pattern for `knowledge_graph.py`:

1. When `add_triple()` is called, check if an open triple exists with the same subject and predicate but a different object
2. If so, create a `contradicts` relationship between the two objects (or flag it for review)
3. When querying an entity, include contradictions in the response with both sides and their timestamps

This gives contradiction *detection* without requiring an LLM. Resolution (deciding which claim is correct) can remain manual or use temporal heuristics (newer claim wins, unless flagged).

## Why spatial visualization matters now

[Belova et al. (2026), "An Alternative Trajectory for Generative AI"](https://arxiv.org/abs/2603.14147) argues that scaling is hitting physical limits: grid failures, water consumption, diminishing returns on data. Their proposed alternative: societies of domain-specific models orchestrated by knowledge graphs and ontologies, running on-device. The key finding: "the energetic burden has shifted from one-time training to recurring, unbounded inference."

The palace architecture already points in this direction. Structure-routed retrieval is more energy-efficient than brute-force embedding search. AAAK's compression (whatever the exact ratio turns out to be after proper round-trip evaluation, per #29 section 8) reduces per-query token cost. The whole stack runs local.

But these architectural advantages are invisible to users today. You can't *see* that your security wing has dense tunnels to devops but none to legal. You can't *see* that three projects share a room about "auth-migration." Making the architecture visible demonstrates its value in a way that retrieval recall numbers never will, and that's especially important right now.

## Multipass: working prototype

Single HTML file, no build step, one CDN dependency ([3d-force-graph](https://github.com/vasturiano/3d-force-graph)):

**[eval/multipass/index.html](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/multipass/index.html)**

Features:
- **Wings** render as colored octahedra, rooms as spheres. Force-directed layout naturally clusters wings.
- **Tunnels** are green particle-animated links between wings. Thickness scales with connection count.
- **Isolated wings** (no tunnels) glow red. Instant gap detection.
- **Click any node** for detail panel: wings, halls, content count, connected tunnels.
- Accepts `build_graph()` JSON directly. Paste, file upload, or built-in demo (20 rooms, 7 wings, 17 tunnels).

**[export_palace.py](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/multipass/export_palace.py)** converts a mempalace install to viz format:
```bash
python export_palace.py --palace-path ~/.mempalace/palace > palace.json
# Open index.html, load the file, walk the palace
```

### What the viz reveals that search can't

- **Isolated wings are knowledge silos.** Visible instantly. Invisible to `mempalace search`.
- **Tunnel density maps unexpected relationships.** Two wings with heavy tunnels between them have a deep structural connection that may not be obvious from search results alone.
- **Gap detection becomes spatial.** Our eval showed "what's missing?" queries are the hardest retrieval category (started at 25%). Making gaps *visible* instead of *queryable* sidesteps the retrieval problem entirely.

Integration path: a `mempalace explore` command that calls `build_graph()`, serves HTML on localhost, opens browser. One CDN dependency for the 3D renderer (could be vendored for fully offline use).

## AAAK for structured graph data?

Separate from the above, but worth exploring. Issue #39 found that AAAK mode regresses retrieval vs raw mode (84.2% vs 96.6%). For narrative text, the compression may trade off too much semantic signal.

But entity-relationship triples have much more regular structure than narrative text. Graph triples are already compressed by structure. AAAK-style encoding on top of that might achieve high compression without the retrieval regression, because the "lossy" parts of AAAK (keyword extraction, sentence truncation) don't apply to structured data. The entity codes and relationship types are already atomic. Worth testing with a round-trip eval, as #29 suggests.

---

Three concrete things here: a [3D visualizer](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/multipass/index.html), an [eval framework](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/retrieval_eval.py) that tests capabilities beyond standard benchmarks, and [`find_contradictions()`](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/second_brain/graph.py) as a pattern for #11. Happy to help adapt any of them.
