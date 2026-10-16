"""Uniform JSON error responses: {"error": {"code", "message", "details"}}.

Messages are user-facing, so they are in Spanish. Details never include request bodies.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

_MESSAGES: dict[int, tuple[str, str]] = {
    400: ("bad_request", "La petición no es válida."),
    401: ("unauthorized", "Necesitas iniciar sesión."),
    403: ("forbidden", "No tienes permiso para hacer esto."),
    404: ("not_found", "No se ha encontrado el recurso."),
    405: ("method_not_allowed", "Método no permitido."),
    409: ("conflict", "La operación entra en conflicto con el estado actual."),
    422: ("validation_error", "Hay datos que no son válidos."),
    429: ("too_many_requests", "Demasiadas peticiones. Inténtalo dentro de un rato."),
    500: ("internal_error", "Ha ocurrido un error inesperado."),
    503: ("service_unavailable", "El servicio no está disponible en este momento."),
}


def error_body(status_code: int, message: str | None = None, details: Any = None) -> dict[str, Any]:
    default_code = HTTPStatus(status_code).phrase.lower().replace(" ", "_")
    code, default_message = _MESSAGES.get(status_code, (default_code, "Error."))
    return {"error": {"code": code, "message": message or default_message, "details": details}}


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # registered only for this type
        raise exc
    # Only pass through messages we wrote ourselves (strings); Starlette defaults are English.
    message = (
        exc.detail
        if isinstance(exc.detail, str) and exc.detail != HTTPStatus(exc.status_code).phrase
        else None
    )
    return JSONResponse(
        error_body(exc.status_code, message),
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def _validation_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # registered only for this type
        raise exc
    # Keep location and message only: "input" would echo the submitted (possibly financial) data.
    details = [{"loc": list(err["loc"]), "msg": err["msg"]} for err in exc.errors()]
    # Our own validators raise ValueError with a Spanish message meant for the user: show it.
    own_message = next(
        (
            str(err["msg"]).removeprefix("Value error, ")
            for err in exc.errors()
            if err.get("type") == "value_error"
        ),
        None,
    )
    return JSONResponse(error_body(422, own_message, details=details), status_code=422)


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(error_body(500), status_code=500)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
