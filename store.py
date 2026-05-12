from __future__ import annotations

from contextlib import contextmanager
import psycopg
from config import SUPABASE_DB_URL


SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_to_project (
    encircle_claim_id      TEXT PRIMARY KEY,
    companycam_project_id  TEXT NOT NULL,
    companycam_project_url TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS synced_photos (
    encircle_claim_id     TEXT NOT NULL,
    encircle_source_type  TEXT NOT NULL,
    encircle_source_id    TEXT NOT NULL,
    companycam_photo_id   TEXT,
    synced_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (encircle_source_type, encircle_source_id)
);

CREATE INDEX IF NOT EXISTS idx_synced_photos_claim ON synced_photos(encircle_claim_id);
"""


class SyncStore:
    def __init__(self, db_url: str = SUPABASE_DB_URL):
        self.db_url = db_url
        with self._conn() as c:
            c.execute(SCHEMA)

    @contextmanager
    def _conn(self):
        with psycopg.connect(self.db_url, connect_timeout=15) as conn:
            yield conn

    def get_project_for_claim(self, claim_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT encircle_claim_id, companycam_project_id, companycam_project_url "
                "FROM claim_to_project WHERE encircle_claim_id = %s",
                (claim_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "encircle_claim_id": row[0],
                "companycam_project_id": row[1],
                "companycam_project_url": row[2],
            }

    def record_project_for_claim(
        self, claim_id: str, project_id: str, project_url: str | None = None
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO claim_to_project "
                "(encircle_claim_id, companycam_project_id, companycam_project_url) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (encircle_claim_id) DO UPDATE SET "
                "  companycam_project_id = EXCLUDED.companycam_project_id, "
                "  companycam_project_url = EXCLUDED.companycam_project_url",
                (claim_id, project_id, project_url),
            )

    def is_photo_synced(self, source_type: str, source_id: str) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM synced_photos WHERE encircle_source_type = %s AND encircle_source_id = %s",
                (source_type, source_id),
            ).fetchone()
            return row is not None

    def record_photo_synced(
        self,
        claim_id: str,
        source_type: str,
        source_id: str,
        companycam_photo_id: str | None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO synced_photos "
                "(encircle_claim_id, encircle_source_type, encircle_source_id, companycam_photo_id) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (encircle_source_type, encircle_source_id) DO UPDATE SET "
                "  companycam_photo_id = EXCLUDED.companycam_photo_id",
                (claim_id, source_type, source_id, companycam_photo_id),
            )

    def synced_photo_count(self, claim_id: str) -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) FROM synced_photos WHERE encircle_claim_id = %s",
                (claim_id,),
            ).fetchone()
            return int(row[0]) if row else 0
