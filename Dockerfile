# /Dockerfile (в корне)
# Этот файл используется только для сборки на Dockhost
# Реальная сборка идет через docker-compose.yml

FROM alpine:latest

RUN echo "Using docker-compose.yml for multi-container deployment"

# Dockhost будет использовать docker-compose up