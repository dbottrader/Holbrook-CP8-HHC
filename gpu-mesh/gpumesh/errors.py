"""Errors that become a stable JSON body for both the public API and the dashboard."""

from __future__ import annotations


class MeshError(Exception):
    def __init__(
        self,
        status: int,
        message: str,
        err_type: str = "invalid_request_error",
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.err_type = err_type
        self.code = code
        self.headers = headers or {}

    def body(self) -> dict:
        return {"error": {"message": self.message, "type": self.err_type, "code": self.code}}
