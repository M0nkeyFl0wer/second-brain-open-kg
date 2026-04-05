.PHONY: test lint smoke check all pre-push

# Unit + integration tests (mocked Ollama, tmpdir graphs)
test:
	source .venv/bin/activate && python -m pytest tests/ -x -q --timeout=30

# Syntax check all Python files
lint:
	source .venv/bin/activate && python -m py_compile second_brain/*.py scripts/*.py

# Full pipeline smoke test (requires Ollama running)
smoke:
	source .venv/bin/activate && bash tests/smoke.sh

# Dependency check
check:
	source .venv/bin/activate && python -m second_brain.check

# Run everything except smoke (no Ollama needed)
all: check lint test

# Run before pushing
pre-push: all
	@echo "All checks passed. Safe to push."
