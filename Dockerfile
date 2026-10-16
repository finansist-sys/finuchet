# Single-container image (Railway and similar platforms): builds the Mini App and serves it
# together with the API and Telegram webhook from one FastAPI process.
# For the multi-container setup with Caddy and Postgres on your own server see compose.yml.

FROM node:22-alpine AS webapp
WORKDIR /w
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY webapp/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install --require-virtualenv -r /tmp/requirements.txt

FROM python:3.12-slim-bookworm
ENV PATH=/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=prod \
    BOT_MODE=serverless \
    STATIC_DIR=/srv/webapp
RUN groupadd --system app && useradd --system --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=deps /venv /venv
WORKDIR /srv/backend
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=webapp /w/dist /srv/webapp
USER app
EXPOSE 8000
# The platform sets $PORT. The schema is migrated and Telegram configured on the first /healthz call.
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log --no-server-header"]
