"""
Health check script for open-second-brain — graph and chunk store observability.

Run manually: python scripts/health_check.py
Run via timer: systemd timer every 15 min

Checks:
1. Chunk store: total chunks, embedded count, sensitivity distribution
2. Graph: total entities, total edges, type distribution, orphan count
3. Queue: pending writes in graph_queue.jsonl
4. Write log: rejection rate from write_log.jsonl
5. Last enrichment: time since last run
6. WAL health: check for orphaned WAL files

Thresholds:
- Orphan entities > 50: WARNING
- Connected % < 95%: WARNING
- Rejection rate > 20%: CRITICAL
- Queue depth > 1000: WARNING
- Last enrichment > 24h: WARNING
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from second_brain.chunk_store import ChunkStore
from second_brain.graph import GraphReader

DATA_DIR = Path(__file__).parent.parent / "data"
CHUNK_STORE_PATH = DATA_DIR / "chunks.duckdb"
GRAPH_DB_PATH = DATA_DIR / "brain.ldb"
QUEUE_PATH = DATA_DIR / "graph_queue.jsonl"
WRITE_LOG = DATA_DIR / "write_log.jsonl"
LAST_RUN_FILE = DATA_DIR / "enrichment_last_run.txt"
ENRICHMENT_LOG = DATA_DIR / "enrichment.log"

THRESHOLDS = {
    "orphan_entities": {"warning": 50, "critical": 500},
    "connected_pct": {"warning": 95, "critical": 90},
    "rejection_rate": {"warning": 0.15, "critical": 0.20},
    "queue_depth": {"warning": 1000, "critical": 5000},
    "hours_since_enrichment": {"warning": 24, "critical": 72},
}


def status_icon(ok: bool, warn: bool) -> str:
    return "✅" if ok else ("⚠️" if warn else "❌")


def check_chunk_store() -> dict:
    """Check chunk store health."""
    try:
        store = ChunkStore(CHUNK_STORE_PATH, read_only=True)
        stats = store.get_stats()
        store.close()

        issues = []
        if stats.get("unembedded_chunks", 0) > 100:
            issues.append(f"{stats['unembedded_chunks']} unembedded chunks")

        return {
            "status": "ok" if not issues else ("warning" if len(issues) < 3 else "critical"),
            "total_chunks": stats.get("total_chunks", 0),
            "embedded_chunks": stats.get("embedded_chunks", 0),
            "unembedded_chunks": stats.get("unembedded_chunks", 0),
            "sensitivity_counts": stats.get("sensitivity_counts", {}),
            "issues": issues,
        }
    except Exception as ex:
        return {"status": "error", "error": str(ex)}


def check_graph() -> dict:
    """Check graph health."""
    try:
        reader = GraphReader(GRAPH_DB_PATH)
        stats = reader.get_stats()
        reader.close()

        if "error" in stats:
            return {"status": "error", "error": stats["error"]}

        # Check orphan entities (no edges)
        orphan_count = _count_orphans()
        total_entities = stats.get("total_entities", 0)
        connected_pct = ((total_entities - orphan_count) / total_entities * 100) if total_entities > 0 else 0

        issues = []
        if orphan_count > THRESHOLDS["orphan_entities"]["critical"]:
            issues.append(f"{orphan_count} orphan entities (critical)")
        elif orphan_count > THRESHOLDS["orphan_entities"]["warning"]:
            issues.append(f"{orphan_count} orphan entities (warning)")

        if connected_pct < THRESHOLDS["connected_pct"]["critical"]:
            issues.append(f"Only {connected_pct:.1f}% connected (critical)")
        elif connected_pct < THRESHOLDS["connected_pct"]["warning"]:
            issues.append(f"Only {connected_pct:.1f}% connected (warning)")

        return {
            "status": "ok" if not issues else ("warning" if len(issues) < 2 else "critical"),
            "total_entities": total_entities,
            "total_edges": stats.get("total_edges", 0),
            "type_counts": stats.get("type_counts", {}),
            "orphan_entities": orphan_count,
            "connected_pct": connected_pct,
            "issues": issues,
        }
    except Exception as ex:
        return {"status": "error", "error": str(ex)}


def _count_orphans() -> int:
    """Count entities with no edges."""
    try:
        reader = GraphReader(GRAPH_DB_PATH)
        orphans = reader.query("""
            MATCH (e:entity)
            WHERE NOT exists((e)-[]->()) AND NOT exists((e)<-[]-())
            RETURN count(e) as c
        """)
        reader.close()
        return orphans[0]["c"] if orphans else 0
    except Exception:
        return 0


def check_queue() -> dict:
    """Check write queue depth."""
    try:
        if not QUEUE_PATH.exists():
            return {"status": "ok", "depth": 0}

        with open(QUEUE_PATH) as f:
            depth = sum(1 for _ in f)

        issues = []
        if depth > THRESHOLDS["queue_depth"]["critical"]:
            issues.append(f"Queue depth {depth} (critical)")
        elif depth > THRESHOLDS["queue_depth"]["warning"]:
            issues.append(f"Queue depth {depth} (warning)")

        return {
            "status": "ok" if not issues else ("warning" if len(issues) < 2 else "critical"),
            "depth": depth,
            "issues": issues,
        }
    except Exception as ex:
        return {"status": "error", "error": str(ex)}


def check_rejection_rate() -> dict:
    """Check write_log.jsonl rejection rate."""
    try:
        if not WRITE_LOG.exists():
            return {"status": "ok", "rate": 0.0}

        total = 0
        rejected = 0
        with open(WRITE_LOG) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    total += 1
                    if entry.get("type"):
                        rejected += 1
                except json.JSONDecodeError:
                    continue

        rate = rejected / total if total > 0 else 0.0

        issues = []
        if rate > THRESHOLDS["rejection_rate"]["critical"]:
            issues.append(f"Rejection rate {rate:.0%} (critical)")
        elif rate > THRESHOLDS["rejection_rate"]["warning"]:
            issues.append(f"Rejection rate {rate:.0%} (warning)")

        return {
            "status": "ok" if not issues else ("warning" if len(issues) < 2 else "critical"),
            "rate": rate,
            "total_records": total,
            "rejected_records": rejected,
            "issues": issues,
        }
    except Exception as ex:
        return {"status": "error", "error": str(ex)}


def check_last_enrichment() -> dict:
    """Check time since last enrichment run."""
    try:
        if not LAST_RUN_FILE.exists():
            return {"status": "warning", "hours_since": None, "issues": ["Never run"]}

        with open(LAST_RUN_FILE) as f:
            last_run = datetime.fromisoformat(f.read().strip())

        hours_since = (datetime.now(timezone.utc) - last_run).total_seconds() / 3600

        issues = []
        if hours_since > THRESHOLDS["hours_since_enrichment"]["critical"]:
            issues.append(f"Last enrichment {hours_since:.1f}h ago (critical)")
        elif hours_since > THRESHOLDS["hours_since_enrichment"]["warning"]:
            issues.append(f"Last enrichment {hours_since:.1f}h ago (warning)")

        return {
            "status": "ok" if not issues else ("warning" if len(issues) < 2 else "critical"),
            "hours_since": hours_since,
            "last_run": last_run.isoformat(),
            "issues": issues,
        }
    except Exception as ex:
        return {"status": "error", "error": str(ex)}


def check_wal_health() -> dict:
    """Check for orphaned WAL files."""
    issues = []
    for db_path in [GRAPH_DB_PATH]:
        wal = db_path.with_suffix(".wal")
        shadow = db_path.with_suffix(".shadow")
        orphan_marker = DATA_DIR / ".builder-running"

        if wal.exists() and orphan_marker.exists():
            issues.append(f"Orphaned WAL detected: {wal.name}")

        if shadow.exists() and orphan_marker.exists():
            issues.append(f"Orphaned shadow detected: {shadow.name}")

    return {
        "status": "ok" if not issues else "critical",
        "issues": issues,
    }


def main() -> None:
    """Run all health checks and print report."""
    print("=" * 60)
    print(" open-second-brain Health Check")
    print(f" {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    checks = {
        "Chunk Store": check_chunk_store(),
        "Graph": check_graph(),
        "Write Queue": check_queue(),
        "Rejection Rate": check_rejection_rate(),
        "Last Enrichment": check_last_enrichment(),
        "WAL Health": check_wal_health(),
    }

    all_ok = True
    any_critical = False

    for name, result in checks.items():
        status = result.get("status", "error")
        icon = status_icon(status == "ok", status == "warning")
        print(f"\n{icon} {name}: {status.upper()}")
        print(f"   {json.dumps(result, indent=2, default=str)}")

        if status != "ok":
            all_ok = False
        if status == "critical":
            any_critical = True

    print("\n" + "=" * 60)
    if any_critical:
        print("❌ CRITICAL ISSUES DETECTED — manual intervention required")
        sys.exit(2)
    elif not all_ok:
        print("⚠️  WARNINGS DETECTED — monitor closely")
        sys.exit(1)
    else:
        print("✅ All systems healthy")
        sys.exit(0)


if __name__ == "__main__":
    main()