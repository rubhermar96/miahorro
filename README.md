# MiAhorro

Plataforma de finanzas personales para España: cuentas, ingresos y gastos, préstamos, inversiones, objetivos de ahorro, presupuestos y calculadoras. Web instalable en el iPhone (PWA).

- Qué hace y por qué: [docs/requisitos.md](docs/requisitos.md)
- Orden de desarrollo: [docs/plan-mvp.md](docs/plan-mvp.md)
- Despliegue en la VPS: [deploy/README.md](deploy/README.md)

## Estructura

| Carpeta | Contenido |
|---|---|
| `backend/app` | API con FastAPI, SQLAlchemy 2 y Alembic (`backend/migrations`) |
| `backend/finance` | Cálculos financieros, independientes del framework |
| `frontend` | React + TypeScript + Vite, como PWA |
| `deploy` | Docker Compose de producción, plantillas del proxy, copias y restauración |
| `docs` | Requisitos y plan |

## Desarrollo local

Requisitos: Docker Desktop, Python 3.14 con [uv](https://docs.astral.sh/uv/) y Node 22.

```bash
# Base de datos (incluye la de tests)
docker compose up -d db          # escucha en 127.0.0.1:15432

# API en http://localhost:8000 (documentación en /api/docs)
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python -m app.cli create-user --email tu@email.com --name "Tu nombre" --admin
uv run uvicorn app.main:app_factory --factory --reload

# App en http://localhost:5173 (redirige /api a la API)
cd frontend
npm ci
npm run dev
```

La plataforma completa, como en producción, en http://localhost:8080:

```bash
docker compose up -d --build --wait
```

## Probar en el iPhone desde local

Safari solo permite Face ID (passkeys) y el modo sin conexión con HTTPS. Para probar la plataforma local desde el iPhone se abre un túnel temporal de Cloudflare: es gratuito, no pide cuenta y se instala con `winget install Cloudflare.cloudflared`.

1. Con la plataforma en marcha (`docker compose up -d --build --wait`), abre el túnel y deja la ventana abierta:

   ```powershell
   & 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --no-autoupdate --url http://localhost:8080
   ```

2. Copia la dirección `https://….trycloudflare.com` que aparece y reinicia la API con ella, en modo producción:

   ```powershell
   $env:MIAHORRO_ENVIRONMENT='production'; $env:MIAHORRO_PUBLIC_URL='https://….trycloudflare.com'; docker compose up -d --wait api
   ```

3. Abre esa dirección en Safari en el iPhone.

Al terminar, pulsa Ctrl+C en el túnel y ejecuta `docker compose up -d --wait api` en una terminal nueva para volver a la configuración local.

- La dirección cambia cada vez que abres el túnel, y las passkeys quedan ligadas a ella. Bórralas después en Ajustes → Contraseñas del iPhone.
- Mientras el túnel está abierto, la app es accesible desde internet, aunque sigue pidiendo inicio de sesión. Úsalo solo con datos de prueba.

## Pruebas

```bash
cd backend  && uv run pytest                     # con la base de datos de Docker en marcha
cd frontend && npm test
cd frontend && npx playwright install webkit && npm run e2e   # con la plataforma completa en marcha
```

Antes de cada commit se ejecutan formateadores y linters (`cd backend && uv run pre-commit install` para activarlos). La integración continua de GitHub Actions ejecuta todo lo anterior en cada push.

## Convenciones

- **Código en inglés; textos para el usuario en español.** Los términos sin traducción clara (ITP, AJD, Euribor, IRPF) se mantienen tal cual.
- **Importes siempre en `Decimal`**, nunca en coma flotante. En la API viajan como texto (`"1234.56"`).
- **Redondeo al céntimo con `ROUND_HALF_UP`**, el redondeo comercial habitual. Se redondea solo al guardar o mostrar (ver `backend/finance/money.py`).
- **Ningún log contiene datos financieros.**
- **Datos de cada usuario siempre filtrados por su dueño.** Las consultas a modelos con `OwnedMixin` pasan por `app/ownership.py`, y un test comprueba que todo endpoint que no sea público exige sesión.
- **Escrituras con cabecera anti-CSRF.** El cliente de la API la añade solo (`X-MiAhorro-CSRF: 1`).
- **Cliente de la API generado.** Si cambia la API, ejecuta `uv run python -m app.export_openapi` en `backend` y `npm run api:generate` en `frontend`. Un test avisa si se olvida.
