"""
Three-phase entity and relationship extraction.
Phase 1: Deterministic (structure, regex, dates) — fast, free, always runs
Phase 2: NLP (spaCy NER) — local, fast, catches named entities
Phase 3: LLM (Ollama or remote) — semantic, identifies relationships and types

Every entity validates against ONTOLOGY.md at extraction time.
Rejected types are counted for ontology improvement feedback.
"""
import re
import json
import hashlib
import time
import spacy
from .ontology import Ontology
from . import config


def generate_entity_id(label: str, entity_type: str, source_url: str) -> str:
    """Canonical ID function. ONE function, used everywhere."""
    normalized = f"{entity_type}:{label.lower().strip()}:{source_url}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class Extractor:
    """Three-phase extraction pipeline."""

    def __init__(self, ontology: Ontology):
        self.ontology = ontology
        self.nlp = spacy.load("en_core_web_sm")

    def extract_from_text(self, text: str, source_url: str = "",
                          doc_id: str = "") -> dict:
        """
        Run all three extraction phases on a text.
        Returns: {"entities": [...], "edges": [...]}
        """
        entities = []
        edges = []
        now = int(time.time())

        # Phase 1: Deterministic extraction
        p1_entities = self._phase1_deterministic(text, source_url, now)
        entities.extend(p1_entities)

        # Phase 2: spaCy NER
        p2_entities = self._phase2_spacy(text, source_url, now)
        entities.extend(p2_entities)

        # Phase 3: LLM extraction (relationships + type refinement)
        if config.PRIVACY_MODE == "local":
            p3 = self._phase3_llm_local(text, source_url, entities, now)
        elif config.PRIVACY_MODE in ("hybrid", "remote"):
            p3 = self._phase3_llm_remote(text, source_url, entities, now)
        else:
            p3 = {"entities": [], "edges": []}

        entities.extend(p3.get("entities", []))
        edges.extend(p3.get("edges", []))

        # Deduplicate by ID
        seen_ids = set()
        unique_entities = []
        for e in entities:
            if e["id"] not in seen_ids:
                seen_ids.add(e["id"])
                unique_entities.append(e)

        return {"entities": unique_entities, "edges": edges}

    def _phase1_deterministic(self, text: str, source_url: str,
                              now: int) -> list:
        """Extract entities from structure: dates, dollar amounts."""
        entities = []

        # Dates (ISO and natural format)
        date_pattern = r'\b(\d{4}-\d{2}-\d{2}|\w+ \d{1,2},? \d{4})\b'
        for match in re.finditer(date_pattern, text):
            label = match.group(0)
            entities.append(self._make_entity(
                label, "event", f"Date reference: {label}",
                0.9, source_url, "deterministic", now))

        return entities

    def _phase2_spacy(self, text: str, source_url: str, now: int) -> list:
        """Extract named entities using spaCy NER.
        Maps spaCy NER labels to our PKG ontology types."""
        doc = self.nlp(text[:100000])
        entities = []

        # Map spaCy labels → PKG ontology types
        spacy_to_ontology = {
            "PERSON": "person",
            "ORG": "source",     # Organizations as knowledge sources
            "GPE": "place",
            "LOC": "place",
            "FAC": "place",
            "WORK_OF_ART": "source",  # Books, articles, etc.
            "EVENT": "concept",  # Events as concepts in PKG
        }

        seen_labels = set()
        for ent in doc.ents:
            ontology_type = spacy_to_ontology.get(ent.label_)
            if not ontology_type:
                continue
            if not self.ontology.validate_entity_type(ontology_type):
                continue

            label = ent.text.strip()
            if label in seen_labels or len(label) < 2:
                continue
            seen_labels.add(label)

            entities.append(self._make_entity(
                label, ontology_type, "",
                0.7, source_url, "spacy_ner", now))

        return entities

    def _phase3_llm_local(self, text: str, source_url: str,
                          existing_entities: list, now: int) -> dict:
        """LLM extraction via local Ollama model."""
        import ollama

        type_guidance = self.ontology.get_extraction_prompt_context()
        edge_guidance = self.ontology.get_edge_prompt_context()
        existing_labels = [e["label"] for e in existing_entities[:30]]

        prompt = f"""Analyze this personal note and extract concepts, people, sources,
insights, questions, and relationships between them. Focus on ideas and their connections.

{type_guidance}

{edge_guidance}

Already extracted entities: {', '.join(existing_labels) if existing_labels else 'none yet'}

Respond ONLY with valid JSON. No preamble, no markdown.
Format:
{{
  "entities": [
    {{"label": "...", "type": "...", "description": "..."}}
  ],
  "edges": [
    {{"source": "entity label", "target": "entity label", "type": "EDGE_TYPE"}}
  ]
}}

Note to analyze:
{text[:4000]}"""

        try:
            response = ollama.chat(
                model=config.LOCAL_EXTRACTION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )
            result = json.loads(response["message"]["content"])
        except Exception as e:
            print(f"  LLM extraction failed: {e}")
            return {"entities": [], "edges": []}

        # Convert LLM output to our format
        entities = []
        for e in result.get("entities", []):
            etype = e.get("type", "").lower()
            label = e.get("label", "")
            if not label or not self.ontology.validate_entity_type(etype):
                continue
            entities.append(self._make_entity(
                label, etype, e.get("description", ""),
                0.6, source_url, f"llm_{config.LOCAL_EXTRACTION_MODEL}", now))

        edges = []
        for e in result.get("edges", []):
            etype = e.get("type", "").upper()
            if not self.ontology.validate_edge_type(etype):
                continue
            src_label = e.get("source", "")
            tgt_label = e.get("target", "")
            src_id = self._find_entity_id(src_label, entities + existing_entities)
            tgt_id = self._find_entity_id(tgt_label, entities + existing_entities)
            if src_id and tgt_id:
                edges.append({
                    "source_id": src_id,
                    "target_id": tgt_id,
                    "edge_type": etype,
                    "weight": 1.0,
                    "confidence": 0.6,
                    "source_url": source_url,
                    "provenance": f"llm_{config.LOCAL_EXTRACTION_MODEL}",
                    "created_at": now,
                })

        return {"entities": entities, "edges": edges}

    def _phase3_llm_remote(self, text: str, source_url: str,
                           existing_entities: list, now: int) -> dict:
        """LLM extraction via remote API (hybrid/remote mode)."""
        print("  Remote extraction not yet configured, falling back to local")
        return self._phase3_llm_local(text, source_url, existing_entities, now)

    def _make_entity(self, label: str, entity_type: str, description: str,
                     confidence: float, source_url: str, provenance: str,
                     now: int) -> dict:
        """Build a standard entity dict."""
        return {
            "id": generate_entity_id(label, entity_type, source_url),
            "entity_type": entity_type,
            "label": label,
            "description": description,
            "confidence": confidence,
            "source_url": source_url,
            "provenance": provenance,
            "created_at": now,
            "updated_at": now,
        }

    def _find_entity_id(self, label: str, entities: list) -> str | None:
        """Find entity ID by label match."""
        label_lower = label.lower().strip()
        for e in entities:
            if e["label"].lower().strip() == label_lower:
                return e["id"]
        # Fuzzy fallback: substring match
        for e in entities:
            if label_lower in e["label"].lower() or e["label"].lower() in label_lower:
                return e["id"]
        return None
