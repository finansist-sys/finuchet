#!/bin/sh
# Runs once, on the first start of an empty database volume.
# The application connects as a non-superuser role that owns only this database.
set -eu

case "$APP_DB_PASSWORD" in
  *[!A-Za-z0-9_-]* | "") echo "APP_DB_PASSWORD must be non-empty and use only A-Z a-z 0-9 _ -" >&2; exit 1 ;;
esac

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE ROLE finuchet_app LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
	ALTER DATABASE "${POSTGRES_DB}" OWNER TO finuchet_app;
	ALTER SCHEMA public OWNER TO finuchet_app;
	REVOKE ALL ON DATABASE "${POSTGRES_DB}" FROM PUBLIC;
	GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO finuchet_app;
EOSQL
