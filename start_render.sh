#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export PORT="${PORT:-10000}"
echo "[Atacarejo Insights] Start Render iniciado. PORT=$PORT"
echo "[Atacarejo Insights] Python: $(python --version)"
echo "[Atacarejo Insights] Diretório: $(pwd)"
echo "[Atacarejo Insights] Arquivos principais:"
ls -la app.py requirements.txt || true
python - <<'PY'
import app
print('[Atacarejo Insights] Preflight import OK')
with app.app.app_context():
    with app.app.test_client() as c:
        r = c.get('/health')
        print('[Atacarejo Insights] Preflight /health:', r.status_code, r.data.decode()[:200])
PY
exec gunicorn "app:app" \
  --bind "0.0.0.0:${PORT}" \
  --workers 1 \
  --threads 2 \
  --timeout 120 \
  --log-level info \
  --access-logfile - \
  --error-logfile -
