#!/bin/bash
# Start the ARQ background worker in the background
arq app.workers.main.WorkerSettings &

uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
