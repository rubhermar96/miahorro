"""Administration commands, run inside the API container:

    docker compose -f deploy/compose.prod.yaml exec api python -m app.cli create-user \\
        --email tu@email.com --name "Tu nombre" --admin
"""

import sys
from typing import Annotated

import typer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import reference
from app.auth import sessions
from app.config import get_settings
from app.db import create_db_engine
from app.models.auth import PasskeyCredential, RecoveryCode
from app.models.user import User
from app.security import passwords

cli = typer.Typer(help="Administración de MiAhorro.", no_args_is_help=True)


def _db() -> Session:
    return Session(create_db_engine(str(get_settings().database_url)))


def _find(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        typer.echo(f"No existe ningún usuario con el email {email}.", err=True)
        raise typer.Exit(1)
    return user


@cli.command("create-user")
def create_user(
    email: Annotated[str, typer.Option(help="Email con el que iniciará sesión.")],
    name: Annotated[str, typer.Option(help="Nombre que se muestra en la app.")],
    admin: Annotated[bool, typer.Option(help="Puede entrar en /admin.")] = False,
    password_stdin: Annotated[
        bool, typer.Option(help="Leer la contraseña de la entrada estándar (scripts).")
    ] = False,
) -> None:
    """Crea un usuario. La verificación en dos pasos se configura en su primer inicio de sesión."""
    password = (
        sys.stdin.readline().rstrip("\n")
        if password_stdin
        else typer.prompt("Contraseña", hide_input=True, confirmation_prompt=True)
    )
    try:
        passwords.validate_new_password(password)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    email = email.strip().lower()
    with _db() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            typer.echo(f"Ya existe un usuario con el email {email}.", err=True)
            raise typer.Exit(1)
        db.add(
            User(
                email=email,
                display_name=name.strip(),
                password_hash=passwords.hash_password(password),
                is_admin=admin,
            )
        )
        db.commit()
    typer.echo(f"Usuario {email} creado{' (administrador)' if admin else ''}.")


@cli.command("reset-mfa")
def reset_mfa(email: Annotated[str, typer.Option()]) -> None:
    """Quita la verificación en dos pasos y las passkeys (móvil perdido) y cierra sus sesiones."""
    with _db() as db:
        user = _find(db, email)
        user.totp_secret_encrypted = None
        user.totp_enabled_at = None
        user.totp_last_used_step = None
        db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
        db.execute(delete(PasskeyCredential).where(PasskeyCredential.user_id == user.id))
        sessions.revoke_all(db, user.id)
        db.commit()
    typer.echo(f"Segundo factor de {email} eliminado: lo configurará al volver a entrar.")


@cli.command("set-password")
def set_password(email: Annotated[str, typer.Option()]) -> None:
    """Cambia la contraseña de un usuario y cierra sus sesiones."""
    password = typer.prompt("Nueva contraseña", hide_input=True, confirmation_prompt=True)
    try:
        passwords.validate_new_password(password)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    with _db() as db:
        user = _find(db, email)
        user.password_hash = passwords.hash_password(password)
        user.failed_login_attempts = 0
        user.locked_until = None
        sessions.revoke_all(db, user.id)
        db.commit()
    typer.echo(f"Contraseña de {email} cambiada.")


@cli.command("list-users")
def list_users() -> None:
    """Lista los usuarios."""
    with _db() as db:
        for user in db.scalars(select(User).order_by(User.created_at)):
            flags = [
                "admin" if user.is_admin else "",
                "2FA" if user.has_totp else "sin 2FA",
                "" if user.is_active else "desactivado",
            ]
            typer.echo(f"{user.email}  {user.display_name}  [{', '.join(f for f in flags if f)}]")


@cli.command("sync-reference-values")
def sync_reference_values() -> None:
    """Añade los valores de referencia que falten (ITP, AJD, escalas…); no toca los que ya hay."""
    with _db() as db:
        added = reference.sync(db)
    typer.echo(f"Valores de referencia añadidos: {added}.")


@cli.command("summary")
def summary() -> None:
    """Resumen para comparar dos bases (p. ej. producción y una copia restaurada): filas por
    tabla y, por usuario, movimientos, saldo de las cuentas y patrimonio neto de hoy."""
    from sqlalchemy import func, text

    from app import clock
    from app.db import Base
    from app.models.transactions import Transaction
    from app.networth import NetWorthBook

    with _db() as db:
        typer.echo("Tablas")
        for table in sorted(Base.metadata.tables):
            count = db.scalar(text(f'SELECT count(*) FROM "{table}"'))  # noqa: S608  # own names
            typer.echo(f"  {table}: {count}")
        typer.echo("Usuarios")
        today = clock.today()
        for user in db.scalars(select(User).order_by(User.email)):
            movements = db.scalar(
                select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id)
            )
            worth = NetWorthBook(db, user, today).at(today)
            typer.echo(
                f"  {user.email}: {movements} movimientos · cuentas {worth.accounts:.2f} · "
                f"inversiones {worth.investments:.2f} · préstamos {worth.debts:.2f} · "
                f"patrimonio {worth.total:.2f}"
            )


if __name__ == "__main__":
    cli()
