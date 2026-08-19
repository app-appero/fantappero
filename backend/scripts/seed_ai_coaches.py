"""Compatibility wrapper — prefer ``python -m devtools.seed_ai_managers``."""

from __future__ import annotations

from devtools.seed_ai_managers import (
    DEFAULT_COUNT,
    ai_manager_display_name,
    main,
    seed_ai_managers,
)

# Backward-compatible names used by older tests/docs.
AI_COACH_NAMES = tuple(ai_manager_display_name(index) for index in range(1, DEFAULT_COUNT + 1))


def seed_ai_coaches(session):  # noqa: ANN001
    return seed_ai_managers(session, count=DEFAULT_COUNT)


if __name__ == "__main__":
    raise SystemExit(main())
