"""Administration panel at /admin (RF-PLT-02, RF-PLT-08).

It reuses the app's own sign-in: only a fully signed-in administrator gets in. It never shows
financial data or secrets. The reference tables (ITP, AJD, tax scales, Euribor…) are edited
here: to change a value from a date, add a row with that `valid_from` and keep the old one.
"""

from typing import Any

from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from app.auth import sessions
from app.config import Settings
from app.models.auth import LEVEL_FULL
from app.models.calculators import ReferenceValue
from app.models.imports import ImportTemplate
from app.models.loans import ReferenceRate
from app.models.user import User


class _AdminAuth(AuthenticationBackend):
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]) -> None:
        # SQLAdmin needs its own signed cookie for flash messages; it never holds credentials.
        super().__init__(
            secret_key=settings.secret_key.get_secret_value(),
            session_cookie="miahorro_admin",
            https_only=settings.secure_cookies,
            same_site="lax",
        )
        self._settings = settings
        self._session_factory = session_factory

    def _admin_user(self, request: Request) -> tuple[bool, User | None]:
        token = request.cookies.get(self._settings.session_cookie_name)
        with self._session_factory() as db:
            row = sessions.load(db, token, self._settings)
            if row is None or row.level != LEVEL_FULL:
                return False, None
            return True, row.user if row.user.is_admin else None

    async def authenticate(self, request: Request) -> Response | bool:
        signed_in, admin = self._admin_user(request)
        if admin is not None:
            return True
        if signed_in:
            return PlainTextResponse("No tienes permiso para entrar aquí.", status_code=403)
        return RedirectResponse("/entrar?siguiente=/admin", status_code=302)

    async def login(self, request: Request) -> Response | bool:
        return RedirectResponse("/entrar?siguiente=/admin", status_code=302)

    async def logout(self, request: Request) -> Response | bool:
        return RedirectResponse("/mas", status_code=302)

    async def get_user_id(self, request: Request) -> Any:
        _, admin = self._admin_user(request)
        return str(admin.id) if admin else None


class UserAdmin(ModelView, model=User):
    name = "Usuario"
    name_plural = "Usuarios"
    icon = "fa-solid fa-user"
    can_create = False  # users are created with `python -m app.cli create-user`
    can_delete = False
    column_list = [User.email, User.display_name, User.is_admin, User.is_active, User.created_at]
    column_details_list = [
        User.email,
        User.display_name,
        User.is_admin,
        User.is_active,
        User.totp_enabled_at,
        User.locked_until,
        User.created_at,
        User.updated_at,
    ]
    column_searchable_list = [User.email, User.display_name]
    column_labels = {
        User.email: "Email",
        User.display_name: "Nombre",
        User.is_admin: "Administrador",
        User.is_active: "Activo",
        User.totp_enabled_at: "Verificación en dos pasos desde",
        User.locked_until: "Bloqueado hasta",
        User.created_at: "Alta",
        User.updated_at: "Última modificación",
    }
    form_columns = [User.display_name, User.is_admin, User.is_active]


class ImportTemplateAdmin(ModelView, model=ImportTemplate):
    """Statement templates are shared by every user (RF-IMP-01): rename or remove bad ones."""

    name = "Plantilla de importación"
    name_plural = "Plantillas de importación"
    icon = "fa-solid fa-file-import"
    can_create = False  # created from the import screen, with a file to try them on
    column_list = [ImportTemplate.name, ImportTemplate.created_at]
    column_details_list = [ImportTemplate.name, ImportTemplate.mapping, ImportTemplate.created_at]
    column_searchable_list = [ImportTemplate.name]
    column_labels = {
        ImportTemplate.name: "Nombre",
        ImportTemplate.mapping: "Columnas",
        ImportTemplate.created_at: "Creada",
    }
    form_columns = [ImportTemplate.name]


class ReferenceValueAdmin(ModelView, model=ReferenceValue):
    """Shared values the calculators use: each one with the date it applies from and its
    source (RF-PLT-02)."""

    name = "Valor de referencia"
    name_plural = "Valores de referencia"
    icon = "fa-solid fa-scale-balanced"
    column_list = [
        ReferenceValue.table_name,
        ReferenceValue.key,
        ReferenceValue.value,
        ReferenceValue.valid_from,
        ReferenceValue.source,
    ]
    column_details_list = [
        ReferenceValue.table_name,
        ReferenceValue.key,
        ReferenceValue.value,
        ReferenceValue.extra,
        ReferenceValue.valid_from,
        ReferenceValue.source,
        ReferenceValue.note,
        ReferenceValue.updated_at,
    ]
    column_searchable_list = [ReferenceValue.table_name, ReferenceValue.key]
    column_sortable_list = [
        ReferenceValue.table_name,
        ReferenceValue.key,
        ReferenceValue.valid_from,
    ]
    column_default_sort = [(ReferenceValue.table_name, False), (ReferenceValue.key, False)]
    page_size = 100
    column_labels = {
        ReferenceValue.table_name: "Tabla",
        ReferenceValue.key: "Clave",
        ReferenceValue.value: "Valor (% o €)",
        ReferenceValue.extra: "Escala (JSON)",
        ReferenceValue.valid_from: "Vigente desde",
        ReferenceValue.source: "Fuente",
        ReferenceValue.note: "Nota",
        ReferenceValue.updated_at: "Última modificación",
    }
    form_columns = [
        ReferenceValue.table_name,
        ReferenceValue.key,
        ReferenceValue.value,
        ReferenceValue.extra,
        ReferenceValue.valid_from,
        ReferenceValue.source,
        ReferenceValue.note,
    ]


class ReferenceRateAdmin(ModelView, model=ReferenceRate):
    """Monthly Euribor values; users can also add them from the app."""

    name = "Euribor"
    name_plural = "Euribor"
    icon = "fa-solid fa-chart-line"
    column_list = [ReferenceRate.index, ReferenceRate.month, ReferenceRate.value]
    column_sortable_list = [ReferenceRate.month]
    column_default_sort = [(ReferenceRate.month, True)]
    column_labels = {
        ReferenceRate.index: "Índice",
        ReferenceRate.month: "Mes",
        ReferenceRate.value: "Valor (%)",
    }
    form_columns = [ReferenceRate.index, ReferenceRate.month, ReferenceRate.value]


def mount_admin(
    app: FastAPI, engine: Engine, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    admin = Admin(
        app,
        engine=engine,
        session_maker=session_factory,
        base_url="/admin",
        title="MiAhorro · Administración",
        authentication_backend=_AdminAuth(settings, session_factory),
    )
    admin.add_view(UserAdmin)
    admin.add_view(ImportTemplateAdmin)
    admin.add_view(ReferenceValueAdmin)
    admin.add_view(ReferenceRateAdmin)
