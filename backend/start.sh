#!/bin/bash

# Convert standard DATABASE_URL to async SQLAlchemy format if it exists
if [ ! -z "$DATABASE_URL" ]; then
  export DATABASE_ASYNC_URL=$(echo $DATABASE_URL | sed 's/postgres:\/\//postgresql+asyncpg:\/\//' | sed 's/postgresql:\/\//postgresql+asyncpg:\/\//')
fi

# Start the ARQ background worker in the background
arq app.workers.main.WorkerSettings &

uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
