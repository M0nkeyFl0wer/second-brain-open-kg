# Personal Knowledge Ontology v1.0

This file defines every entity type and edge type the knowledge graph accepts.
Edit it for your thinking style. The system validates all entities against this
file at write time — types not listed here are rejected and logged.

## Entity Types

| Type | Description | Archetypical | Atypical | Exotypical (NOT this type) |
|------|-------------|-------------|----------|---------------------------|
| concept | An idea, topic, principle, or belief | "spaced repetition" | "the feeling of flow while coding" | "Anki" → tool (the app, not the concept) |
| person | An individual — author, mentor, friend, historical figure | "Richard Feynman" | "my therapist" (unnamed but referenced) | "Feynman Lectures" → source |
| source | A book, article, podcast, course, or other knowledge origin | "Thinking, Fast and Slow" | "a conversation with a friend" | "Daniel Kahneman" → person |
| project | A personal project, initiative, or ongoing effort | "learning Rust" | "decluttering the apartment" | "Rust" → concept (the language itself, not your project) |
| insight | An original thought, realization, or synthesis you had | "sleep deprivation compounds like debt" | "the shower thought about graph topology" | "sleep debt" → concept (general idea, not your insight) |
| question | An open question, uncertainty, or thing you want to explore | "why does meditation reduce anxiety?" | "what should I do about the job offer?" | "meditation" → concept |
| practice | A habit, method, routine, or technique you use | "morning journaling" | "the 2-minute rule for tasks" | "Getting Things Done" → source (the book, not your practice) |
| place | A location with personal meaning or context | "the coffee shop on Queen St" | "where I had the breakthrough idea" | "Toronto" → use only if the city itself matters, not a venue in it |

## Edge Types

| Type | From → To | Description | Signal |
|------|-----------|-------------|--------|
| LEARNED_FROM | concept/insight → source | Where you learned something | Knowledge provenance |
| INSPIRED_BY | insight → concept/person/source | What sparked an original thought | Creative lineage |
| CONFLICTS_WITH | concept → concept | Two ideas you hold that contradict | Cognitive tension, growth edge |
| SUPPORTS | concept → concept | One idea reinforces another | Belief structure |
| PART_OF | concept → concept | Hierarchy or composition | Knowledge organization |
| PRACTICED_IN | practice → project | Where you apply a method | Theory → practice link |
| ASKED_ABOUT | question → concept | What a question is investigating | Research direction |
| ANSWERS | insight/source → question | What resolves or addresses a question | Knowledge closure |
| ASSOCIATED_WITH | any → any | Unspecified relationship | **Use sparingly** — prefer a typed edge |

## Semantic Spacetime Edge-Nodes

For complex, multi-way, or annotated relationships, the graph supports
**edge-nodes** — first-class nodes that represent the relationship itself.
An edge-node connects to its participants via CONNECTS and BINDS edges.

| Edge-Node Type | Meaning | Example |
|---------------|---------|---------|
| similar_edge | Proximity, analogy — "X is like Y" | "spaced repetition" is similar to "compound interest" |
| contains_edge | Hierarchy, composition — "X contains Y" | "cognitive science" contains "memory", "attention", "learning" |
| property_edge | State, attribute — "X has property Y" | "meditation" has property "requires consistency" |
| leads_to_edge | Causality, sequence — "X leads to Y" | "sleep deprivation" leads to "impaired decision making" |

Edge-nodes support **hypergraphs** (one relationship linking 3+ entities)
and **metagraphs** (thoughts about thoughts) without schema changes.

### When to use edge-nodes vs direct edges

- **Direct edge:** Simple, binary, well-typed relationship (LEARNED_FROM, SUPPORTS, etc.)
- **Edge-node:** Relationship needs annotation, connects 3+ things, or represents
  a thought about a relationship itself

## Extending This Ontology

- Only add a type when you've seen 3+ instances that don't fit existing types
- Every edge type should have a clear purpose for *your* thinking
- Check `validate_ontology.py` after editing to verify syntax
- The rejection log after ingestion tells you what types your notes need
