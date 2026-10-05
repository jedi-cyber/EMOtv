#!/bin/sh
# Arranque de la API en Docker: espera a PostgreSQL, migra, verifica pesos y
# lanza uvicorn. No abre ninguna cámara: el análisis llega por WebSocket.
set -eu

if [ "$#" -gt 0 ]; then
    # Permite ejecutar comandos puntuales con la misma imagen (servicio models).
    exec "$@"
fi

echo "Esperando a PostgreSQL..."
python - <<'EOF'
import time
from sqlalchemy import create_engine, text
from emotv.config import get_database_url

engine = create_engine(get_database_url(), pool_pre_ping=True)
for attempt in range(60):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("PostgreSQL no respondió en 60 segundos")
engine.dispose()
EOF

echo "Aplicando migraciones..."
alembic upgrade head

echo "Verificando pesos de modelos..."
python scripts/download_models.py --check

echo "Iniciando API EMOtv..."
exec uvicorn emotv.interfaces.web.app:app --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips="*"
