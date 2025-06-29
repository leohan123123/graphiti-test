#!/bin/bash

# Navigate to the directory where docker-compose.yml is located (project root)
# This assumes the script is run from the project root or the script navigates correctly.
# If this script is in a 'scripts' subdirectory, it needs to go up one level.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_ROOT" || exit

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Docker does not seem to be running, please start Docker and try again."
  exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f docker-compose.yml ]; then
    echo "docker-compose.yml not found in the project root!"
    exit 1
fi

echo "Building and starting all services..."

# Pull latest images for base services like neo4j (optional, but good practice)
docker-compose pull neo4j

# Build and start all services in detached mode
docker-compose up --build -d

if [ $? -eq 0 ]; then
  echo "All services started successfully."
  echo "Backend should be accessible on http://localhost:8000 (or your configured port)"
  echo "Frontend should be accessible on http://localhost (or your configured port)"
  echo "Neo4j Browser should be accessible on http://localhost:7474"
  echo "To see logs, run: docker-compose logs -f"
  echo "To stop services, run: docker-compose down"
else
  echo "There was an error starting the services. Check the output above."
  echo "You can try running 'docker-compose up --build' without '-d' to see live logs."
fi
