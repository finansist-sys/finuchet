#!/bin/sh
# Runs once, on the first start of an empty database volume.
# The application connects as a non-superuser role that owns only this database.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE ROLE finuchet_app LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
	ALTER DATABASE "${POSTGRES_DB}" OWNER TO finuchet_app;
	ALTER SCHEMA public OWNER TO finuchet_app;
	REVOKE ALL ON DATABASE "${POSTGRES_DB}" FROM PUBLIC;
	GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO finuchet_app;
EOSQL
