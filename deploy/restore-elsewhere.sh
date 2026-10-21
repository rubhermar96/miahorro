#!/usr/bin/env bash
# Recovery drill on ANOTHER machine (RNF-07): restore an encrypted backup into a throwaway
# database, bring it up to the current code with the migrations and print the same summary as
# production, to compare. Needs only Docker, gpg and this repository; it leaves nothing behind.
#
#   ./restore-elsewhere.sh <copia.dump.gpg> <fichero-con-la-clave>
#
# In production, before the backup:  docker compose -f compose.prod.yaml exec api \
#   python -m app.cli summary > resumen-produccion.txt
# Then compare it with what this script prints (diff); the counts and totals must match.
set -euo pipefail
cd "$(dirname "$0")/.."

file=${1:?"Uso: ./restore-elsewhere.sh <copia.dump.gpg> <fichero-con-la-clave>"}
passphrase_file=${2:?"Falta el fichero con la clave de las copias"}
[[ -f "$file" ]] || { echo "No existe $file" >&2; exit 1; }
[[ -f "$passphrase_file" ]] || { echo "No existe $passphrase_file" >&2; exit 1; }

name=miahorro-drill-$$
password=$(openssl rand -hex 16 2>/dev/null || date +%s%N)
url="postgresql+psycopg://miahorro:$password@$name-db:5432/miahorro"
secret=$(printf 'drill-only-%064d' 0)

cleanup() {
  docker rm -f "$name-db" >/dev/null 2>&1 || true
  docker network rm "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Construyendo la imagen de la API…"
docker build --quiet --tag "$name-api" backend >/dev/null

docker network create "$name" >/dev/null
docker run --detach --name "$name-db" --network "$name" \
  -e POSTGRES_USER=miahorro -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=miahorro \
  postgres:18-alpine >/dev/null
until docker exec "$name-db" pg_isready -U miahorro -d miahorro >/dev/null 2>&1; do sleep 1; done
# The first answer can come before the database is fully up: give it a moment.
sleep 2

echo "Descifrando y restaurando $file…"
gpg --batch --quiet --decrypt --passphrase-file "$passphrase_file" "$file" \
  | docker exec -i "$name-db" pg_restore -U miahorro -d miahorro --no-owner

api() {
  docker run --rm --network "$name" --entrypoint "" \
    -e MIAHORRO_DATABASE_URL="$url" -e MIAHORRO_SECRET_KEY="$secret" \
    "$name-api" "$@"
}
echo "Aplicando las migraciones del código actual…"
api alembic upgrade head
echo
api python -m app.cli summary
echo
echo "Simulacro terminado. La base temporal se borra al salir."
docker image rm "$name-api" >/dev/null 2>&1 || true
