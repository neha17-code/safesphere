"""Tiny additive migration so existing databases (e.g. the hosted one) pick up new columns.
create_all() only creates MISSING TABLES, never missing columns. Use Alembic for anything bigger."""
from sqlalchemy import inspect, text

NEW_COLUMNS = {
    "contacts": {
        "email": "VARCHAR(254)",
        "invite_sent_at": "TIMESTAMP",
        "invite_channel": "VARCHAR(12)",
    },
    "journeys": {
        "last_progress_at": "TIMESTAMP",
    },
}


def ensure_columns(engine) -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in NEW_COLUMNS.items():
            have = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
