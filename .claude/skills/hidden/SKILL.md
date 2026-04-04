# /hidden — Hidden Connections Discovery

Find entity pairs that are semantically similar (close in embedding space) but structurally disconnected (no edges in the graph). These are ideas your brain hasn't linked yet.

## When to use

- User asks "what am I missing", "hidden connections", "surprise me"
- User wants serendipitous discovery across their knowledge
- After ingestion to find new cross-domain links

## Usage

```bash
# Find hidden connections for a specific concept
python scripts/search_cli.py -q "meditation" --mode hidden

# Programmatic: global scan
python -c "
from second_brain.graph import Graph
from second_brain.hidden_connections import find_hidden_connections
g = Graph()
for h in find_hidden_connections(g, top_n=10):
    print(f'{h[\"source_label\"]} ↔ {h[\"target_label\"]} (distance: {h[\"distance\"]:.3f})')
g.close()
"
```

## Algorithm

1. For each entity with an embedding, HNSW index finds nearest neighbors
2. Filter out entities already connected (via RELATES_TO, CONNECTS→EdgeNode→BINDS)
3. Pairs with cosine distance < 0.3 (similarity > 0.7) and zero edges = hidden connections
4. Deduplicate symmetric pairs (A↔B = B↔A)
5. Rank by distance ascending (closest = strongest hidden connection)

## Configuration

```python
# In second_brain/config.py
HIDDEN_CONNECTION_THRESHOLD = 0.7   # Minimum similarity (converted to distance internally)
HIDDEN_CONNECTION_CANDIDATES = 20   # Neighbors checked per entity
```

## Output

```
Hidden connections for: meditation

  [concept        ] neuroplasticity
                    distance: 0.187 | unlinked
  [practice       ] deep work sessions
                    distance: 0.223 | unlinked
```

## Notes

- Requires HNSW vector index (rebuilt after ingestion)
- Falls back to brute-force cosine similarity if index not available
- Also integrated into daily reflection (briefing section)
