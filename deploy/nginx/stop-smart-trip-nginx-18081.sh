#!/usr/bin/env bash
set -euo pipefail

CONF="/home/obiah/Desktop/smart-trip/deploy/nginx/smart-trip-local-18081.conf"
RUNTIME_DIR="/tmp/smart-trip-nginx"
PID_FILE="$RUNTIME_DIR/nginx.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "No Smart Trip Nginx pid file found at $PID_FILE."
  exit 0
fi

nginx -p "$RUNTIME_DIR/" -c "$CONF" -s quit
echo "Smart Trip Nginx stop signal sent."
