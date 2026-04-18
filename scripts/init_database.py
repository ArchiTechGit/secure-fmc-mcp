"""Database initialization script.

Handles both fresh deployments (SQLAlchemy create_all) and upgrades
(sequential migration files).  Migrations are tracked via a
schema_migrations table so each file runs exactly once.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings, init_db
from src.config.database import get_db
from src.services.credential_manager import CredentialManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "config" / "migrations"


async def run_migrations():
    """Apply pending SQL migration files in order.

    Tracks applied migrations in a schema_migrations table so each file
    is executed exactly once.  This allows existing deployments to pick up
    new columns/tables that SQLAlchemy create_all() cannot add to existing
    tables.
    """
    db = get_db()

    async with db.async_engine.begin() as conn:
        # Ensure tracking table exists
        await conn.execute(
            __import__("sqlalchemy").text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "  id SERIAL PRIMARY KEY,"
                "  filename VARCHAR(255) NOT NULL UNIQUE,"
                "  applied_at TIMESTAMP DEFAULT NOW() NOT NULL"
                ")"
            )
        )

        # Get already-applied migrations
        result = await conn.execute(
            __import__("sqlalchemy").text(
                "SELECT filename FROM schema_migrations ORDER BY filename"
            )
        )
        applied = {row[0] for row in result.fetchall()}

    # Discover and sort migration files
    if not MIGRATIONS_DIR.is_dir():
        logger.info("No migrations directory found, skipping migrations")
        return

    migration_files = sorted(
        f for f in MIGRATIONS_DIR.iterdir()
        if f.suffix == ".sql" and f.name not in applied
    )

    if not migration_files:
        logger.info("No pending migrations")
        return

    from sqlalchemy import text

    for migration_file in migration_files:
        logger.info(f"Applying migration: {migration_file.name}")
        sql = migration_file.read_text()

        try:
            async with db.async_engine.begin() as conn:
                # Get the raw asyncpg connection and execute the entire
                # migration as one block.  This avoids asyncpg's prepared-
                # statement validation which fails when an ALTER TABLE ADD
                # COLUMN is followed by a CREATE INDEX on that column in
                # the same transaction.
                raw = await conn.get_raw_connection()
                await raw.driver_connection.execute(sql)

                # Record it as applied
                await conn.execute(
                    text(
                        "INSERT INTO schema_migrations (filename) VALUES (:f)"
                    ),
                    {"f": migration_file.name},
                )

            logger.info(f"Migration applied: {migration_file.name}")
        except Exception as e:
            logger.error(f"Migration {migration_file.name} failed: {e}")
            raise


async def main():
    """Initialize database and optionally bootstrap default FMC device.

    NOTE: Environment variables are only used for initial bootstrap.
    If a device already exists in the database, it will NOT be overwritten.
    Use the Web UI to manage device credentials after initial setup.
    """
    try:
        # Initialize database (creates tables from SQLAlchemy models)
        logger.info("Initializing database schema...")
        await init_db()
        logger.info("Database initialized successfully")

        # Apply pending migrations (handles ALTER TABLE, new tables, data fixes
        # that create_all cannot do on existing databases)
        logger.info("Checking for pending migrations...")
        await run_migrations()

        # Check if default device already exists
        credential_manager = CredentialManager()
        existing_cluster = await credential_manager.get_cluster("default")

        if existing_cluster:
            logger.info(f"Default FMC device already exists: {existing_cluster.url}")
            logger.info("Skipping environment variable bootstrap (use Web UI to modify)")
            return

        # Bootstrap from environment only if no device exists
        settings = get_settings()

        if settings.fmc_host_url and settings.fmc_username and settings.fmc_password:
            logger.info("No existing device found - bootstrapping from environment")
            logger.info(f"Creating default FMC device: {settings.fmc_host_url}")

            await credential_manager.store_credentials(
                name="default",
                url=settings.fmc_host_url,
                username=settings.fmc_username,
                password=settings.fmc_password,
                verify_ssl=settings.fmc_verify_ssl,
            )

            logger.info("Default FMC device created successfully")
            logger.info("NOTE: Future changes should be made via Web UI, not .env file")
        else:
            logger.warning("No FMC credentials found in environment")
            logger.warning(
                "Please configure a device via the Web UI or set "
                "FMC_HOST_URL, FMC_USERNAME, and FMC_PASSWORD for first-time setup"
            )

    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
