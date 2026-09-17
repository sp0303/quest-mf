"""Database and cache initialization script."""

import asyncio
import logging
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("questmf.init_db")


async def init_database():
    logger.info("Connecting to PostgreSQL at: %s", settings.pg_dsn.split("@")[-1])
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # Read and execute schema.sql
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")
        logger.info("Executing schema.sql...")
        await conn.execute(schema_sql)
        logger.info("Database schemas and tables successfully initialized.")

        # Seed default model version
        await conn.execute("""
            INSERT INTO scoring.model_versions (model_version, config, is_default)
            VALUES (
                'v1_baseline',
                '{"weights": {"momentum": 0.35, "persistence": 0.25, "quality": 0.20, "risk": 0.10, "cost": 0.10}, "min_obs_required": 252}',
                true
            )
            ON CONFLICT (model_version) DO NOTHING;
        """)

        # Seed categories
        categories = [
            ("EQ_SMALL_CAP", "Small Cap", "EQUITY"),
            ("EQ_MID_CAP", "Mid Cap", "EQUITY"),
            ("EQ_LARGE_CAP", "Large Cap", "EQUITY"),
            ("EQ_FLEXI_CAP", "Flexi Cap", "EQUITY"),
            ("EQ_ELSS", "ELSS (Tax Saving)", "EQUITY"),
        ]
        for code, label, asset_class in categories:
            await conn.execute(
                """
                INSERT INTO ref.categories (code, label, asset_class)
                VALUES ($1, $2, $3)
                ON CONFLICT (code) DO NOTHING;
            """,
                code,
                label,
                asset_class,
            )

        logger.info("Reference categories and default model version seeded.")
    finally:
        await conn.close()

    # Test Redis connection
    logger.info("Connecting to Redis at: %s", settings.redis_url.split("@")[-1])
    try:
        r = aioredis.from_url(settings.redis_url, socket_timeout=3.0)
        await r.ping()
        await r.set("ver:scores", "1")
        await r.set("ver:analytics", "1")
        logger.info("Redis cache verified and version keys initialized.")
        await r.aclose()
    except Exception as exc:
        logger.warning("Redis connection warning: %s", exc)


if __name__ == "__main__":
    asyncio.run(init_database())
