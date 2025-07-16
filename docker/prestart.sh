#!/bin/bash
set -e

echo "Running pre-start script..."

# Wait for database to be ready
echo "Waiting for database..."
python -c "
import time
import psycopg2
import os
from urllib.parse import urlparse

database_url = os.getenv('DATABASE_URL', os.getenv('DB_URL'))
if database_url:
    result = urlparse(database_url)
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )
            conn.close()
            print('Database is ready!')
            break
        except psycopg2.OperationalError:
            retry_count += 1
            print(f'Database not ready, waiting... ({retry_count}/{max_retries})')
            time.sleep(2)
    else:
        print('Database connection timeout!')
        exit(1)
"

# Run database migrations
echo "Running database migrations..."
if [ -f "alembic.ini" ]; then
    alembic upgrade head || echo "Migration failed or no migrations to run"
fi

# Create necessary directories
mkdir -p /app/logs /app/temp

echo "Pre-start script completed!"