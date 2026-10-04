"""Tiny additive migration so existing databases (e.g. the hosted one) pick up new columns.
create_all() only creates MISSING TABLES, never missing columns. Use Alembic for anything bigger."""
from sqlalchemy import inspect, text

NEW_CONTACT_COLUMNS = {
    "email": "VARCHAR(254)",
}


def ensure_columns(engine) -> None:
    have = {c["name"] for c in inspect(engine).get_columns("contacts")}
    with engine.begin() as conn:
        for name, ddl in NEW_CONTACT_COLUMNS.items():
            if name not in have:
                conn.execute(text(f"ALTER TABLE contacts ADD COLUMN {name} {ddl}"))
