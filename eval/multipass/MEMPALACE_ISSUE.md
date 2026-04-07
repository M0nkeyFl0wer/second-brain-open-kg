# feat: Multipass -- multi-hop paths through the Mem Palace

![multipass](https://i.imgflip.com/eiw5f.jpg)

Three concrete things here: a 3D palace visualizer that makes structural knowledge visible, an eval framework that tests what palace architecture uniquely enables, and a potentially useful contradiction detection pattern.

## Why visualization matters more than benchmarks right now

First of all thank you. The palace metaphor is one of the more interesting things I've come across recently in the [agentic-memory survey](https://github.com/lhl/agentic-memory/blob/main/ANALYSIS-mempalace.md). No other system uses a spatial/navigational metaphor for memory organization. Wings as domains, halls as edge types, rooms as topics, tunnels as cross-domain connections. It's an ontology expressed as architecture rather than declared in a schema file.

But here's the thing: **what would happen if we went further into visualization.**

You can't necessarily tell from `mempalace search` that your security wing has dense tunnels to devops but none to legal. You can't see that three projects share a room about auth-migration. You can't spot the isolated wing with no tunnels to anything -- a knowledge silo hiding in plain sight. These are structural properties. They exist in the palace right now, but they're invisible until you render the graph.

Visualization doesn't just demonstrate value. It changes how you interact with the system. When you can see that two wings are connected by a single tunnel, you know where to add knowledge. When you see a cluster of rooms with no cross-wing connections, you've found a gap without asking a question. The palace becomes a navigable space rather than a search endpoint.

On a related note, I think this kind of memory system is part of an interesting and important alternative vision for "AI". Check [Belova et al. (2026), "An Alternative Trajectory for Generative AI"](https://arxiv.org/abs/2603.14147), which argues that scaling is hitting physical limits and the alternative is structure-routed retrieval over domain-specific knowledge graphs. The palace already points in this direction. Making the architecture visible demonstrates its value in a way that retrieval recall numbers never will.

## Multipass: traverse your memory palace in 3D

Single HTML file, no build step, one CDN dependency ([3d-force-graph](https://github.com/vasturiano/3d-force-graph)):

**[eval/multipass/index.html](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/multipass/index.html)**

The name is a double reference: multi-hop path traversal through graph nodes, and a Fifth Element callback because the palace metaphor deserves one.

![multipass-demo](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/multipass/multipass-demo.png?raw=true)

Features:
- **Wings** render as colored nodes that anchor spatial clusters. Rooms orbit their wings. Force-directed layout naturally groups related knowledge.
- **Tunnels** are teal links with orange particle flow between wings. Thickness scales with connection count. These are the multi-hop paths -- the paths between domains that only a graph structure can traverse.
- **Isolated wings** (no tunnels) glow red. Instant gap detection without querying.
- **Click any node** for a detail panel: wings, halls, content count, connected corridors.
- Accepts `build_graph()` JSON directly. Paste, file upload, or built-in demo (20 rooms, 7 wings, 17 tunnels).

**[export_palace.py](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/multipass/export_palace.py)** converts a mempalace install to viz format:
```bash
python export_palace.py --palace-path ~/.mempalace/palace > palace.json
# Open index.html, load the file, walk the palace
```

### What the viz reveals that search can't

- **Isolated wings are knowledge silos.** Visible instantly. Invisible to `mempalace search`.
- **Tunnel density maps unexpected relationships.** Two wings with heavy tunnels between them have a deep structural connection that may not be obvious from search results alone.
- **Gap detection becomes spatial.** Our eval showed "what's missing?" queries started as the hardest retrieval category (25%). Making gaps *visible* instead of *queryable* sidesteps the retrieval problem entirely.

Integration path: a `mempalace explore` command that calls `build_graph()`, serves HTML on localhost, opens browser. One CDN dependency for the 3D renderer (could be vendored for fully offline use).

## A retrieval eval that tests what palace architecture enables

The benchmark problem is well-documented in issues #27, #29, and #39. The [lhl/agentic-memory analysis](https://github.com/lhl/agentic-memory/blob/main/ANALYSIS-mempalace.md) and [dial481/locomo-audit](https://github.com/dial481/locomo-audit) show real methodological issues with LoCoMo and LongMemEval.

But the deeper question is: **what should a memory system be evaluated on?**

Standard benchmarks test one thing: factual retrieval. Can you find the specific memory that answers this question? That's necessary but insufficient. It doesn't test what makes the palace architecture interesting.

The palace's structural primitives enable capabilities that flat memory systems can't do and that standard benchmarks don't test:
- **Tunnels are multi-hop paths.** A room in two wings is a typed cross-domain connection. No other memory system has this structural primitive.
- **Isolated wings are structural gaps.** A wing with no tunnels is a knowledge silo. The architecture already encodes this.
- **Halls could distinguish claim types.** `hall_facts` could split into `hall_supports` and `hall_contradicts` to give the architecture contradiction awareness without any LLM in the loop.

We built a [20-question retrieval eval](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/retrieval_eval.py) across five categories:

| Category | What it tests | Palace relevance |
|----------|--------------|-----------------|
| **Factual** | "Find a specific memory" | Baseline. Wing routing helps but this is where every system competes. |
| **Multi-hop path** | "How are X and Y connected?" | Tunnels. This is the palace's unique structural advantage. |
| **Contradiction** | "Surface conflicting claims" | Typed halls could enable this without LLM extraction. |
| **Gap detection** | "What's missing?" | Isolated wings, missing tunnels. Already encoded in the architecture. |
| **Thematic/global** | "What are the broad themes?" | Wings *are* themes. Community detection over tunnel topology. |

Current scores on our own (small, early) graph: factual 100%, path 75%, contradiction 100%, gap 75%, global 75%. We went from 60% to 85% overall across two sessions by wiring existing infrastructure into the search API and measuring each fix.

**How this addresses the benchmark methodology concerns from #29:**
- Separate eval that tests different capabilities. No LongMemEval or LoCoMo claims.
- Scoring is transparent: substring matching against expected terms in top-K results. No LLM judge.
- Results are timestamped JSON with per-category breakdowns. Fully reproducible.
- Tests the *architecture's* capabilities, not the embedding model's retrieval recall.

The framework is designed to be adapted. Swap in mempalace queries and expected terms, point at the MCP search tools, get per-category scores that show what the palace structure actually contributes beyond raw ChromaDB.

## Contradiction detection: a working implementation for #11 and #27

Issue #27 flags that `knowledge_graph.py` has no contradiction detection, only exact-match dedup. Issue #11 requests auto-resolution of conflicting triples. We built the detection side.

Our ontology defines a `CONFLICTS_WITH` edge type. [`graph.py:_fetch_contradictions()`](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/vault_rag/retrieval/graph.py) queries these edges for a set of entity IDs and returns both sides with evidence and provenance. Two search strategies: targeted (check matched entities for contradiction edges) and broad (search contradiction evidence by query keywords when targeted finds nothing).

The pattern for `knowledge_graph.py`:

1. When `add_triple()` is called, check if a triple exists with the same subject and predicate but a different object
2. If so, create a `contradicts` relationship between the two objects (or flag for review)
3. When querying, include contradictions in the response with both sides and their timestamps

This gives contradiction *detection* without requiring an LLM. Resolution (deciding which claim is correct) can remain manual or use temporal heuristics (newer claim wins, unless flagged).

## AAAK for structured graph data?

Separate from the above, but worth exploring. Issue #39 found that AAAK mode regresses retrieval vs raw mode (84.2% vs 96.6%). For narrative text, the compression trades off too much semantic signal.

But entity-relationship triples have much more regular structure. Graph triples are already compressed by structure. AAAK-style encoding on top of that might achieve high compression without the retrieval regression, because the "lossy" parts of AAAK (keyword extraction, sentence truncation) don't apply to structured data. The entity codes and relationship types are already atomic. Worth testing with a round-trip eval, as #29 suggests.

---

Three concrete things: a [3D visualizer](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/multipass/index.html) that makes the palace navigable, an [eval framework](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/eval/retrieval_eval.py) that tests what palace architecture uniquely enables, and [`_fetch_contradictions()`](https://github.com/M0nkeyFl0wer/second-brain-open-kg/blob/main/vault_rag/retrieval/graph.py) as a pattern for #11. Happy to help adapt any of them.
