# Use python image and copy uv binary to it
FROM python:3.11-slim AS uv_installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
# --locked fails the build instead of silently re-resolving if pyproject.toml
# and uv.lock have drifted apart - every dependency actually installed is the
# one pinned in the lockfile, not whatever the resolver would pick today.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --locked --no-install-project

# Clean execution container
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Install necessary runtime dependencies (if any required by pg/redis usually covered, libpq maybe needed for asyncpg/psycopg2)
# Since we use asyncpg, it compiles wheels or uses binary wheels, but it's good practice to keep the image minimal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment
COPY --from=uv_installer /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY . /app

EXPOSE 8000
