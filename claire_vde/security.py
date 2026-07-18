from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from claire_vde.storage import VentureRepository


@dataclass(frozen=True)
class AccessContext:
    client_key: str
    role: str
    trace_id: str


class VentureSecurity:
    def __init__(
        self,
        repository: VentureRepository,
        *,
        read_token: str | None = None,
        write_token: str | None = None,
        admin_token: str | None = None,
        rate_limit_per_minute: int | None = None,
    ) -> None:
        self.repository = repository
        self.read_token = (read_token if read_token is not None else os.environ.get("CLAIRE_VDE_API_READ_TOKEN", "")).strip()
        self.write_token = (write_token if write_token is not None else os.environ.get("CLAIRE_VDE_API_WRITE_TOKEN", "")).strip()
        self.admin_token = (admin_token if admin_token is not None else os.environ.get("CLAIRE_VDE_API_ADMIN_TOKEN", "")).strip()
        self.single_token = os.environ.get("CLAIRE_VDE_API_TOKEN", "").strip()
        self.rate_limit_per_minute = int(
            rate_limit_per_minute if rate_limit_per_minute is not None else os.environ.get("CLAIRE_VDE_RATE_LIMIT_PER_MINUTE", "60")
        )

    def authorize(self, request: Request, action: str) -> AccessContext:
        trace_id = self._trace_id(request)
        token = self._extract_token(request)
        route = request.url.path
        method = request.method
        client_hint = self._client_hint(request)

        if not token:
            self._audit_denied(trace_id, method, route, action, client_hint, "missing_token")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        role = self._role_for_token(token)
        if role is None:
            self._audit_denied(trace_id, method, route, action, self._client_key(token, client_hint), "invalid_token")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

        client_key = self._client_key(token, client_hint)
        if not self._allows(role, action):
            self._audit_denied(trace_id, method, route, action, client_key, f"insufficient_permission:{role}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")

        window_start = self._window_start()
        count = self.repository.record_rate_limit_hit(client_key=client_key, window_start=window_start)
        if count > self.rate_limit_per_minute:
            self._audit_denied(trace_id, method, route, action, client_key, "rate_limited")
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

        return AccessContext(client_key=client_key, role=role, trace_id=trace_id)

    def _audit_denied(self, trace_id: str, method: str, route: str, action: str, client_key: str, reason: str) -> None:
        self.repository.record_api_audit(
            trace_id=trace_id,
            method=method,
            route=route,
            action=action,
            client_key=client_key,
            decision="denied",
            reason=reason,
        )

    def _trace_id(self, request: Request) -> str:
        trace_id = str(request.headers.get("x-trace-id") or request.headers.get("x-request-id") or "").strip()
        if trace_id:
            return trace_id
        return f"trace_{int(time.time() * 1000)}_{secrets.token_hex(4)}"

    def _client_hint(self, request: Request) -> str:
        host = request.client.host if request.client else "unknown"
        return str(host or "unknown")

    def _client_key(self, token: str, client_hint: str) -> str:
        material = token or client_hint
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def _extract_token(self, request: Request) -> str:
        auth = str(request.headers.get("authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        return str(request.headers.get("x-claire-token") or "").strip()

    def _role_for_token(self, token: str) -> str | None:
        if self.admin_token and token == self.admin_token:
            return "admin"
        if self.write_token and token == self.write_token:
            return "write"
        if self.read_token and token == self.read_token:
            return "read"
        if self.single_token and token == self.single_token:
            return "admin"
        return None

    def _allows(self, role: str, action: str) -> bool:
        if role == "admin":
            return True
        if role == "write":
            return action in {"read", "write"}
        if role == "read":
            return action == "read"
        return False

    def _window_start(self) -> int:
        return int(time.time() // 60)


def security_from_env(repository: VentureRepository) -> VentureSecurity:
    return VentureSecurity(repository)
