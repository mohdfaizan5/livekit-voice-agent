"""
Database helpers — async pool creation and teardown for Neon (PostgreSQL).
"""

import logging
from typing import Optional

import asyncpg

from config import NEONDB_URL

logger = logging.getLogger("agent-UnlockPi")


async def create_db_pool() -> Optional[asyncpg.Pool]:
    """Create and return an asyncpg connection pool, or None on failure."""
    if not NEONDB_URL:
        logger.warning("NEONDB_API_KEY not set — database features will be unavailable.")
        return None
    try:
        pool = await asyncpg.create_pool(NEONDB_URL)
        logger.info("Connected to Neon DB successfully.")
        return pool
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        return None


async def close_db_pool(pool: Optional[asyncpg.Pool]) -> None:
    """Gracefully close the database pool."""
    if pool:
        await pool.close()
        logger.info("Closed Neon DB connection.")
