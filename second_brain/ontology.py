"""
Ontology for open-second-brain — triplet-first entity/edge types.

Entity types:
    concept      — ideas, topics, principles
    person       — authors, mentors, references
    source       — books, articles, podcasts, courses
    project      — personal projects, initiatives
    insight      — original thoughts, realizations
    question     — open questions, uncertainties
    practice     — habits, methods, routines
    place        — locations with meaning
    method       — techniques, approaches
    tool         — software, apps, resources

Edge types (triplets with evidence):
    LEARNED_FROM    — concept ← source (provenance)
    INSPIRED_BY     — insight ← concept/person (creative lineage)
    CONFLICTS_WITH  — concept ← concept (belief contradictions)
    SUPPORTS        — concept ← concept (reinforcement)
    PART_OF         — concept ← concept (hierarchy)
    PRACTICED_IN    — practice ← project (application)
    ASKED_ABOUT     — question ← concept (investigation direction)
    ANSWERS         — insight/source ← question (closure)
    IMPLEMENTS      — tool ← concept (tool-concept link)
    REQUIRES        — tool/concept ← tool/concept (dependencies)

Evidence requirement: every edge MUST have an evidence quote (verbatim).
Confidence scoring: 0.9 deterministic / 0.7 NLP / 0.5 LLM
"""

import re
from typing import Optional

NODE_TYPES = frozenset([
    "concept",
    "person",
    "source",
    "project",
    "insight",
    "question",
    "practice",
    "place",
    "method",
    "tool",
])

EDGE_TYPES = frozenset([
    "LEARNED_FROM",
    "INSPIRED_BY",
    "CONFLICTS_WITH",
    "SUPPORTS",
    "PART_OF",
    "PRACTICED_IN",
    "ASKED_ABOUT",
    "ANSWERS",
    "IMPLEMENTS",
    "REQUIRES",
])

EDGE_DOMAIN_RANGE = {
    "LEARNED_FROM":    (NODE_TYPES, NODE_TYPES),
    "INSPIRED_BY":     (NODE_TYPES, NODE_TYPES),
    "CONFLICTS_WITH":  (NODE_TYPES, NODE_TYPES),
    "SUPPORTS":        (NODE_TYPES, NODE_TYPES),
    "PART_OF":         (NODE_TYPES, NODE_TYPES),
    "PRACTICED_IN":    ({"practice", "method", "tool"}, NODE_TYPES),
    "ASKED_ABOUT":     ({"question"}, NODE_TYPES),
    "ANSWERS":         (NODE_TYPES, {"question"}),
    "IMPLEMENTS":      ({"tool", "method"}, NODE_TYPES),
    "REQUIRES":        (NODE_TYPES, NODE_TYPES),
}

TYPE_ALIASES = {
    "concept": "concept",
    "concepts": "concept",
    "idea": "concept",
    "topic": "concept",
    "person": "person",
    "people": "person",
    "author": "person",
    "source": "source",
    "book": "source",
    "article": "source",
    "podcast": "source",
    "course": "source",
    "project": "project",
    "projects": "project",
    "insight": "insight",
    "idea_original": "insight",
    "question": "question",
    "questions": "question",
    "practice": "practice",
    "method": "practice",
    "habit": "practice",
    "place": "place",
    "location": "place",
    "method": "method",
    "technique": "method",
    "tool": "tool",
    "software": "tool",
    "app": "tool",
}


def normalize_node_type(raw: str) -> Optional[str]:
    """
    Normalize a raw type string to a canonical node type.

    Handles:
    - Aliases (e.g., "idea" → "concept", "people" → "person")
    - Whitespace stripping
    - Lowercasing

    Returns None if the type is not recognized.
    """
    if not raw:
        return None
    cleaned = raw.strip().lower()
    return TYPE_ALIASES.get(cleaned, cleaned) if cleaned in TYPE_ALIASES else None


def validate_edge(
    edge_type: str,
    source_type: str,
    target_type: str,
) -> tuple[bool, Optional[str]]:
    """
    Validate an edge against domain/range constraints.

    Returns:
        (is_valid, error_message)

    Example:
        validate_edge("PRACTICED_IN", "practice", "project")
        # (True, None)
    """
    if edge_type not in EDGE_TYPES:
        return False, f"Unknown edge type: {edge_type}"

    if source_type not in NODE_TYPES:
        return False, f"Unknown source type: {source_type}"

    if target_type not in NODE_TYPES:
        return False, f"Unknown target type: {target_type}"

    domain, range_ = EDGE_DOMAIN_RANGE.get(edge_type, (NODE_TYPES, NODE_TYPES))

    if source_type not in domain:
        return False, f"{edge_type} source must be one of {domain}, got {source_type}"

    if target_type not in range_:
        return False, f"{edge_type} target must be one of {range_}, got {target_type}"

    return True, None


def slugify(label: str) -> str:
    """
    Convert an entity label to a stable ID slug.

    Examples:
        "Thinking in Systems" → "thinking_in_systems"
        "Sam Harris" → "sam_harris"
        "My note on AGI" → "my_note_on_agi"
    """
    if not label:
        return "unknown"
    slug = label.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = re.sub(r'_+', '_', slug)
    slug = slug.strip('_')
    return slug[:128]


def extraction_prompt_fragment() -> str:
    """
    Return the edge type section for LLM extraction prompts.

    Include this verbatim in any triplet extraction prompt.
    """
    edge_lines = []
    for etype in sorted(EDGE_TYPES):
        domain, range_ = EDGE_DOMAIN_RANGE.get(etype, (NODE_TYPES, NODE_TYPES))
        edge_lines.append(f"    - {etype} (source: {domain} → target: {range_})")

    return "\n".join([
        "Edge types (all require verbatim evidence quote):",
        *edge_lines,
        "",
        "Rules:",
        "  - Every edge MUST have evidence (exact quote from text, min 10 chars)",
        "  - Confidence: 0.9 deterministic / 0.7 NLP / 0.5 LLM",
        "  - Use exact entity labels from text, don't invent names",
        "  - Extract CONFLICTS_WITH and SUPPORTS when beliefs contrast/reinforce",
    ])


def node_type_prompt_fragment() -> str:
    """
    Return the node type section for LLM extraction prompts.
    """
    examples = {
        "concept": "feedback loops, emergent behavior, twin earth",
        "person": "Donella Meadows, Judea Pearl, Ted Nelson",
        "source": "Thinking in Systems, The Book of Why, Auguments of Creation",
        "project": "newsletter production, knowledge graph, research",
        "insight": "patterns seen in multiple domains, original realizations",
        "question": "open investigative threads, unresolved problems",
        "practice": "time-blocking, weekly review, Zettelkasten",
        "method": "causal inference, counterfactual reasoning",
        "tool": "Obsidian, DuckDB, Claude Code",
        "place": "home office, local library, favorite cafe",
    }

    lines = ["Node types:"]
    for ntype in sorted(NODE_TYPES):
        ex = examples.get(ntype, "")
        lines.append(f"  - {ntype}: {ex}" if ex else f"  - {ntype}")
    return "\n".join(lines)