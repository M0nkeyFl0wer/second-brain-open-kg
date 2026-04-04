# /briefing — Daily Reflection

Generate a markdown summary of what the knowledge graph knows today: new ideas, conflicting beliefs, knowledge gaps, hidden connections, surprising bridges, and underdeveloped ideas.

## When to use

- User asks for a "daily reflection", "briefing", "what's new in my graph"
- User wants a summary of their knowledge structure
- As part of a weekly or daily review routine

## Usage

```bash
python scripts/daily_briefing.py
```

## Output

Writes `reflections/YYYY-MM-DD.md` containing:

| Section | What it shows |
|---------|--------------|
| New Ideas | Entities added in last 24h, grouped by type |
| Conflicting Beliefs | CONFLICTS_WITH edges between concepts |
| Knowledge Gaps | Community pairs with low cross-connection (as questions) |
| Hidden Connections | Semantically similar but unlinked entity pairs |
| Surprising Bridges | High betweenness on low-degree entities |
| Ideas Needing Development | Entities older than 14 days with no connections |

If `VAULT_PATH` is configured, also copies to `{vault}/00-inbox/daily-reflection-YYYY-MM-DD.md` for Obsidian integration.

## Configuration

Sections are configurable in `second_brain/config.py`:

```python
BRIEFING_SECTIONS = [
    "new_ideas",
    "conflicting_beliefs",
    "knowledge_gaps",
    "hidden_connections",
    "surprising_bridges",
    "underdeveloped_ideas",
]
```

Remove a section name to exclude it.
