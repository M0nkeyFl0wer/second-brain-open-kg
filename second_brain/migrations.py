"""
Schema versioning and migration for the knowledge graph.

Stores the current schema version in a _meta table. On Graph init,
checks the version and runs sequential migration functions if needed.
Each migration is a function that runs ALTER TABLE or CREATE statements
to bring the schema up to date without losing existing data.

Usage:
    from second_brain.migrations import ensure_schema_version
    ensure_schema_version(conn)  # called during Graph.__init__
"""
import logging

logger = logging.getLogger(__name__)

# Increment this when the schema changes. Each version needs a
# corresponding _migrate_vN_to_vN+1 function below.
CURRENT_VERSION = 1


def ensure_schema_version(conn) -> int:
    """Check schema version and run migrations if needed.
    Returns the final schema version after any migrations."""

    # Create _meta table if it doesn't exist
    conn.execute("""
        CREATE NODE TABLE IF NOT EXISTS _SchemaMeta (
            id STRING PRIMARY KEY,
            version INT64 DEFAULT 1
        )
    """)

    # Check current version
    result = conn.execute(
        "MATCH (m:_SchemaMeta {id: 'schema'}) RETURN m.version AS v")
    rows = []
    while result.has_next():
        rows.append(result.get_next())

    if not rows:
        # Fresh database — set version to current
        conn.execute("""
            CREATE (m:_SchemaMeta {id: 'schema', version: $v})
        """, parameters={"v": CURRENT_VERSION})
        logger.info("Schema initialized at version %d", CURRENT_VERSION)
        return CURRENT_VERSION

    db_version = rows[0][0]

    if db_version >= CURRENT_VERSION:
        return db_version

    # Run sequential migrations
    for v in range(db_version, CURRENT_VERSION):
        migrate_fn = globals().get(f"_migrate_v{v}_to_v{v + 1}")
        if migrate_fn is None:
            raise RuntimeError(
                f"No migration function for v{v} → v{v + 1}")
        logger.info("Migrating schema v%d → v%d", v, v + 1)
        migrate_fn(conn)

    # Update stored version
    conn.execute("""
        MATCH (m:_SchemaMeta {id: 'schema'})
        SET m.version = $v
    """, parameters={"v": CURRENT_VERSION})

    logger.info("Schema migrated to version %d", CURRENT_VERSION)
    return CURRENT_VERSION


# ---------------------------------------------------------------------------
# Migration functions — add new ones here as schema evolves.
# Name format: _migrate_vN_to_vN+1(conn)
# ---------------------------------------------------------------------------

# Example for when we need to add a column:
# def _migrate_v1_to_v2(conn):
#     """Add 'importance' column to Entity table."""
#     conn.execute("ALTER TABLE Entity ADD importance DOUBLE DEFAULT 0.0")
