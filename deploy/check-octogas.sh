#!/usr/bin/env bash
# Snapshot of how octogas.es responds, to compare before and after touching the VPS (RNF-18).
#   ./check-octogas.sh > antes.txt ; (deploy) ; ./check-octogas.sh > despues.txt ; diff antes.txt despues.txt
set -uo pipefail

for url in https://octogas.es https://www.octogas.es; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url")
  echo "$url -> HTTP $code"
done

host=octogas.es
expiry=$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null \
  | openssl x509 -noout -enddate 2>/dev/null)
echo "certificado $host: ${expiry:-no se pudo leer}"

echo "contenedores en marcha (todos los proyectos):"
docker ps --format '  {{.Names}}  {{.Status}}' | sort
