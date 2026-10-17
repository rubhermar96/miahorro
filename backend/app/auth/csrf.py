"""CSRF protection for the cookie-authenticated API.

State-changing requests must carry a custom header. Browsers only let another site send custom
headers after a CORS preflight, which this API never approves, so a forged form or script on
another site cannot pass. SameSite=Lax cookies are a second layer.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.errors import error_body

CSRF_HEADER = "X-MiAhorro-CSRF"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Endpoints authenticated by a bearer token instead of the cookie: the payment capture of the
# Apple Pay Shortcut (app/routers/capture.py), which never reads the session cookie.
EXEMPT_PATHS: frozenset[str] = frozenset({"/api/capture/payments"})


def register_csrf_protection(app: FastAPI) -> None:
    @app.middleware("http")
    async def csrf_protection(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if (
            request.method in _UNSAFE_METHODS
            and path.startswith("/api/")
            and path not in EXEMPT_PATHS
            and request.headers.get(CSRF_HEADER) != "1"
        ):
            message = "Petición rechazada por seguridad. Recarga la página e inténtalo de nuevo."
            return JSONResponse(error_body(403, message), status_code=403)
        return await call_next(request)
