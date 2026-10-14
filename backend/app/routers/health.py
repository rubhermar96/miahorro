import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.db import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "unavailable"]


@router.get("/health", responses={503: {"model": HealthResponse}})
def health(session: Annotated[Session, Depends(get_session)], response: Response) -> HealthResponse:
    """Liveness and database check, used by the container healthcheck and the app."""
    try:
        session.execute(text("SELECT 1"))
        database: Literal["ok", "unavailable"] = "ok"
    except SQLAlchemyError:
        logger.warning("Database health check failed")
        database = "unavailable"

    if database != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", version=__version__, database=database)
    return HealthResponse(status="ok", version=__version__, database=database)
