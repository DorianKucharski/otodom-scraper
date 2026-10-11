from __future__ import annotations

from functools import lru_cache
from typing import Iterator, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from database import DatabaseManager


@lru_cache(maxsize=1)
def get_database_manager() -> DatabaseManager:
    return DatabaseManager()


def get_session() -> Iterator[Session]:
    with get_database_manager().get_session() as session:
        yield session


def get_user_name(request: Request) -> Optional[str]:
    return getattr(request.state, "user_name", None)
