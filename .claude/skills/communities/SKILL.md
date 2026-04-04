# /communities — Community Summaries (Zoom Out)

Pre-compute community summaries using LadybugDB's native Louvain algorithm. Stores summaries as CommunityMeta nodes with embeddings for "zoom out" queries — answering broad questions with themes instead of individual entities.

## When to use

- User asks "what are the themes in my graph", "zoom out", "big picture"
- After significant ingestion to recompute community structure
- When the MCP `memory_zoom_out` tool needs fresh data

## Usage

```bash
# Compute community summaries
python -c "
from second_brain.graph import Graph
from second_brain.community_summaries import compute_community_summaries
g = Graph()
communities = compute_community_summaries(g)
for c in communities:
    print(f'Community {c[\"community_id\"]}: {c[\"size\"]} members — {c[\"summary\"][:80]}')
g.close()
"

# Search communities by topic
python -c "
from second_brain.graph import Graph
from second_brain.embed import embed_text
from second_brain.community_summaries import search_communities
g = Graph()
results = search_communities(g, embed_text('learning and memory'))
for r in results:
    print(f'Community {r[\"community_id\"]}: {r[\"summary\"][:100]}')
g.close()
"
```

## Algorithm

1. Project Entity/RELATES_TO subgraph via LadybugDB algo extension
2. Run native Louvain community detection
3. For each community >= `MIN_COMMUNITY_SIZE` (default 3):
   - Get top-5 entities by degree
   - Concatenate labels + descriptions into summary
   - Embed summary via Ollama
   - Store as CommunityMeta node
4. Rebuild HNSW vector index on CommunityMeta

## Output

CommunityMeta nodes in the graph with:
- `community_id`, `size`, `summary`, `top_entities`, `computed_at`, `embedding[768]`

Searchable via vector similarity for "zoom out" queries.

## Notes

- Requires LadybugDB algo extension (loaded automatically)
- Summaries are recomputed from scratch each run (not incremental)
- HNSW index rebuilt after all summaries are embedded
- Used by MCP `memory_zoom_out` tool for AI assistant integration
