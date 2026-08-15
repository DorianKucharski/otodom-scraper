from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from data.models import ServiceHeartbeat, ServiceLog
from monitoring.services import ENRICHER_SERVICE, SCRAPER_SERVICE, SERVICE_LABELS, STALE_AFTER_SECONDS
from ..dependencies import get_session
from ..schemas import ServiceLogEntry, ServiceLogsResponse, ServiceStatusResponse

router = APIRouter(prefix="/api/services", tags=["services"])

_KNOWN_SERVICES = (SCRAPER_SERVICE, ENRICHER_SERVICE)
_MAX_LOG_ROWS = 2000


@router.get("", response_model=list[ServiceStatusResponse])
def get_services(session: Annotated[Session, Depends(get_session)]) -> list[ServiceStatusResponse]:
    heartbeats = {
        heartbeat.service: heartbeat
        for heartbeat in session.execute(select(ServiceHeartbeat)).scalars().all()
    }
    return [_to_status(service, heartbeats.get(service)) for service in _KNOWN_SERVICES]


@router.get("/{service}/logs", response_model=ServiceLogsResponse)
def get_service_logs(
        service: str,
        session: Annotated[Session, Depends(get_session)],
        limit: int = Query(500, ge=1, le=_MAX_LOG_ROWS),
        min_level: Optional[str] = Query(None, description="Pokaż tylko ten poziom i wyższe."),
        search: Optional[str] = Query(None),
) -> ServiceLogsResponse:
    statement = select(ServiceLog).where(ServiceLog.service == service)

    if min_level:
        statement = statement.where(ServiceLog.level.in_(_levels_from(min_level)))
    if search:
        statement = statement.where(ServiceLog.message.ilike(f"%{search}%"))

    rows = session.execute(statement.order_by(desc(ServiceLog.id)).limit(limit)).scalars().all()

    return ServiceLogsResponse(
        service=service,
        entries=[
            ServiceLogEntry(
                id=row.id,
                level=row.level,
                logger_name=row.logger_name,
                message=row.message,
                logged_at=row.logged_at,
            )
            for row in reversed(rows)
        ],
    )


_LEVEL_ORDER = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _levels_from(min_level: str) -> list[str]:
    normalized = min_level.upper()
    if normalized not in _LEVEL_ORDER:
        return list(_LEVEL_ORDER)
    return list(_LEVEL_ORDER[_LEVEL_ORDER.index(normalized):])


def _to_status(service: str, heartbeat: Optional[ServiceHeartbeat]) -> ServiceStatusResponse:
    if heartbeat is None:
        return ServiceStatusResponse(
            service=service,
            label=SERVICE_LABELS.get(service, service),
            status="unknown",
            is_alive=False,
        )

    seconds_since_update = max((datetime.now() - heartbeat.updated_at).total_seconds(), 0.0)
    is_alive = seconds_since_update <= STALE_AFTER_SECONDS

    return ServiceStatusResponse(
        service=service,
        label=SERVICE_LABELS.get(service, service),
        status=_status_value(heartbeat.status) if is_alive else "stale",
        reported_status=_status_value(heartbeat.status),
        phase=heartbeat.phase,
        detail=heartbeat.detail,
        command=heartbeat.command,
        started_at=heartbeat.started_at,
        updated_at=heartbeat.updated_at,
        seconds_since_update=round(seconds_since_update),
        is_alive=is_alive,
    )


def _status_value(status) -> str:
    return status.value if hasattr(status, "value") else str(status)
