#!/bin/bash

echo "==============================================="
echo "   LEXSECURE STARTUP SCRIPT"
echo "==============================================="

PROJECT_ROOT=$(pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

LOCK_FILE="$PROJECT_ROOT/.start.pid"
if [ -f "$LOCK_FILE" ] && kill -0 "$(cat "$LOCK_FILE" 2>/dev/null)" 2>/dev/null; then
  echo "LexSecure is already running (supervisor PID $(cat "$LOCK_FILE"))."
  echo "Stop it first, or run: kill $(cat "$LOCK_FILE")"
  exit 1
fi
echo $$ > "$LOCK_FILE"

for port in 8000 5173; do
  stale_pids=$(lsof -t -nP -iTCP:$port -sTCP:LISTEN 2>/dev/null)
  if [ -n "$stale_pids" ]; then
    echo "  Stopping stale process(es) on port $port (PIDs: $stale_pids)"
    kill $stale_pids 2>/dev/null
    sleep 1
    still_up=$(lsof -t -nP -iTCP:$port -sTCP:LISTEN 2>/dev/null)
    if [ -n "$still_up" ]; then
      kill -9 $still_up 2>/dev/null
      sleep 1
    fi
  fi
done

echo "[1/2] Starting FastAPI Backend on port 8000..."

PGBIN="/Applications/Postgres.app/Contents/Versions/16/bin"
PGDATA_DIR="$BACKEND_DIR/.pgdata"
DB_PORT="55432"
if [ -x "$PGBIN/pg_ctl" ] && [ -d "$PGDATA_DIR" ]; then
  if ! "$PGBIN/pg_ctl" -D "$PGDATA_DIR" status >/dev/null 2>&1; then
    echo "  Starting local PostgreSQL 16 on port $DB_PORT..."
    "$PGBIN/pg_ctl" -D "$PGDATA_DIR" -l "$PGDATA_DIR/server.log" \
      -o "-p $DB_PORT -k /tmp" start >/dev/null 2>&1
    sleep 2
  fi
  if "$PGBIN/pg_ctl" -D "$PGDATA_DIR" status >/dev/null 2>&1; then
    echo "  PostgreSQL is ready on 127.0.0.1:$DB_PORT"
  else
    echo "  WARNING: PostgreSQL did not start; see $PGDATA_DIR/server.log"
  fi
fi

cd "$BACKEND_DIR"
source venv/bin/activate
(
  failures=0
  while true; do
    stale=$(lsof -t -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null)
    if [ -n "$stale" ]; then
      kill $stale 2>/dev/null
      sleep 1
      still_up=$(lsof -t -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null)
      if [ -n "$still_up" ]; then
        kill -9 $still_up 2>/dev/null
        sleep 1
      fi
    fi
    started=$(date +%s)
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    code=$?
    runtime=$(( $(date +%s) - started ))
    if [ "$runtime" -lt 5 ]; then
      failures=$((failures + 1))
    else
      failures=0
    fi
    if [ "$failures" -ge 5 ]; then
      echo "  [backend] failed to start 5 times in a row — giving up (port in use?)."
      break
    fi
    echo "  [backend] exited with code $code — restarting in 2s..."
    sleep 2
  done
) &
BACKEND_PID=$!

echo "[2/2] Starting React Frontend on port 5173..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo "==============================================="
echo " Services are starting up!"
echo " "
echo " - Backend API: http://localhost:8000/docs"
echo " - Frontend UI: http://localhost:5173"
echo " "
echo " Press Ctrl+C to stop all services."
echo "==============================================="

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  pkill -P "$BACKEND_PID" 2>/dev/null
  rm -f "$LOCK_FILE"
  exit 0
}
trap cleanup INT TERM
wait $BACKEND_PID $FRONTEND_PID
