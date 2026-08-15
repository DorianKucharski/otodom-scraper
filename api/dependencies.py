from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from sqlalchemy.orm import Session

from database import DatabaseManager


@lru_cache(maxsize=1)
def get_database_manager() -> DatabaseManager:
    return DatabaseManager()


def get_session() -> Iterator[Session]:
    with get_database_manager().get_session() as session:
        yield session
