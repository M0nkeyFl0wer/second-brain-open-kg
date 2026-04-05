"""
Unit tests for the Ontology parser and validator.

Tests cover:
  - Parsing entity types and edge types from ONTOLOGY.md
  - Type validation (accept/reject)
  - Rejection counting for ontology improvement feedback
  - Extraction prompt generation
  - Boundary examples (exotypical column)
"""
import pytest


class TestOntologyParsing:
    """Verify that ONTOLOGY.md is parsed correctly."""

    def test_parse_entity_types(self, ontology):
        """ONTOLOGY.md declares 8 entity types: concept, person, source,
        project, insight, question, practice, place."""
        expected = {
            "concept", "person", "source", "project",
            "insight", "question", "practice", "place",
        }
        assert set(ontology.entity_type_names) == expected

    def test_parse_edge_types(self, ontology):
        """ONTOLOGY.md declares 9 edge types."""
        expected = {
            "LEARNED_FROM", "INSPIRED_BY", "CONFLICTS_WITH", "SUPPORTS",
            "PART_OF", "PRACTICED_IN", "ASKED_ABOUT", "ANSWERS",
            "ASSOCIATED_WITH",
        }
        assert set(ontology.edge_type_names) == expected

    def test_entity_type_has_description(self, ontology):
        """Each entity type should have a non-empty description."""
        for name, et in ontology.entity_types.items():
            assert et.description, f"Entity type '{name}' has empty description"

    def test_edge_type_has_from_to(self, ontology):
        """Each edge type should have from_type and to_type parsed."""
        for name, edge in ontology.edge_types.items():
            # ASSOCIATED_WITH has 'any' as from/to, still parsed as non-empty
            assert edge.from_type, f"Edge '{name}' missing from_type"
            assert edge.to_type, f"Edge '{name}' missing to_type"


class TestOntologyValidation:
    """Verify entity and edge type validation."""

    def test_validate_entity_type_valid(self, ontology):
        """'concept' is a declared type and should be accepted."""
        assert ontology.validate_entity_type("concept") is True

    def test_validate_entity_type_case_insensitive(self, ontology):
        """Validation should be case-insensitive."""
        assert ontology.validate_entity_type("CONCEPT") is True
        assert ontology.validate_entity_type("Person") is True

    def test_validate_entity_type_invalid(self, ontology):
        """'weapon' is not a declared type and should be rejected."""
        assert ontology.validate_entity_type("weapon") is False

    def test_validate_edge_type_valid(self, ontology):
        """'SUPPORTS' is a declared edge type."""
        assert ontology.validate_edge_type("SUPPORTS") is True

    def test_validate_edge_type_invalid(self, ontology):
        """'DESTROYS' is not a declared edge type."""
        assert ontology.validate_edge_type("DESTROYS") is False

    def test_validate_edge_type_case_insensitive(self, ontology):
        """Edge validation normalizes to uppercase."""
        assert ontology.validate_edge_type("supports") is True


class TestRejectionCounting:
    """Verify rejection counts track invalid types for ontology feedback."""

    def test_rejection_counts_increment(self, ontology):
        """Rejecting the same invalid type multiple times increments the count."""
        ontology.validate_entity_type("weapon")
        ontology.validate_entity_type("weapon")
        ontology.validate_entity_type("weapon")
        counts = ontology.get_rejection_counts()
        assert counts["weapon"] == 3

    def test_rejection_counts_multiple_types(self, ontology):
        """Different invalid types are tracked separately."""
        ontology.validate_entity_type("weapon")
        ontology.validate_entity_type("food")
        ontology.validate_entity_type("weapon")
        counts = ontology.get_rejection_counts()
        assert counts["weapon"] == 2
        assert counts["food"] == 1

    def test_valid_type_not_in_rejections(self, ontology):
        """Valid types should not appear in rejection counts."""
        ontology.validate_entity_type("concept")
        counts = ontology.get_rejection_counts()
        assert "concept" not in counts


class TestPromptGeneration:
    """Verify LLM prompt context generation."""

    def test_extraction_prompt_context_includes_all_types(self, ontology):
        """The extraction prompt should mention every entity type."""
        prompt = ontology.get_extraction_prompt_context()
        for name in ontology.entity_type_names:
            assert name in prompt, f"Type '{name}' not in extraction prompt"

    def test_extraction_prompt_has_boundary_instruction(self, ontology):
        """The prompt should tell the LLM not to invent types."""
        prompt = ontology.get_extraction_prompt_context()
        assert "Do NOT invent types" in prompt

    def test_edge_prompt_context_includes_all_edges(self, ontology):
        """The edge prompt should mention every edge type."""
        prompt = ontology.get_edge_prompt_context()
        for name in ontology.edge_type_names:
            assert name in prompt, f"Edge type '{name}' not in edge prompt"

    def test_exotypical_examples_present(self, ontology):
        """Entity types with exotypical examples should have them parsed."""
        # 'concept' has exotypical: '"Anki" -> tool (the app, not the concept)'
        concept = ontology.entity_types["concept"]
        assert concept.exotypical, "concept should have exotypical boundary example"
        # The exotypical should appear in the prompt as a "NOT this type" hint
        prompt = ontology.get_extraction_prompt_context()
        assert "NOT this type" in prompt
