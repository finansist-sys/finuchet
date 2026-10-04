#!/bin/sh
# Daily database backup, kept for 7 days. Run from cron on the server, e.g.:
#   15 3 * * *  /opt/finuchet/deploy/backup.sh >/dev/null 2>&1
# Optional encryption: set AGE_RECIPIENT to an `age` public key (https://age-encryption.org).
# The database holds no Telegram IDs or names; ID_PEPPER is NOT included in backups.
set -eu
cd "$(dirname "$0")/.."

DIR="${BACKUP_DIR:-/var/backups/finuchet}"
umask 077
mkdir -p "$DIR"
FILE="$DIR/finuchet-$(date +%Y%m%d-%H%M).sql.gz"

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' | gzip -9 > "$FILE"

if [ -n "${AGE_RECIPIENT:-}" ]; then
  age -r "$AGE_RECIPIENT" -o "$FILE.age" "$FILE"
  rm -f "$FILE"
fi

find "$DIR" -name 'finuchet-*' -type f -mtime +7 -delete
