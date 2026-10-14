#!/usr/bin/env bash
# Create deploy/.env with fresh random secrets, and the backup passphrase file.
# Run once on the VPS. Refuses to overwrite existing files.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -e .env ]]; then
  echo "deploy/.env ya existe; no se sobrescribe." >&2
  exit 1
fi

random_hex() { openssl rand -hex "$1"; }

umask 077
sed \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(random_hex 24)|" \
  -e "s|^MIAHORRO_SECRET_KEY=.*|MIAHORRO_SECRET_KEY=$(random_hex 32)|" \
  .env.example > .env
echo "Creado deploy/.env"

passphrase_file=$(grep '^BACKUP_PASSPHRASE_FILE=' .env | cut -d= -f2-)
if [[ ! -e "$passphrase_file" ]]; then
  sudo install -d -m 700 -o "$(id -u)" -g "$(id -g)" "$(dirname "$passphrase_file")"
  random_hex 32 > "$passphrase_file"
  chmod 600 "$passphrase_file"
  echo "Creada la clave de las copias en $passphrase_file"
fi

cat <<EOF

IMPORTANTE: guarda ahora en tu gestor de contraseñas
  - el contenido de deploy/.env
  - la clave de las copias: $(cat "$passphrase_file")
Sin esa clave, las copias de seguridad no se pueden descifrar si la VPS se pierde.
EOF
