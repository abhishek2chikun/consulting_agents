#!/usr/bin/env bash
#
# scripts/check.sh — local "all green" gate for the Consulting Research Agent.
#
# Runs lint + typecheck + fast tests for both backend and frontend. Fails fast
# on the first error. Mirrors what CI would run (no DB-dependent tests).
#
# Backend integration tests (tests/integration/) are intentionally excluded
# here because they require a live Postgres. Run them separately with:
#
#     make db-up
#     make check-integration
#
# `pnpm build` (next build) is gated behind CHECK_BUILD=1 because it's a
# CI-grade check that's slower than lint+typecheck. CI workflows should
# export CHECK_BUILD=1.
#
# Usage:
#     bash scripts/check.sh                 # lint + typecheck + unit tests
#     CHECK_BUILD=1 bash scripts/check.sh   # also run `pnpm build`
#     # or:  make check

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Backend: ruff check"
( cd backend && uv run ruff check . )

echo "==> Backend: ruff format --check"
( cd backend && uv run ruff format --check . )

echo "==> Backend: mypy app"
( cd backend && uv run mypy app )

echo "==> Backend: pytest (unit only, integration tests skipped)"
( cd backend && uv run pytest --ignore=tests/integration -v )

echo "==> Frontend: pnpm install --frozen-lockfile"
( cd frontend && pnpm install --frozen-lockfile )

echo "==> Frontend: pnpm lint"
( cd frontend && pnpm lint )

echo "==> Frontend: pnpm typecheck"
( cd frontend && pnpm typecheck )

echo "==> Frontend: node --test lib/runEvents.test.js"
( cd frontend && node --test lib/runEvents.test.js )

if [[ "${CHECK_BUILD:-0}" == "1" ]]; then
  echo "==> Frontend: pnpm build (CHECK_BUILD=1)"
  ( cd frontend && pnpm build )
else
  echo "==> Frontend: skipping build (set CHECK_BUILD=1 to enable)"
fi

echo
echo "All checks passed."
