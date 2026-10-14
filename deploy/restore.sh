#!/usr/bin/env bash
# Restore an encrypted backup.
#   ./restore.sh --check <copia.dump.gpg>   restores into a temporary database, reports what it
#                                           contains and deletes it; production is not touched.
#   ./restore.sh <copia.dump.gpg>           REPLACES all MiAhorro data with the backup.
# The file may be local or come from the off-site copy (rclone copy <remote>/<file> .).
set -euo pipefail
cd "$(dirname "$0")"

set -a
# shellcheck source=/dev/null
source ./.env
set +a

compose() { docker compose -f compose.prod.yaml "$@"; }
psql_db() { compose exec -T db psql -U miahorro -v ON_ERROR_STOP=1 "$@"; }
decrypt() { gpg --batch --quiet --decrypt --passphrase-file "$BACKUP_PASSPHRASE_FILE" "$1"; }

mode=replace
if [[ "${1:-}" == "--check" ]]; then
  mode=check
  shift
fi
file=${1:?"Uso: ./restore.sh [--check] <copia.dump.gpg>"}
[[ -f "$file" ]] || { echo "No existe $file" >&2; exit 1; }

if [[ "$mode" == "check" ]]; then
  check_db=miahorro_restore_check
  psql_db -d postgres -c "DROP DATABASE IF EXISTS $check_db" -c "CREATE DATABASE $check_db"
  trap 'psql_db -d postgres -c "DROP DATABASE IF EXISTS $check_db" >/dev/null' EXIT
  decrypt "$file" | compose exec -T db pg_restore -U miahorro -d "$check_db" --no-owner
  echo "Copia descifrada y restaurada en una base temporal. Tablas y filas:"
  psql_db -d "$check_db" -c \
    "SELECT relname AS tabla, n_live_tup AS filas FROM pg_stat_user_tables ORDER BY relname"
  echo "Simulacro correcto. La base temporal se borra al salir."
  exit 0
fi

read -r -p "Se REEMPLAZARÁN todos los datos de MiAhorro con $file. Escribe 'restaurar': " answer
[[ "$answer" == "restaurar" ]] || { echo "Cancelado."; exit 1; }

./backup.sh  # safety copy of the current state first
compose stop api
decrypt "$file" | compose exec -T db pg_restore -U miahorro -d miahorro --clean --if-exists --no-owner
compose start api
echo "Restauración terminada."
