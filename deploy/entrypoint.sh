#!/bin/bash
set -e

echo "[VPR-Worker] Initializing storage directories at ${DATA_DIR:-/app/data}..."
mkdir -p "${DATA_DIR:-/app/data}/markdown"
mkdir -p "${DATA_DIR:-/app/data}/downloads"
mkdir -p "${DATA_DIR:-/app/data}/temp"

echo "[VPR-Worker] Starting auto-cleanup background daemon (TTL: ${CLEANUP_MINUTES:-10}m)..."
python3 /app/cleanup_daemon.py &
CLEANUP_PID=$!

echo "[VPR-Worker] Auto-cleanup daemon running with PID ${CLEANUP_PID}."
echo "[VPR-Worker] Container ready for manual research tasks & local MCP execution."

trap "kill ${CLEANUP_PID} 2>/dev/null || true; exit 0" SIGTERM SIGINT

tail -f /dev/null
