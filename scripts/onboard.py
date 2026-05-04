"""
Interactive onboarding for open-second-brain.

Scans the user's vault or content directory, suggests edge types based on
detected patterns, and writes the initial config.

Run: python scripts/onboard.py

Supports:
- Obsidian vault (--vault path)
- Any directory of documents (--dir path)
- Fresh start with no content (interactive discovery)
"""

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from second_brain.ontology import EDGE_TYPES, NODE_TYPES

CONFIG_PATH = Path(__file__).parent.parent / "config" / "edge_types.json"

EDGE_DESCRIPTIONS = {
    "LEARNED_FROM": "You read/heard something and learned a concept from it (book, article, course, person)",
    "INSPIRED_BY": "A concept or person sparked an original insight or idea",
    "CONFLICTS_WITH": "Two beliefs or concepts contradict each other in your thinking",
    "SUPPORTS": "One concept reinforces or corroborates another",
    "PART_OF": "A concept is a component or sub-topic of a larger concept",
    "PRACTICED_IN": "A habit, method, or practice is applied in a project or area",
    "ASKED_ABOUT": "A question is investigating or exploring a concept",
    "ANSWERS": "A concept or insight resolves or closes a question",
    "IMPLEMENTS": "A tool or method implements or embodies a concept",
    "REQUIRES": "One concept or tool depends on or requires another",
}

EDGE_EXAMPLES = {
    "LEARNED_FROM": '"feedback loops" learned from "Thinking in Systems"',
    "INSPIRED_BY": '"emergent behavior" inspired insight about city planning',
    "CONFLICTS_WITH": '"free will exists" conflicts with "determinism is true"',
    "SUPPORTS": '"time-blocking" supports "deep work practice"',
    "PART_OF": '"attention" part of "cognitive science"',
    "PRACTICED_IN": '"Zettelkasten" practiced in "research workflow"',
    "ASKED_ABOUT": '"how does memory work?" asked about "spaced repetition"',
    "ANSWERS": '"distributed practice" answers "how to remember things"',
    "IMPLEMENTS": '"Obsidian dataview" implements "query-based views"',
    "REQUIRES": '"HNSW index" requires "vector embedding"',
}

DEFAULT_EDGE_TYPES = ["LEARNED_FROM", "INSPIRED_BY", "PRACTICED_IN", "CONFLICTS_WITH", "IMPLEMENTS"]


def scan_directory(path: Path) -> dict[str, int]:
    """Scan a directory for content patterns to suggest edge types."""
    patterns = {
        "LEARNED_FROM": 0,
        "INSPIRED_BY": 0,
        "CONFLICTS_WITH": 0,
        "PRACTICED_IN": 0,
        "IMPLEMENTS": 0,
    }

    keywords = {
        "LEARNED_FROM": ["read", "book", "article", "course", "learned from", "studied", "course", "paper", "podcast", "video", "talk"],
        "INSPIRED_BY": ["inspired by", "reminds me of", "this makes me think", "spark", "idea from", "originated from"],
        "CONFLICTS_WITH": ["conflicts with", "contradicts", "opposite of", "disagrees", "vs", "versus", " tension"],
        "PRACTICED_IN": ["i use", "i practice", "i apply", "in my workflow", "in my project", "implemented in"],
        "IMPLEMENTS": ["implements", "tool for", "software for", "app for", "plugin", "extension"],
    }

    for md_file in path.rglob("*.md"):
        try:
            content = md_file.read_text().lower()
            for edge_type, words in keywords.items():
                for word in words:
                    patterns[edge_type] += content.count(word)
        except Exception:
            continue

    return {k: v for k, v in patterns.items() if v > 0}


