# syntax=docker/dockerfile:1

# --- Stage 1: build the React frontend ---
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build        # -> /frontend/dist

# --- Stage 2: Python backend that also serves the built frontend ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
# config.py serves the app from <project_root>/frontend/dist (project_root = /app)
COPY --from=frontend /frontend/dist ./frontend/dist

WORKDIR /app/backend
EXPOSE 8017
# Shell form so ${PORT} is expanded; defaults to 8017 if PORT is unset.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8017}
