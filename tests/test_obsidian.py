"""
Unit tests for the Obsidian vault parser.

Tests cover:
  - YAML frontmatter parsing (present and absent)
  - Wikilink extraction (plain and aliased)
  - Tag extraction (inline and frontmatter)
  - Text chunking with overlap
"""
import pytest

from second_brain.obsidian import (
    parse_frontmatter,
    extract_wikilinks,
    extract_tags,
    chunk_text,
)


class TestFrontmatterParsing:
    """Test YAML frontmatter extraction from markdown text."""

    def test_parse_frontmatter(self):
        """Valid frontmatter should extract title and tags."""
        text = """---
title: My Test Note
tags: [philosophy, epistemology]
---
This is the body of the note.
"""
        fm, body = parse_frontmatter(text)
        assert fm["title"] == "My Test Note"
        assert isinstance(fm["tags"], list)
        assert "philosophy" in fm["tags"]
        assert "epistemology" in fm["tags"]
        assert "This is the body" in body

    def test_parse_frontmatter_missing(self):
        """Text without frontmatter should return empty dict and full body."""
        text = "Just some plain text without frontmatter."
        fm, body = parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_parse_frontmatter_no_closing_delimiter(self):
        """Frontmatter without closing '---' should return empty dict."""
        text = "---\ntitle: Broken\nNo closing delimiter here."
        fm, body = parse_frontmatter(text)
        assert fm == {}

    def test_parse_frontmatter_string_value(self):
        """Simple key: value pairs should be parsed as strings."""
        text = """---
title: Test
author: Jane Doe
---
Body."""
        fm, body = parse_frontmatter(text)
        assert fm["title"] == "Test"
        assert fm["author"] == "Jane Doe"


class TestWikilinkExtraction:
    """Test [[wikilink]] parsing."""

    def test_extract_wikilinks(self):
        """Plain wikilinks should be extracted."""
        text = "I learned about [[spaced repetition]] from [[Make It Stick]]."
        links = extract_wikilinks(text)
        assert "spaced repetition" in links
        assert "Make It Stick" in links

    def test_extract_wikilinks_with_alias(self):
        """Aliased wikilinks [[link|display]] should return the link part."""
        text = "See [[spaced repetition|SR]] for details."
        links = extract_wikilinks(text)
        assert "spaced repetition" in links
        # The alias 'SR' should NOT appear as a separate link
        assert "SR" not in links

    def test_extract_wikilinks_deduplication(self):
        """Duplicate wikilinks should be deduplicated."""
        text = "[[concept]] and [[concept]] again."
        links = extract_wikilinks(text)
        assert links.count("concept") == 1

    def test_extract_wikilinks_empty(self):
        """Text without wikilinks should return empty list."""
        text = "No links here at all."
        links = extract_wikilinks(text)
        assert links == []


class TestTagExtraction:
    """Test #tag extraction from text and frontmatter."""

    def test_extract_tags_inline(self):
        """Inline #tags should be extracted from body text."""
        text = "This note is about #philosophy and #epistemology."
        tags = extract_tags(text, {})
        assert "philosophy" in tags
        assert "epistemology" in tags

    def test_extract_tags_frontmatter(self):
        """Tags from YAML frontmatter should be included."""
        fm = {"tags": ["science", "learning"]}
        tags = extract_tags("", fm)
        assert "science" in tags
        assert "learning" in tags

    def test_extract_tags_both_sources(self):
        """Tags from both inline and frontmatter should be combined."""
        text = "Discussing #memory in this note."
        fm = {"tags": ["neuroscience"]}
        tags = extract_tags(text, fm)
        assert "memory" in tags
        assert "neuroscience" in tags

    def test_extract_tags_frontmatter_string(self):
        """Frontmatter tags as comma-separated string should be split."""
        fm = {"tags": "alpha, beta, gamma"}
        tags = extract_tags("", fm)
        assert "alpha" in tags
        assert "beta" in tags
        assert "gamma" in tags

    def test_extract_tags_hash_prefix_stripped(self):
        """Tags should not retain the '#' prefix."""
        text = "Working on #deep-work strategies."
        tags = extract_tags(text, {})
        # Tag names should not start with '#'
        for tag in tags:
            assert not tag.startswith("#")

    def test_extract_tags_sorted(self):
        """Returned tags should be sorted alphabetically."""
        text = "#zebra #alpha #middle"
        tags = extract_tags(text, {})
        assert tags == sorted(tags)


class TestTextChunking:
    """Test text splitting into overlapping chunks."""

    def test_chunk_text_basic(self):
        """A 2500-char text with chunk_size=1000, overlap=200 should yield 4 chunks.
        Step = 1000 - 200 = 800. Starts: 0, 800, 1600, 2400."""
        text = "x" * 2500
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(chunks) == 4

    def test_chunk_text_overlap(self):
        """Consecutive chunks should share overlap characters."""
        text = "A" * 500 + "B" * 500 + "C" * 500
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(chunks) >= 2
        # The end of chunk 0 and start of chunk 1 should overlap
        end_of_first = chunks[0][-200:]
        start_of_second = chunks[1][:200]
        assert end_of_first == start_of_second

    def test_chunk_text_short_text(self):
        """Text shorter than chunk_size should yield exactly 1 chunk."""
        text = "Short text."
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_empty(self):
        """Empty text should yield no chunks."""
        chunks = chunk_text("", chunk_size=1000, overlap=200)
        assert chunks == []

    def test_chunk_text_whitespace_only(self):
        """Whitespace-only text should yield no chunks."""
        chunks = chunk_text("   \n\t  ", chunk_size=1000, overlap=200)
        assert chunks == []
