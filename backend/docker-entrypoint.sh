#!/bin/sh
# Apply pending database migrations, then start the API.
set -eu

alembic upgrade head
exec "$@"
