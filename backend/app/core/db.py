"""Database connection pool management using asyncpg."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import asyncpg

from app.config import settings

logger = logging.getLogger("questmf.db")

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Initialize asyncpg connection pool."""
    global _pool
    if _pool is None:
        logger.info("Initializing asyncpg connection pool to PostgreSQL...")
        _pool = await asyncpg.create_pool(
            dsn=settings.pg_dsn,
            min_size=settings.pg_pool_min,
            max_size=settings.pg_pool_max,
            command_timeout=settings.pg_statement_timeout_ms / 1000.0,
            server_settings={
                "statement_timeout": str(settings.pg_statement_timeout_ms),
                "application_name": "questmf-monolith",
            },
        )
        logger.info("Asyncpg connection pool established.")
    return _pool


async def close_pool() -> None:
    """Close asyncpg connection pool."""
    global _pool
    if _pool is not None:
        logger.info("Closing asyncpg connection pool...")
        await _pool.close()
        _pool = None


async def get_pool() -> asyncpg.Pool:
    """Get active database pool, initializing if necessary."""
    global _pool
    import asyncio

    current_loop = asyncio.get_running_loop()
    if _pool is None or getattr(_pool, "_loop", None) != current_loop or _pool._loop.is_closed():
        _pool = await asyncpg.create_pool(
            dsn=settings.pg_dsn,
            min_size=settings.pg_pool_min,
            max_size=settings.pg_pool_max,
            command_timeout=settings.pg_statement_timeout_ms / 1000.0,
            server_settings={
                "statement_timeout": str(settings.pg_statement_timeout_ms),
                "application_name": "questmf-monolith",
            },
        )
    return _pool


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Dependency for obtaining a single database connection from the pool."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
