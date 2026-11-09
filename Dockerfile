# Build the React application into the backend's static directory.
FROM node:20-slim AS frontend-build
WORKDIR /workspace
COPY backend ./backend
COPY frontend/package.json ./frontend/package.json
RUN cd frontend && npm install --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && npm run build

# Build the Python application image.
FROM python:3.11-slim AS application
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY --from=frontend-build /workspace/backend/app/static/spa ./backend/app/static/spa

WORKDIR /app/backend
EXPOSE 10000
CMD ["sh", "-c", "flask --app run.py init-db && exec gunicorn run:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120"]
