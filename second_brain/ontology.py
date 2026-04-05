"""
Parse and validate against ONTOLOGY.md.
The ontology is the law — nothing enters the graph without matching a declared type.
"""
import re
from pathlib import Path
from dataclasses import dataclass


@dataclass
class EntityType:
    name: str
    description: str
    archetypical: str = ""
    atypical: str = ""
    exotypical: str = ""


@dataclass
class EdgeType:
    name: str
    from_type: str
    to_type: str
    description: str
    investigative_signal: str = ""


class Ontology:
    """Parsed ontology from ONTOLOGY.md with validation."""

    def __init__(self, ontology_path: str = None):
        if ontology_path is None:
            ontology_path = str(Path(__file__).resolve().parent.parent / "ONTOLOGY.md")
        self.path = Path(ontology_path)
        self.entity_types: dict[str, EntityType] = {}
        self.edge_types: dict[str, EdgeType] = {}
        self._rejection_counts: dict[str, int] = {}
        self._parse()

    def _parse(self):
        """Parse markdown tables from ONTOLOGY.md."""
        if not self.path.exists():
            raise FileNotFoundError(f"Ontology file not found: {self.path}")

        text = self.path.read_text()
        current_section = None

        for line in text.split("\n"):
            if "## Entity Types" in line:
                current_section = "entities"
                continue
            elif "## Edge Types" in line:
                current_section = "edges"
                continue
            elif line.startswith("## "):
                current_section = None
                continue

            if not line.startswith("|") or line.startswith("|---") or line.startswith("| Type"):
                continue

            cells = [c.strip() for c in line.split("|")[1:-1]]

            if current_section == "entities" and len(cells) >= 2:
                name = cells[0].lower().strip()
                desc = cells[1].strip()
                et = EntityType(
                    name=name,
                    description=desc,
                    archetypical=cells[2] if len(cells) > 2 else "",
                    atypical=cells[3] if len(cells) > 3 else "",
                    exotypical=cells[4] if len(cells) > 4 else "",
                )
                self.entity_types[name] = et

            elif current_section == "edges" and len(cells) >= 3:
                name = cells[0].upper().strip()
                from_to = cells[1].strip()
                desc = cells[2].strip()
                signal = cells[3] if len(cells) > 3 else ""

                # Parse "person → organization" format
                parts = re.split(r"\s*(?:→|->|→)+\s*", from_to)
                from_type = parts[0].lower() if parts else ""
                to_type = parts[1].lower() if len(parts) > 1 else ""

                self.edge_types[name] = EdgeType(
                    name=name,
                    from_type=from_type,
                    to_type=to_type,
                    description=desc,
                    investigative_signal=signal,
                )

    def validate_entity_type(self, entity_type: str) -> bool:
        """Check if an entity type is declared in the ontology."""
        normalized = entity_type.lower().strip()
        if normalized in self.entity_types:
            return True
        # Track rejections
        self._rejection_counts[normalized] = self._rejection_counts.get(normalized, 0) + 1
        return False

    def validate_edge_type(self, edge_type: str) -> bool:
        """Check if an edge type is declared in the ontology."""
        return edge_type.upper().strip() in self.edge_types

    def get_rejection_counts(self) -> dict[str, int]:
        """Return counts of rejected entity types — signals for ontology expansion."""
        return dict(sorted(self._rejection_counts.items(), key=lambda x: -x[1]))

    def get_extraction_prompt_context(self) -> str:
        """Generate type guidance for LLM extraction prompts."""
        lines = ["Classify entities using ONLY these types:\n"]
        for name, et in self.entity_types.items():
            line = f"- **{name}**: {et.description}"
            if et.exotypical:
                line += f"\n  NOT this type: {et.exotypical}"
            lines.append(line)
        lines.append("\nIf an entity doesn't clearly fit any type, skip it. Do NOT invent types.")
        return "\n".join(lines)

    def get_edge_prompt_context(self) -> str:
        """Generate edge type guidance for LLM extraction prompts."""
        lines = ["Use ONLY these relationship types:\n"]
        for name, edge in self.edge_types.items():
            lines.append(f"- **{name}** ({edge.from_type} → {edge.to_type}): {edge.description}")
        lines.append("\nPrefer specific types. Use ASSOCIATED_WITH only as last resort.")
        return "\n".join(lines)

    @property
    def entity_type_names(self) -> list[str]:
        return list(self.entity_types.keys())

    @property
    def edge_type_names(self) -> list[str]:
        return list(self.edge_types.keys())

    def __repr__(self):
        return f"Ontology({len(self.entity_types)} entity types, {len(self.edge_types)} edge types)"
