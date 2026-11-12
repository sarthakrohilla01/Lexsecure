"""Lightweight schema migrations."""

from sqlalchemy import inspect, text

from app.database.session import Base, engine

_ADDITIONS = [
    ("users", "mfa_activated_at", "TIMESTAMP"),
    ("users", "mfa_last_step", "INTEGER"),
    ("users", "mfa_backup_codes", "TEXT"),
    ("users", "is_temporary", "BOOLEAN DEFAULT FALSE"),
    ("users", "expires_at", "TIMESTAMP"),
    ("document_metadata", "scan_engine", "VARCHAR(50)"),
    ("document_metadata", "scan_signature", "VARCHAR(255)"),
]


def _columns(conn, table: str) -> set:
    return {c["name"] for c in inspect(conn).get_columns(table)}


def ensure_schema() -> None:
    """Creates missing tables and adds new nullable columns in place."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        inspector = inspect(conn)
        for table, column, ddl in _ADDITIONS:
            if not inspector.has_table(table):
                continue
            if column in _columns(conn, table):
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
