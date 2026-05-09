"""
phantombox/auth/db_extensions.py
─────────────────────────────────────────────────────────────
Adds shared_links table and extends init_db for new features:
  - shared_links: ephemeral self-destruct share links
  - Adds ip_address column to audit_ledger if missing
  - Adds fragment_count/file_size to file_registry if missing
─────────────────────────────────────────────────────────────
"""

import logging
from .db import get_db

logger = logging.getLogger("phantombox.db_ext")


def extend_db():
    """
    Run all schema migrations for new features.
    Updated to handle foreign key compatibility by inheriting DB defaults.
    """
    conn, cur = get_db()
    try:
        # ── 1. Create shared_links table ────────────────────
        # Note: We removed explicit COLLATE to allow inheritance from the database
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shared_links (
                id              VARCHAR(36)  PRIMARY KEY,
                file_id         VARCHAR(255) NOT NULL,
                owner_id        VARCHAR(36)  NOT NULL,
                token           VARCHAR(128) NOT NULL UNIQUE,
                label           VARCHAR(255),
                max_downloads   INT          DEFAULT 1,
                download_count  INT          DEFAULT 0,
                expires_at      BIGINT       NOT NULL,
                created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                is_revoked      TINYINT(1)   DEFAULT 0,
                last_accessed   TIMESTAMP    NULL,
                CONSTRAINT fk_share_file FOREIGN KEY (file_id)  REFERENCES file_registry(file_id) ON DELETE CASCADE,
                CONSTRAINT fk_share_owner FOREIGN KEY (owner_id) REFERENCES users(id)              ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)

        # ── 2. Add ip_address to audit_ledger if missing ───────
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM   information_schema.COLUMNS
            WHERE  TABLE_SCHEMA = DATABASE()
            AND    TABLE_NAME   = 'audit_ledger'
            AND    COLUMN_NAME  = 'ip_address'
        """)
        if cur.fetchone()["cnt"] == 0:
            cur.execute(
                "ALTER TABLE audit_ledger ADD COLUMN ip_address VARCHAR(45) NULL"
            )
            logger.info("✅ Added ip_address to audit_ledger")

        # ── 3. Add fragment_count to file_registry if missing ──
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM   information_schema.COLUMNS
            WHERE  TABLE_SCHEMA = DATABASE()
            AND    TABLE_NAME   = 'file_registry'
            AND    COLUMN_NAME  = 'fragment_count'
        """)
        if cur.fetchone()["cnt"] == 0:
            cur.execute(
                "ALTER TABLE file_registry ADD COLUMN fragment_count INT DEFAULT 3"
            )
            logger.info("✅ Added fragment_count to file_registry")

        # ── 4. Add file_size to file_registry if missing ───────
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM   information_schema.COLUMNS
            WHERE  TABLE_SCHEMA = DATABASE()
            AND    TABLE_NAME   = 'file_registry'
            AND    COLUMN_NAME  = 'file_size'
        """)
        if cur.fetchone()["cnt"] == 0:
            cur.execute(
                "ALTER TABLE file_registry ADD COLUMN file_size BIGINT DEFAULT 0"
            )
            logger.info("✅ Added file_size to file_registry")

        conn.commit()
        logger.info("✅ DB schema extensions applied")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ extend_db error: {e}")
        # We don't raise here so the app can still start if the columns already exist
    finally:
        cur.close()
        conn.close()