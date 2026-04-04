# Privacy Guide

## The Three Modes

### Local (default)

Everything runs on your machine. No network connections. No API keys. No accounts.

- **Embeddings:** Ollama + nomic-embed-text (runs on your CPU/GPU)
- **Extraction:** Ollama + mistral or llama3 (runs on your CPU/GPU)
- **Graph:** KuzuDB directory on your disk
- **Search:** sqlite-vec file on your disk
- **Analysis:** NetworkX + Ripser in Python

**When to use:** Sensitive sources, leaked documents, anything you can't risk being transmitted. This is the default and the recommended mode for investigative work.

**Tradeoff:** Local extraction models are less accurate than large cloud models, especially for complex relationship extraction. Entity recognition is solid. Relationship typing (distinguishing FUNDED_BY from ASSOCIATED_WITH) may need manual correction.

### Hybrid

Embeddings stay local. Entity extraction can optionally use a remote LLM with zero-data-retention (ZDR) for non-sensitive documents.

- **Embeddings:** Local (Ollama) — always
- **Extraction:** Remote LLM with ZDR for non-sensitive docs, local for sensitive
- **Graph/Search/Analysis:** Local — always

**When to use:** You have a mix of public records (non-sensitive) and confidential material (sensitive). Process the public records with higher-quality remote extraction, process confidential material locally.

**Configuration:**

```python
# In second_brain/config.py
PRIVACY_MODE = "hybrid"
REMOTE_API_BASE = "https://api.anthropic.com/v1"
REMOTE_MODEL = "claude-haiku-4-5-20251001"
# Set NEWSROOM_API_KEY as an environment variable
```

**ZDR providers** (verify current policies before use):
- Anthropic API: zero-data-retention by default on API usage
- Check provider documentation for current data handling policies
- The safest approach: assume anything sent to a remote API could be logged

### Remote

Everything uses remote APIs. Not recommended for sensitive material.

**When to use:** Bulk processing of purely public datasets where speed and quality matter more than confidentiality.

## Newsroom Server Mode

For teams that want a shared knowledge graph:

1. **Run the server on a machine your team controls** — a newsroom server, a university server, or a machine at a press freedom organization
2. **Access over your local network or VPN** — never expose to the public internet
3. **Each journalist ingests documents** — the graph is shared, everyone benefits from everyone's research
4. **The graph stays on the server** — no cloud, no third-party access

See `docs/sharing-guide.md` for setup instructions.

## What Data Goes Where

| Data | Local mode | Hybrid mode | Remote mode |
|------|-----------|-------------|-------------|
| Your documents | Stays on disk | Stays on disk | Stays on disk |
| Document text (for extraction) | Processed locally | Non-sensitive: sent to API | Sent to API |
| Embeddings | Computed locally | Computed locally | Sent to API |
| Knowledge graph | On disk | On disk | On disk |
| Search queries | Local | Local | Local |
| Analysis results | Local | Local | Local |
| Daily briefings | Local | Local | Local |

The graph, search, and analysis NEVER leave your machine regardless of privacy mode. Only the extraction step (converting document text to entities) can optionally use a remote model.

## Operational Security Tips

- Keep the graph directory encrypted at rest (full disk encryption or encrypted volume)
- Don't commit the `data/` directory to git if the repo is public
- If using hybrid mode, review which documents were sent remotely (check extraction logs)
- Back up the graph directory regularly — it's your entire structured knowledge base
- If sharing with colleagues, use encrypted transfer (SCP, encrypted USB, etc.)
