#!/bin/bash
# Script to initialize the database with schema
# Usage: ./init_db.sh

set -e

echo "Initializing database schema..."

# Get database connection details from environment or use defaults
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-app_db}"
DB_USER="${DB_USER:-app_user}"
DB_PASSWORD="${DB_PASSWORD:-super_secret_password}"

# Export password for psql
export PGPASSWORD="$DB_PASSWORD"

# Check if running in Docker
if [ -f /.dockerenv ] || [ -n "$DOCKER_CONTAINER" ]; then
    # Running inside Docker - use direct psql
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f /db/schema.sql
else
    # Running on host - use docker exec
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    docker exec -i postgres psql -U "$DB_USER" -d "$DB_NAME" < "$SCRIPT_DIR/schema.sql"
fi

echo "Database schema initialized successfully!"

# Verify tables were created
if [ -f /.dockerenv ] || [ -n "$DOCKER_CONTAINER" ]; then
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\dt"
else
    docker exec postgres psql -U "$DB_USER" -d "$DB_NAME" -c "\dt"
fi
