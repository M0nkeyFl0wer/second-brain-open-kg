"""Quick system check — verifies all dependencies are available."""


def run():
    checks = []
    try:
        import real_ladybug
        checks.append(f"  LadybugDB: {real_ladybug.__version__}")
    except ImportError:
        checks.append("  LadybugDB: NOT INSTALLED (pip install real_ladybug)")

    try:
        import pyarrow
        checks.append(f"  PyArrow: {pyarrow.__version__}")
    except ImportError:
        checks.append("  PyArrow: NOT INSTALLED (pip install pyarrow)")

    try:
        import spacy
        checks.append(f"  spaCy: {spacy.__version__}")
        try:
            spacy.load("en_core_web_sm")
            checks.append("  spaCy model: en_core_web_sm OK")
        except OSError:
            checks.append("  spaCy model: MISSING (python -m spacy download en_core_web_sm)")
    except ImportError:
        checks.append("  spaCy: NOT INSTALLED")

    try:
        import networkx
        checks.append(f"  NetworkX: {networkx.__version__}")
    except ImportError:
        checks.append("  NetworkX: NOT INSTALLED (pip install networkx)")

    try:
        import ripser
        checks.append("  Ripser: OK")
    except ImportError:
        checks.append("  Ripser: not installed (optional, pip install ripser)")

    try:
        import ollama
        models = ollama.list()
        model_names = [m.model for m in models.models] if hasattr(models, "models") else []
        checks.append(f"  Ollama: OK ({len(model_names)} models)")
        if any("nomic-embed-text" in m for m in model_names):
            checks.append("  Embedding model: nomic-embed-text OK")
        else:
            checks.append("  Embedding model: MISSING (ollama pull nomic-embed-text)")
    except Exception:
        checks.append("  Ollama: NOT RUNNING (install from ollama.com, then: ollama serve)")

    print("open-second-brain system check")
    print("=" * 40)
    for c in checks:
        print(c)
    print()

    from .ontology import Ontology
    try:
        ont = Ontology()
        print(f"Ontology: {ont}")
        if "NOT" in "\n".join(checks):
            print("  Some dependencies missing — see above.")
        else:
            print("  All checks passed.")
    except FileNotFoundError:
        print("  ONTOLOGY.md not found — run from the repo root directory.")


if __name__ == "__main__":
    run()
