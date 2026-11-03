from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class StringList(TypeDecorator):
    """
    Stores list of strings portably:
    Uses JSON representation on SQLite and PostgreSQL.
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return []
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> list[str]:
        if value is None:
            return []
        return [str(v) for v in value]


def utc_now() -> datetime:
    """Return timezone-aware current UTC timestamp."""
    return datetime.now(timezone.utc)
