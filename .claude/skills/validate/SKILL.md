# /validate — Ontology Health Check

Check ONTOLOGY.md syntax and measure how well the ontology matches reality in the graph. Reports ICR (type coverage), CI (class imbalance), IPR (edge coverage), and type distribution.

## When to use

- User asks "is my ontology healthy", "what types are unused"
- After editing ONTOLOGY.md to verify changes
- After ingestion to check if new types are needed (rejection signals)
- User asks about class imbalance or dominant types

## Usage

```bash
python scripts/validate_ontology.py
```

## Output

```
Ontology: Ontology(8 entity types, 9 edge types)
  Entity types: concept, person, source, project, insight, question, practice, place
  Edge types: LEARNED_FROM, INSPIRED_BY, CONFLICTS_WITH, SUPPORTS, ...

Graph: 1,847 entities, 423 edges, 247 documents

  ICR (type coverage): 0.88 — healthy
  CI (class imbalance): 0.28 — healthy
  IPR (edge coverage): 0.67 — warning

  Type distribution:
    concept            612 ( 33.1%) ████████████████
    source             389 ( 21.1%) ██████████
    person             287 ( 15.5%) ███████
    ...

  Unpopulated types: practice
  Unpopulated edges: ANSWERS, PRACTICED_IN
```

## Metrics

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| ICR (Instantiated Class Ratio) | > 0.8 | 0.5–0.8 | < 0.5 |
| CI (Class Imbalance) | < 0.3 | 0.3–0.5 | > 0.5 |
| IPR (Instantiated Property Ratio) | > 0.8 | 0.5–0.8 | < 0.5 |

## Notes

- High CI means one type is catching everything — add better exotypical examples
- Unpopulated types may be dead schema — remove or wait for more data
- Run after ingestion to see rejection counts (signals for ontology expansion)
