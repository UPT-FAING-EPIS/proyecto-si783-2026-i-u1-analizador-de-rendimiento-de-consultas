#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MAX_WAIT=120
INTERVAL=5
ELAPSED=0

echo "⏳ Esperando que todos los servicios estén listos..."
echo ""

# Get total number of services
TOTAL_SERVICES=$(docker compose -f docker/compose.yml ps --services 2>/dev/null | wc -l)

while [ $ELAPSED -lt $MAX_WAIT ]; do
	# Count services that are healthy or up and running
	# Services with health checks must be healthy (contains "healthy")
	# Services without health checks just need to be up (Up [0-9]+ seconds)
	HEALTHY=$(docker compose -f docker/compose.yml ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null | tail -n +2 | grep -c 'healthy\|Up [0-9]' || echo 0)

	if [ "$HEALTHY" -eq "$TOTAL_SERVICES" ]; then
		echo "✅ ¡Todos los servicios están listos!"
		echo ""
		echo "🎉 Stack completamente operativo:"
		echo ""
		docker compose -f docker/compose.yml ps --format 'table {{.Names}}\t{{.Status}}'
		exit 0
	fi

	echo "⏳ [$ELAPSED/$MAX_WAIT] Aguardando... ($HEALTHY/$TOTAL_SERVICES servicios listos)"
	sleep $INTERVAL
	ELAPSED=$((ELAPSED + INTERVAL))
done

# Timeout reached
echo ""
echo "⏱️  TIMEOUT: No todos los servicios estuvieron listos después de $MAX_WAIT segundos"
echo ""
echo "Estado actual:"
docker compose -f docker/compose.yml ps --format 'table {{.Names}}\t{{.Status}}'
exit 1
