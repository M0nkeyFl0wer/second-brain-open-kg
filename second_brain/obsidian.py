"""
Obsidian vault reader. Parses markdown notes, extracts wikilinks,
frontmatter, and tags. Prepares notes for the extraction pipeline.
"""
import re
import hashlib
from pathlib import Path
from . import config


def scan_vault(vault_path: str = "") -> list[dict]:
    """
    Recursively read all markdown files from an Obsidian vault.
    Skips ignored directories (.obsidian, .trash, templates, etc.).
    Returns list of note dicts ready for extraction.
    """
    vault = Path(vault_path or config.VAULT_PATH).expanduser()
    if not vault.exists():
        raise FileNotFoundError(f"Vault not found: {vault}")

    notes = []
    for md_file in sorted(vault.rglob("*.md")):
        # Skip ignored directories
        if any(part in config.VAULT_IGNORE_DIRS
               for part in md_file.relative_to(vault).parts):
            continue

        text = md_file.read_text(errors="replace")
        frontmatter, body = parse_frontmatter(text)

        doc_id = hashlib.sha256(
            str(md_file.relative_to(vault)).encode()
        ).hexdigest()[:16]

        notes.append({
            "doc_id": doc_id,
            "path": str(md_file),
            "relative_path": str(md_file.relative_to(vault)),
            "title": frontmatter.get("title", md_file.stem),
            "body": body,
            "full_text": text,
            "frontmatter": frontmatter,
            "tags": extract_tags(text, frontmatter),
            "wikilinks": extract_wikilinks(body),
        })

    return notes


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Split YAML frontmatter from body.
    Returns (frontmatter_dict, body_text).
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    yaml_block = text[3:end].strip()
    body = text[end + 3:].strip()

    # Simple YAML parser (no PyYAML dependency)
    frontmatter = {}
    for line in yaml_block.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip().strip('"').strip("'")
            if value.startswith("[") and value.endswith("]"):
                # Simple list parsing: [tag1, tag2]
                value = [v.strip().strip('"').strip("'")
                         for v in value[1:-1].split(",") if v.strip()]
            frontmatter[key] = value

    return frontmatter, body


def extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilinks]] from text. Returns list of linked note names."""
    # Match [[link]] and [[link|display text]]
    pattern = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
    return list(set(re.findall(pattern, text)))


def extract_tags(text: str, frontmatter: dict) -> list[str]:
    """Extract #tags from text and tags from frontmatter."""
    tags = set()

    # Frontmatter tags
    fm_tags = frontmatter.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.split(",")]
    if isinstance(fm_tags, list):
        tags.update(t.strip().lstrip("#") for t in fm_tags if t.strip())

    # Inline #tags (not inside code blocks or URLs)
    inline = re.findall(r'(?<!\S)#([a-zA-Z][a-zA-Z0-9_/-]*)', text)
    tags.update(inline)

    return sorted(tags)


def chunk_text(text: str, chunk_size: int = 1000,
               overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for embedding."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
