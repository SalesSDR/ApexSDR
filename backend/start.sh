#!/bin/bash
# Start the ARQ background worker in the background
arq app.workers.main.WorkerSettings &

# Start the Gunicorn web server in the foreground
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
