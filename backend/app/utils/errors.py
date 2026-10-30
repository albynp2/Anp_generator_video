"""Error aplikasi. `message` aman ditampilkan ke user, `detail` hanya untuk log."""
from __future__ import annotations

from typing import Optional


class AppError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str = "bad_request",
        detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.detail = detail
