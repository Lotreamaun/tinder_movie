# Multi-stage build для Movie Tinder Bot

# Stage 1: Собираем фронтенд (React + Vite)
FROM node:18-alpine AS frontend-build

WORKDIR /app

COPY frontend/package*.json ./

RUN npm ci

COPY frontend/ .

RUN npm run build

# Stage 2: Собираем финальный контейнер с nginx и backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

# Устанавливаем nginx
RUN apt-get update && apt-get install -y \
    nginx \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости Python
COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Копируем backend код
COPY backend/ /app/

# Копируем собранный фронтенд в nginx
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Копируем nginx конфиг
COPY frontend/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Expose порты
EXPOSE 80 8000

# Стартовый скрипт
CMD sh -c "nginx -g 'daemon off;' & uvicorn app.main:app --host 0.0.0.0 --port 8000"