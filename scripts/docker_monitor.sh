#!/bin/bash

# Navigate to the directory where docker-compose.yml is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_ROOT" || exit

echo "=== Docker Services Monitor ==="
echo "Timestamp: $(date)"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker does not seem to be running. Please start Docker and try again."
  exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f docker-compose.yml ]; then
    echo "❌ docker-compose.yml not found in the project root!"
    exit 1
fi

echo "--- Services Status (docker-compose ps) ---"
docker-compose ps
echo ""

echo "--- Container Resource Usage (docker stats - one snapshot) ---"
# Show stats for containers managed by this docker-compose.yml
# Get container names/IDs from docker-compose ps
COMPOSE_PROJECT_NAME=$(basename "$PROJECT_ROOT") # Docker Compose typically names containers projectname_servicename_1
# Attempt to get container IDs for services defined in the compose file
CONTAINER_IDS=$(docker-compose ps -q 2>/dev/null)

if [ -n "$CONTAINER_IDS" ]; then
    docker stats --no-stream $CONTAINER_IDS
else
    echo "Could not retrieve container IDs. Skipping docker stats."
    # Fallback or alternative if above fails consistently
    # docker stats --no-stream $(docker ps --filter label=com.docker.compose.project="$COMPOSE_PROJECT_NAME" -q)
fi
echo ""

echo "--- Health Checks (as defined in docker-compose.yml) ---"
SERVICES=("backend" "frontend" "neo4j") # Services defined in docker-compose.yml

for SERVICE_NAME in "${SERVICES[@]}"; do
    # Construct the expected container name. Default is project_service_1
    # For project names with special characters or very long names, this might need adjustment.
    # A more robust way is to use docker-compose ps -q <service_name>
    CONTAINER_ID=$(docker-compose ps -q "$SERVICE_NAME" 2>/dev/null)

    if [ -z "$CONTAINER_ID" ]; then
        echo "⚠️ Could not find container for service: $SERVICE_NAME. It might not be running or defined."
        continue
    fi

    # Get the full container name using the ID, useful if multiple replicas exist (though not in this setup)
    FULL_CONTAINER_NAME=$(docker inspect --format='{{.Name}}' "$CONTAINER_ID" | sed 's/^\///')


    HEALTH_STATUS=$(docker inspect --format='{{json .State.Health}}' "$CONTAINER_ID" 2>/dev/null)

    if [ -z "$HEALTH_STATUS" ] || [ "$HEALTH_STATUS" == "null" ]; then
        echo "ጤ Health status not available or not configured for $FULL_CONTAINER_NAME ($SERVICE_NAME)."
    else
        STATUS=$(echo "$HEALTH_STATUS" | grep -o '"Status":"[^"]*"' | sed 's/"Status":"//;s/"//')
        # LOG=$(echo "$HEALTH_STATUS" | jq -r '.Log[-1].Output' 2>/dev/null || echo "No log details") # Requires jq
        # For simplicity without jq:
        LOG_OUTPUT=$(docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' "$CONTAINER_ID" | tail -n 1 | sed 's/\n//g; s/\r//g')


        case "$STATUS" in
          "healthy")
            echo "✅ $FULL_CONTAINER_NAME ($SERVICE_NAME) is healthy."
            ;;
          "unhealthy")
            echo "❌ $FULL_CONTAINER_NAME ($SERVICE_NAME) is unhealthy."
            [ -n "$LOG_OUTPUT" ] && echo "   Last health log: $LOG_OUTPUT"
            ;;
          "starting")
            echo "⏳ $FULL_CONTAINER_NAME ($SERVICE_NAME) is starting..."
            ;;
          *)
            echo "❓ Unknown health status for $FULL_CONTAINER_NAME ($SERVICE_NAME): $STATUS"
            [ -n "$LOG_OUTPUT" ] && echo "   Last health log: $LOG_OUTPUT"
            ;;
        esac
    fi
done
echo ""

echo "--- Log Tailing ---"
echo "To view live logs for all services, run: docker-compose logs -f"
echo "To view logs for a specific service (e.g., backend), run: docker-compose logs -f backend"
echo ""

echo "=== Monitoring Script Finished ==="
