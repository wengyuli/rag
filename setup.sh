#!/bin/sh
set -eu
cd "$(dirname "$0")"
command -v docker >/dev/null
command -v python3 >/dev/null
command -v curl >/dev/null
python3 prepare.py
docker compose config --quiet
docker compose up -d db ollama
attempt=0
until docker compose exec -T ollama ollama list >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        printf '%s\n' 'Ollama did not become ready; inspect docker compose logs ollama.' >&2
        exit 1
    fi
    sleep 2
done
docker compose exec -T ollama ollama pull qwen2.5:3b
docker compose exec -T ollama ollama pull bge-m3
python3 download_models.py
docker compose up -d --build
printf '%s\n' "Web: http://127.0.0.1:${WEB_PORT:-8090}" 'Login: admin / admin123' 'The backend may need a moment to finish loading the reranker.'
