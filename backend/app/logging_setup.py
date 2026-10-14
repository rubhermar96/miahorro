"""Logging setup.

Rule (RNF-15): logs never contain financial data. The access log records method, path
(without query string), status and duration; request and response bodies are never logged.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

access_logger = logging.getLogger("miahorro.access")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


def register_access_log(app: FastAPI) -> None:
    @app.middleware("http")
    async def access_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        access_logger.info(
            "%s %s %s %.1fms", request.method, request.url.path, response.status_code, elapsed_ms
        )
        return response
