"""Idempotent, additive migration for existing installations."""
from sqlalchemy import text


def migrate_media_schema(engine):
    # Serialize startup migration without resetting or rewriting existing data.
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(81734001)"))
        for definition in (
            "storage_filename VARCHAR",
            "media_type VARCHAR NOT NULL DEFAULT 'document'",
            "processing_status VARCHAR NOT NULL DEFAULT 'indexed'",
            "processing_progress INTEGER NOT NULL DEFAULT 100",
            "processing_stage VARCHAR NOT NULL DEFAULT '已入库'",
            "processing_error TEXT",
            "media_metadata JSONB NOT NULL DEFAULT '{}'::jsonb",
        ):
            connection.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS " + definition))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_processing ON documents(processing_status)"))
