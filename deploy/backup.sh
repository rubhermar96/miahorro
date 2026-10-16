#!/usr/bin/env bash
# Encrypted database backup (RF-IMP-05, RNF-07): pg_dump -> gpg (AES-256) -> local folder
# and, if configured, an off-site copy with rclone. Keeps 30 days in both places.
# Cron (daily at 03:30):  30 3 * * * /opt/miahorro/deploy/backup.sh >> /var/log/miahorro-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"

set -a
# shellcheck source=/dev/null
source ./.env
set +a

: "${BACKUP_DIR:?}" "${BACKUP_PASSPHRASE_FILE:?}"
retention_days=30
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_DIR/miahorro-$stamp.dump.gpg"

umask 077
mkdir -p "$BACKUP_DIR"

# Write to a temporary name first so a failed dump never looks like a valid backup.
docker compose -f compose.prod.yaml exec -T db pg_dump -U miahorro -d miahorro --format=custom \
  | gpg --batch --yes --symmetric --cipher-algo AES256 \
      --passphrase-file "$BACKUP_PASSPHRASE_FILE" --output "$target.partial"
mv "$target.partial" "$target"
echo "$(date -Is) copia creada: $target ($(du -h "$target" | cut -f1))"

find "$BACKUP_DIR" -name 'miahorro-*.dump.gpg' -mtime +"$retention_days" -delete

if [[ -n "${BACKUP_RCLONE_REMOTE:-}" ]]; then
  rclone copy "$target" "$BACKUP_RCLONE_REMOTE"
  rclone delete --min-age "${retention_days}d" --include 'miahorro-*.dump.gpg' "$BACKUP_RCLONE_REMOTE"
  echo "$(date -Is) copia externa subida a $BACKUP_RCLONE_REMOTE"
fi
