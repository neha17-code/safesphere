"""Tiny additive migration so existing databases (e.g. the hosted one) pick up new columns.
create_all() only creates MISSING TABLES, never missing columns. Use Alembic for anything bigger."""
from sqlalchemy import inspect, text


def ensure_columns(engine) -> None:
    cols = {c["name"] for c in inspect(engine).get_columns("contacts")}
    if "telegram_chat_id" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE contacts ADD COLUMN telegram_chat_id VARCHAR(32)"))
