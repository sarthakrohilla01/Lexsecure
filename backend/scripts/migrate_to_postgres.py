#!/usr/bin/env python
"""Copy an existing SQLite database into PostgreSQL."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Integer, create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database.session import Base
import app.models  # noqa: F401 — registers every table on Base.metadata

TABLE_ORDER = [
    "users",
    "cases",
    "case_assignments",
    "documents",
    "document_versions",
    "document_metadata",
    "signatures",
    "ledger_blocks",
    "audit_logs",
    "workflow_tasks",
    "document_comments",
    "document_chunks",
    "dual_auth_requests",
    "login_attempts",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite -> PostgreSQL")
    parser.add_argument("--source", required=True, help="Path to the SQLite file")
    parser.add_argument("--target", default=settings.DATABASE_URL, help="PostgreSQL DATABASE_URL")
    parser.add_argument("--wipe", action="store_true", help="Delete existing target rows first")
    args = parser.parse_args()

    if not args.target.startswith("postgres"):
        print("ERROR: --target / DATABASE_URL must be a PostgreSQL URL.")
        return 1
    if not os.path.exists(args.source):
        print(f"ERROR: source database not found: {args.source}")
        return 1

    source_engine = create_engine(f"sqlite:///{os.path.abspath(args.source)}")
    target_engine = create_engine(args.target, pool_pre_ping=True)

    Base.metadata.create_all(bind=target_engine)

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)
    src, dst = SourceSession(), TargetSession()

    copied = {}
    try:
        with dst.begin():
            if args.wipe:
                for name in reversed(TABLE_ORDER):
                    table = Base.metadata.tables.get(name)
                    if table is not None:
                        dst.execute(table.delete())

            for name in TABLE_ORDER:
                table = Base.metadata.tables.get(name)
                if table is None:
                    continue

                rows = [dict(row._mapping) for row in src.execute(select(table)).all()]
                if not rows:
                    copied[name] = 0
                    continue

                dst.execute(table.insert(), rows)
                copied[name] = len(rows)
                print(f"[+] {name}: {len(rows)} rows")

        with target_engine.begin() as conn:
            for name in TABLE_ORDER:
                table = Base.metadata.tables.get(name)
                if table is None or "id" not in table.c:
                    continue
                if not isinstance(table.c["id"].type, Integer):
                    continue
                conn.execute(
                    text(
                        "SELECT setval("
                        "pg_get_serial_sequence(:table, 'id'), "
                        "COALESCE((SELECT MAX(id) FROM " + name + "), 1), "
                        "(SELECT COUNT(*) > 0 FROM " + name + "))"
                    ),
                    {"table": name},
                )
    finally:
        src.close()
        dst.close()

    print("\nMigration complete:")
    for name, count in copied.items():
        print(f"  {name:<24} {count}")
    print(f"\nTarget: {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
