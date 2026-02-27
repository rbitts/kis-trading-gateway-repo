from __future__ import annotations

import threading
import time
from pydantic import BaseModel


class SessionState(BaseModel):
    mode: str = "mock"
    owner: str | None = None
    state: str = "IDLE"
    source: str = "bootstrap"
    lease_expires_at: int | None = None


class SessionOrchestrator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = SessionState()

    def _expired(self, now: int) -> bool:
        return self._state.lease_expires_at is not None and now >= self._state.lease_expires_at

    def acquire(self, owner: str, ttl_sec: int = 30, source: str = "api") -> bool:
        now = int(time.time())
        with self._lock:
            if self._state.owner and self._state.owner != owner and not self._expired(now):
                return False
            self._state.owner = owner
            self._state.state = "ACTIVE"
            self._state.source = source
            self._state.lease_expires_at = now + ttl_sec
            return True

    def release(self, owner: str, source: str = "api") -> bool:
        with self._lock:
            if self._state.owner != owner:
                return False
            self._state.owner = None
            self._state.state = "IDLE"
            self._state.source = source
            self._state.lease_expires_at = None
            return True

    def status(self) -> SessionState:
        now = int(time.time())
        with self._lock:
            if self._state.owner and self._expired(now):
                self._state.owner = None
                self._state.state = "IDLE"
                self._state.source = "lease-expired"
                self._state.lease_expires_at = None
            return self._state.model_copy(deep=True)


session_orchestrator = SessionOrchestrator()
# default owner for MVP bootstrap
session_orchestrator.acquire(owner="gateway", ttl_sec=3600 * 24 * 365, source="bootstrap")
