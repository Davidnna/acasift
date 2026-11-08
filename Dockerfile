# Build the React application with Node, then serve the generated assets from Flask.
FROM node:20-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json ./frontend/package.json
RUN cd frontend && npm install --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && npm run build

# Python application image.
FROM python:3.11-slim AS application
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /app/app/static/spa ./app/static/spa

EXPOSE 10000
CMD ["sh", "-c", "flask --app run.py init-db && exec gunicorn run:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120"]
