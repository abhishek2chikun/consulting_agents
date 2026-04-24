"""Integration test: SettingKV upsert + read against real Postgres.

Requires `make db-up` and the schema from migration `0002` to be applied
(`uv run alembic upgrade head`).
"""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.db import AsyncSessionLocal
from app.models import SINGLETON_USER_ID, SettingKV


async def test_upsert_and_read_setting() -> None:
    session = AsyncSessionLocal()
    try:
        # Insert path.
        stmt = insert(SettingKV).values(
            user_id=SINGLETON_USER_ID,
            key="max_stage_retries",
            value={"value": 2},
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SettingKV.user_id, SettingKV.key],
            set_={"value": stmt.excluded.value},
        )
        await session.execute(stmt)
        await session.commit()

        result = await session.execute(
            select(SettingKV).where(
                SettingKV.user_id == SINGLETON_USER_ID,
                SettingKV.key == "max_stage_retries",
            )
        )
        row = result.scalar_one()
        assert row.value == {"value": 2}

        # Update path — same upsert, different value.
        stmt2 = insert(SettingKV).values(
            user_id=SINGLETON_USER_ID,
            key="max_stage_retries",
            value={"value": 5},
        )
        stmt2 = stmt2.on_conflict_do_update(
            index_elements=[SettingKV.user_id, SettingKV.key],
            set_={"value": stmt2.excluded.value},
        )
        await session.execute(stmt2)
        await session.commit()

        # expire_all() forces a fresh read after commit because expire_on_commit=False
        # is set on AsyncSessionLocal — without this, the post-update SELECT would
        # return the cached pre-update instance.
        session.expire_all()
        result2 = await session.execute(
            select(SettingKV).where(
                SettingKV.user_id == SINGLETON_USER_ID,
                SettingKV.key == "max_stage_retries",
            )
        )
        row2 = result2.scalar_one()
        assert row2.value == {"value": 5}
    finally:
        # Idempotent across runs.
        await session.execute(
            delete(SettingKV).where(
                SettingKV.user_id == SINGLETON_USER_ID,
                SettingKV.key == "max_stage_retries",
            )
        )
        await session.commit()
        await session.close()
