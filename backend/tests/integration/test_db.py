"""Integration test: async DB session can execute SELECT 1.

Requires the local Postgres stack to be running (`make db-up`) and
`DATABASE_URL` to point at it (defaults to the docker-compose creds).
"""

import pytest
from sqlalchemy import text

from app.core.db import AsyncSessionLocal


@pytest.mark.asyncio
async def test_db_session_can_select_one() -> None:
    session = AsyncSessionLocal()
    try:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
    finally:
        await session.close()