def prompt_yes_no(question: str) -> bool:
    """Ask a yes/no question and return the answer."""
    while True:
        answer = input(f"  {question} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        elif answer in ("n", "no"):
            return False
        print("  Please enter 'y' or 'n'")


def prompt_multi_select(options: list[str], descriptions: dict[str, str], defaults: list[str], max_select: int = 10) -> list[str]:
    """Prompt user to select multiple options from a list."""
    print("\n  Available options (press number to toggle, Enter to confirm):\n")
    selected = set(defaults)

    while True:
        for i, opt in enumerate(options, 1):
            marker = "[X]" if opt in selected else "[ ]"
            desc = descriptions.get(opt, "")[:50]
            print(f"    {i}. {marker} {opt:20s} — {desc}")

        print(f"\n  Selected: {sorted(selected)}")
        print("  Press number to toggle, Enter to confirm, 'q' to quit without changes")

        try:
            answer = input("  > ").strip().lower()
            if answer == "q":
                return list(defaults)
            if answer == "":
                return sorted(list(selected))
            idx = int(answer) - 1
            if 0 <= idx < len(options):
                opt = options[idx]
                if opt in selected:
                    selected.remove(opt)
                else:
                    selected.add(opt)
        except ValueError:
            continue


def interactive_node_type_selection() -> list[str]:
    """Ask user which entity types they care about."""
    print("\n  What types of knowledge do you track? (press number to toggle)")
    print("  Leave at default if unsure — you can change later in config/edge_types.json\n")

    all_types = sorted(NODE_TYPES)
    defaults = ["concept", "person", "source", "insight", "question", "practice"]

    selected = set(defaults)
    while True:
        for i, ntype in enumerate(all_types, 1):
            marker = "[X]" if ntype in selected else "[ ]"
            print(f"    {i}. {marker} {ntype}")
        print(f"\n  Selected: {sorted(selected)}")
        print("  Press number to toggle, Enter to confirm, 'q' to quit without changes")
        try:
            answer = input("  > ").strip().lower()
            if answer == "q":
                return list(defaults)
            if answer == "":
                return sorted(list(selected))
            idx = int(answer) - 1
            if 0 <= idx < len(all_types):
                ntype = all_types[idx]
                if ntype in selected:
                    selected.remove(ntype)
                else:
                    selected.add(ntype)
        except ValueError:
            continue


def detect_content_type() -> tuple[Optional[Path], str]:
    """Detect whether user has an Obsidian vault or generic directory."""
    print("=" * 60)
    print(" open-second-brain Setup")
    print("=" * 60)

    print("\n[1] Check for Obsidian vault")
    obsidian_default = Path.home() / "obsidian-vault"
    if obsidian_default.exists():
        if prompt_yes_no("Found Obsidian vault at ~/obsidian-vault — use it?"):
            return obsidian_default, "obsidian"

    print("\n[2] Enter path to your content")
    custom = input("  Path to vault or folder (or press Enter to skip): ").strip()
    if custom:
        path = Path(custom).expanduser()
        if path.exists():
            if (path / "obsidian.json").exists() or (path / ".obsidian").exists():
                return path, "obsidian"
            return path, "generic"
        print(f"  Path not found: {path}")

    print("\n[3] Starting from scratch")
    if prompt_yes_no("No content detected — start fresh and we'll build from there?"):
        return None, "empty"

    return None, "empty"


def run_onboarding(vault_path: Optional[Path], content_type: str) -> None:
    """Run the full onboarding flow."""
    print("\n" + "=" * 60)
    print(" Detecting content patterns...")
    print("=" * 60)

    pattern_counts = {}
    if vault_path and vault_path.exists():
        pattern_counts = scan_directory(vault_path)

    if pattern_counts:
        print("\n  Detected patterns in your content:")
        for edge_type, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    - {edge_type}: {count} potential edges")
        print()

    print("=" * 60)
    print(" Edge Type Selection")
    print("=" * 60)
    print("\n  Which relationships do you want to track?")
    print("  Default options (recommended): LEARNED_FROM, INSPIRED_BY, PRACTICED_IN, CONFLICTS_WITH, IMPLEMENTS\n")

    edge_type_list = sorted(EDGE_TYPES)
    suggested_defaults = [et for et in DEFAULT_EDGE_TYPES if et in EDGE_TYPES]

    print("  Example: ", end="")
    if "LEARNED_FROM" in edge_type_list:
        print(EDGE_EXAMPLES["LEARNED_FROM"])

    selected_edges = prompt_multi_select(edge_type_list, EDGE_DESCRIPTIONS, suggested_defaults)

    print("\n" + "=" * 60)
    print(" Entity Type Selection")
    print("=" * 60)

    selected_nodes = interactive_node_type_selection()

    print("\n" + "=" * 60)
    print(" Summary")
    print("=" * 60)
    print(f"\n  Entity types: {', '.join(selected_nodes)}")
    print(f"  Edge types:   {', '.join(selected_edges)}")
    print(f"  Vault path:   {vault_path or '(none — fresh start)'}")

    if not prompt_yes_no("\nWrite this configuration?"):
        print("\n  Cancelled — no changes written.")
        return

    config = {
        "version": 1,
        "edge_types": selected_edges,
        "entity_types": selected_nodes,
        "embedding_model": "nomic-embed-text",
        "embedding_dim": 768,
        "hnsw_ef_construction": 200,
        "hnsw_M": 32,
        "rrf_k": 60,
        "chunk_size_chars": 500,
        "onboard_completed": True,
        "vault_path": str(vault_path) if vault_path else None,
    }

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n  Configuration written to: {CONFIG_PATH}")
    print("\n  Next steps:")
    if vault_path:
        print(f"    python scripts/ingest_obsidian.py --vault {vault_path}")
    else:
        print("    python scripts/ingest_folder.py --dir ~/your/documents")
    print("    python scripts/search_cli.py -q 'your topic'")
    print("\n  Run 'python scripts/health_check.py' anytime to check system status.")


def main() -> None:
    vault_path, content_type = detect_content_type()
    run_onboarding(vault_path, content_type)


if __name__ == "__main__":
    main()