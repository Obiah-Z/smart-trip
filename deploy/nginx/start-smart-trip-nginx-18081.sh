#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/obiah/Desktop/smart-trip"
CONF="$PROJECT_ROOT/deploy/nginx/smart-trip-local-18081.conf"
RUNTIME_DIR="/tmp/smart-trip-nginx"
PORT="18081"

mkdir -p \
  "$RUNTIME_DIR/proxy_temp" \
  "$RUNTIME_DIR/client_body_temp" \
  "$RUNTIME_DIR/fastcgi_temp" \
  "$RUNTIME_DIR/uwsgi_temp" \
  "$RUNTIME_DIR/scgi_temp"

if [ ! -f "$PROJECT_ROOT/frontend/dist/index.html" ]; then
  echo "frontend/dist/index.html not found. Run frontend build before starting Nginx." >&2
  exit 1
fi

nginx -p "$RUNTIME_DIR/" -c "$CONF" -t

if ss -ltn | awk '{print $4}' | grep -q "127.0.0.1:$PORT$"; then
  echo "Smart Trip Nginx is already listening on 127.0.0.1:$PORT."
  exit 0
fi

setsid nginx -p "$RUNTIME_DIR/" -c "$CONF" > "$RUNTIME_DIR/stdout.log" 2>&1 < /dev/null &

for _ in 1 2 3 4 5; do
  if curl -fsS -I "http://127.0.0.1:$PORT/" >/dev/null; then
    echo "Smart Trip Nginx started on 127.0.0.1:$PORT."
    exit 0
  fi
  sleep 0.5
done

echo "Smart Trip Nginx did not become ready. Check $RUNTIME_DIR/error.log." >&2
exit 1
