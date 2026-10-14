#!/usr/bin/env bash
# Deploy the current branch on the VPS: update the code, back up, rebuild and restart MiAhorro.
# Only touches MiAhorro's own containers, images and volumes (RNF-18).
set -euo pipefail
cd "$(dirname "$0")"

compose() { docker compose -f compose.prod.yaml "$@"; }
port=$(grep '^MIAHORRO_HTTP_PORT=' .env | cut -d= -f2-)

echo "==> Actualizando el código"
git -C .. pull --ff-only

if [[ -n "$(compose ps --status running --quiet db 2>/dev/null)" ]]; then
  echo "==> Copia de seguridad antes de desplegar"
  ./backup.sh
fi

echo "==> Construyendo imágenes"
compose build --pull

echo "==> Arrancando (las migraciones se aplican al iniciar la API)"
compose up -d --remove-orphans --wait

echo "==> Comprobando el servicio"
curl -fsS "http://127.0.0.1:${port}/api/health"
echo

# Remove only MiAhorro's dangling images; other projects on this VPS are left alone.
docker image prune -f --filter "label=com.miahorro.project=miahorro" >/dev/null
compose ps
