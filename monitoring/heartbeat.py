from __future__ import annotations

import atexit
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from data.models import ServiceHeartbeat, ServiceStatus
from database import DatabaseManager

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 30


@dataclass(frozen=True)
class ServiceState:
    status: ServiceStatus
    phase: Optional[str]
    detail: Optional[dict]


class ServiceHeartbeatWriter:
    def __init__(
            self,
            database_manager: DatabaseManager,
            service: str,
            command: str,
            interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS,
    ):
        self.__database_manager = database_manager
        self.__service = service
        self.__command = command
        self.__interval_seconds = interval_seconds
        self.__started_at = datetime.now()
        self.__state = ServiceState(ServiceStatus.STARTING, None, None)
        self.__state_lock = threading.Lock()
        self.__stop_requested = threading.Event()
        self.__thread: Optional[threading.Thread] = None

    def report(self, status: ServiceStatus, phase: Optional[str] = None, detail: Optional[dict] = None) -> None:
        with self.__state_lock:
            self.__state = ServiceState(status, phase, detail)
        self.__write()

    def start(self) -> "ServiceHeartbeatWriter":
        if self.__thread is not None:
            return self

        self.__write()
        self.__thread = threading.Thread(target=self.__keep_alive, name=f"heartbeat-{self.__service}", daemon=True)
        self.__thread.start()
        atexit.register(self.stop)
        return self

    def stop(self) -> None:
        if self.__stop_requested.is_set():
            return
        self.__stop_requested.set()
        self.report(ServiceStatus.STOPPED, phase="proces zakończony")

    def __keep_alive(self) -> None:
        while not self.__stop_requested.wait(self.__interval_seconds):
            self.__write()

    def __write(self) -> None:
        with self.__state_lock:
            state = self.__state

        try:
            with self.__database_manager.get_session() as session:
                session.merge(ServiceHeartbeat(
                    service=self.__service,
                    status=state.status,
                    phase=state.phase,
                    detail=state.detail,
                    command=self.__command,
                    started_at=self.__started_at,
                    updated_at=datetime.now(),
                ))
        except Exception as error:
            logger.warning("Could not write the heartbeat for %s: %s", self.__service, error)
