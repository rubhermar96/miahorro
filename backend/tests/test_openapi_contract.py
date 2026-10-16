from app.export_openapi import SCHEMA_PATH, build_schema, render_schema


def test_frontend_schema_is_up_to_date() -> None:
    """The frontend's typed client is generated from this file; it must match the API."""
    committed = SCHEMA_PATH.read_text(encoding="utf-8")

    assert committed == render_schema(build_schema()), (
        "frontend/src/api/openapi.json is outdated: run `uv run python -m app.export_openapi` "
        "and `npm run api:generate` in frontend/"
    )
