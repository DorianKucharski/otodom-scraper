from __future__ import annotations

import logging

from sqlalchemy import Table, inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ensure_table(engine: Engine, table: Table):
    inspector = inspect(engine)
    if inspector.has_table(table.name):
        existing = {column["name"]: _normalized(str(column["type"])) for column in inspector.get_columns(table.name)}
        expected = {column.name: _normalized(column.type.compile(engine.dialect)) for column in table.columns}
        if existing == expected:
            return
        logger.warning("%s has an outdated shape, recreating it", table.name)
        table.drop(engine)
    table.create(engine)


def _normalized(type_name: str) -> str:
    return type_name.upper().replace(" WITHOUT TIME ZONE", "")
