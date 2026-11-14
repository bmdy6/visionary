"""Idempotent additive migration. Existing accounts never receive new trial grants."""
from sqlalchemy import inspect, text
from backend.models.database import Base


def migrate(engine):
    # Run with the app stopped; create_all alone cannot add existing-table columns.
    Base.metadata.create_all(engine)
    additions = {
        "users": {"trial_remaining": "INTEGER NOT NULL DEFAULT 0", "frozen_trials": "INTEGER NOT NULL DEFAULT 0"},
        "image_logs": {"source": "VARCHAR(32) NOT NULL DEFAULT 'normal'", "trial_used": "BOOLEAN NOT NULL DEFAULT 0", "aspect_ratio": "VARCHAR(16) DEFAULT '1:1'"},
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {c["name"] for c in inspect(conn).get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
