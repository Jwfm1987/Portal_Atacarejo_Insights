#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export PORT="${PORT:-10000}"
echo "[Atacarejo Insights] Iniciando via start_render.sh com python app.py. PORT=$PORT"
python app.py
