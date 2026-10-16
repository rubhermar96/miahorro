"""Write the OpenAPI schema used to generate the frontend's typed API client.

Usage: uv run python -m app.export_openapi
"""

import json
from pathlib import Path
from typing import Any

from app.config import Settings
from app.main import create_app

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"

# Placeholder settings: building the schema never connects to the database.
_EXPORT_SETTINGS = Settings(
    environment="development",
    database_url="postgresql+psycopg://export:export@localhost:5432/export",
    secret_key="export-only-not-a-real-secret-key-000000",  # noqa: S106
    _env_file=None,
)


def build_schema() -> dict[str, Any]:
    return create_app(_EXPORT_SETTINGS).openapi()


def render_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    # LF on every platform, as stored in git.
    SCHEMA_PATH.write_text(render_schema(build_schema()), encoding="utf-8", newline="\n")
    print(f"OpenAPI schema written to {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
