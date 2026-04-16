#!/bin/bash
# YugabyteDB Entrypoint Script
# This script starts YugabyteDB with advertise_address set to 0.0.0.0
# and creates the query_analyzer database
#
# Note: The entrypoint is not used in compose.yml currently, but kept for reference.
# Instead, we use a command-line approach with --advertise_address=0.0.0.0

set -e

echo "[ENTRYPOINT] Starting YugabyteDB..."
# Start in background so we can monitor it
bin/yugabyted start --daemon=false --advertise_address=0.0.0.0 &
YUGABYTE_PID=$!

# Wait for YSQL to be ready
echo "[ENTRYPOINT] Waiting for YSQL to be ready..."
for i in {1..60}; do
    if bin/ysqlsh -U yugabyte -d yugabyte -c "\dt" >/dev/null 2>&1; then
        echo "[ENTRYPOINT] YSQL is ready!"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "[ENTRYPOINT] ERROR: YSQL not ready after 60 seconds"
        kill $YUGABYTE_PID || true
        exit 1
    fi
    echo "[ENTRYPOINT] Attempt $i/60: Waiting for YSQL..."
    sleep 1
done

# Create query_analyzer database
echo "[ENTRYPOINT] Creating query_analyzer database..."
bin/ysqlsh -U yugabyte -d yugabyte -c "CREATE DATABASE query_analyzer;" 2>/dev/null || echo "[ENTRYPOINT] Database may already exist"

echo "[ENTRYPOINT] YugabyteDB initialization complete!"
echo "[ENTRYPOINT] Keeping yugabyted process running in foreground..."

# Keep the process running in foreground
wait $YUGABYTE_PID
