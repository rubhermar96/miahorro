#!/bin/sh
# Apply pending database migrations and add missing reference values, then start the API.
set -eu

alembic upgrade head
python -m app.cli sync-reference-values
exec "$@"
