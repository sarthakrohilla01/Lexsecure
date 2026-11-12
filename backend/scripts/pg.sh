#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PGBIN="${PGBIN:-/Applications/Postgres.app/Contents/Versions/16/bin}"
PGDATA_DIR="${PGDATA_DIR:-$PROJECT_ROOT/backend/.pgdata}"
PORT="${PGPORT:-55432}"

if [ ! -x "$PGBIN/pg_ctl" ]; then
  echo "PostgreSQL binaries not found at $PGBIN"
  echo "Install Postgres.app (https://postgresapp.com) or use docker compose."
  exit 1
fi

if [ ! -d "$PGDATA_DIR" ]; then
  echo "Cluster not found at $PGDATA_DIR"
  echo "Create one with:"
  echo "  \"$PGBIN/initdb\" -D \"$PGDATA_DIR\" -U lexsecure --auth=trust -E UTF8 --locale=C"
  exit 1
fi

case "${1:-status}" in
  start)
    if "$PGBIN/pg_ctl" -D "$PGDATA_DIR" status >/dev/null 2>&1; then
      echo "PostgreSQL is already running."
    else
      "$PGBIN/pg_ctl" -D "$PGDATA_DIR" -l "$PGDATA_DIR/server.log" \
        -o "-p $PORT -k /tmp" start
      echo "PostgreSQL started on 127.0.0.1:$PORT"
    fi
    ;;
  stop)
    "$PGBIN/pg_ctl" -D "$PGDATA_DIR" stop -m fast
    ;;
  restart)
    "$PGBIN/pg_ctl" -D "$PGDATA_DIR" restart -m fast -l "$PGDATA_DIR/server.log" \
      -o "-p $PORT -k /tmp"
    ;;
  status)
    "$PGBIN/pg_ctl" -D "$PGDATA_DIR" status
    ;;
  psql)
    "$PGBIN/psql" -h 127.0.0.1 -p "$PORT" -U lexsecure -d lexsecure
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|psql}"
    exit 1
    ;;
esac
