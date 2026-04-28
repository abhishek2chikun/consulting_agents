"""Integration tests for run lifecycle ORM fields and schema migration."""

from __future__ import annotations

from sqlalchemy import text

from app.core.db import AsyncSessionLocal
from app.models import Run


def test_run_model_exposes_lifecycle_fields() -> None:
    columns = Run.__table__.c

    assert "started_at" in columns
    assert columns.started_at.nullable is True
    assert "completed_at" in columns
    assert columns.completed_at.nullable is True
    assert "heartbeat_at" in columns
    assert columns.heartbeat_at.nullable is True


async def test_runs_table_has_nullable_lifecycle_columns_and_partial_index() -> None:
    session = AsyncSessionLocal()
    try:
        column_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT column_name, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'runs'
                      AND column_name IN ('started_at', 'completed_at', 'heartbeat_at')
                    ORDER BY column_name
                    """
                    )
                )
            )
            .mappings()
            .all()
        )

        assert column_rows == [
            {
                "column_name": "completed_at",
                "is_nullable": "YES",
                "column_default": None,
            },
            {
                "column_name": "heartbeat_at",
                "is_nullable": "YES",
                "column_default": None,
            },
            {
                "column_name": "started_at",
                "is_nullable": "YES",
                "column_default": None,
            },
        ]

        indexdef = await session.scalar(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'runs'
                  AND indexname = 'ix_runs_status_heartbeat'
                """
            )
        )

        assert indexdef is not None
        expected_index = (
            "CREATE INDEX ix_runs_status_heartbeat ON public.runs USING btree "
            "(status, heartbeat_at)"
        )
        assert expected_index in indexdef
        assert "WHERE (status = 'running'::run_status)" in indexdef
    finally:
        await session.close()
