from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app import __version__
from app.admin import mount_admin
from app.auth.csrf import register_csrf_protection
from app.config import Settings, get_settings
from app.db import create_db_engine
from app.errors import register_error_handlers
from app.logging_setup import configure_logging, register_access_log
from app.routers import (
    accounts,
    auth,
    budgets,
    calculators,
    capture,
    categories,
    goals,
    health,
    imports,
    investments,
    loans,
    me,
    recurring,
    reports,
    rules,
    transactions,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # Interactive API docs only outside production.
    docs_enabled = not settings.is_production
    app = FastAPI(
        title="MiAhorro API",
        version=__version__,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )

    engine = create_db_engine(str(settings.database_url))
    app.state.settings = settings
    app.state.engine = engine
    session_factory = sessionmaker(engine, expire_on_commit=False)
    app.state.session_factory = session_factory

    register_error_handlers(app)
    register_csrf_protection(app)
    register_access_log(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(accounts.router)
    app.include_router(categories.router)
    app.include_router(transactions.router)
    app.include_router(imports.router)
    app.include_router(rules.router)
    app.include_router(capture.router)
    app.include_router(recurring.router)
    app.include_router(goals.router)
    app.include_router(budgets.router)
    app.include_router(loans.router)
    app.include_router(calculators.router)
    app.include_router(investments.router)
    app.include_router(reports.router)
    mount_admin(app, engine, session_factory, settings)
    return app


def app_factory() -> FastAPI:
    """Entry point for uvicorn (`--factory`), so importing this module has no side effects."""
    settings = get_settings()
    configure_logging(settings.log_level)
    return create_app(settings)
