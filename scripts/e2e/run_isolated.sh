#!/usr/bin/env bash
# Ejecuta las pruebas e2e contra el stack aislado de docker-compose.e2e.yml.
#
#   bash scripts/e2e/run_isolated.sh                 # todas las pruebas
#   bash scripts/e2e/run_isolated.sh e2e/auth.spec.ts
#
# 1. Levanta (o reutiliza) el proyecto "emotv-e2e" con su propia base de datos.
# 2. Genera una contraseña temporal para la cuenta de administración de pruebas
#    (la crea si no existe) y reinicia su segundo factor. global-setup.ts la
#    cambia por una aleatoria y configura la aplicación autenticadora en
#    memoria. Nada de eso se escribe en archivos ni en la terminal.
# 3. Lanza Playwright con E2E_BASE_URL apuntando al stack aislado y el n8n falso
#    activado.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${E2E_ENV_FILE:-.env.docker}"
PORT="${E2E_WEB_PORT:-8081}"
ADMIN_EMAIL="${E2E_ADMIN_EMAIL:-e2e-admin@emotv.local}"
BASE_URL="http://localhost:${PORT}"
compose=(docker compose -p emotv-e2e --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.e2e.yml)

mask() { if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::add-mask::$1"; fi; }

if [ "${E2E_SKIP_UP:-0}" != "1" ]; then
  "${compose[@]}" up -d --build
fi
# La primera vez el servicio models descarga pesos y mide el benchmark: puede tardar.
for _ in $(seq 1 180); do
  curl -fsS -o /dev/null "$BASE_URL/health" && break
  sleep 5
done
curl -fsS -o /dev/null "$BASE_URL/health" || { echo "El stack e2e no respondió en $BASE_URL/health." >&2; exit 1; }

output="$("${compose[@]}" exec -T api python scripts/security/reset_admin_password.py --email "$ADMIN_EMAIL" 2>&1)" \
  || output="$("${compose[@]}" exec -T api python scripts/security/create_admin.py --email "$ADMIN_EMAIL" --force 2>&1)" \
  || { echo "No se pudo preparar la cuenta de administración de pruebas." >&2; exit 1; }
temporary="$(printf '%s\n' "$output" | sed -n 's/^Contraseña temporal: //p')"
[ -n "$temporary" ] || { echo "El script de administración no devolvió una contraseña temporal." >&2; exit 1; }
mask "$temporary"
# Sin clave conocida: en el primer ingreso global-setup.ts configura la aplicación.
"${compose[@]}" exec -T api python scripts/security/reset_mfa.py --email "$ADMIN_EMAIL" >/dev/null \
  || { echo "No se pudo reiniciar el segundo factor de la cuenta de pruebas." >&2; exit 1; }

cd web
E2E_BASE_URL="$BASE_URL" E2E_ADMIN_EMAIL="$ADMIN_EMAIL" E2E_ADMIN_PASSWORD="$temporary" E2E_FAKE_N8N=1 \
  npx playwright test "$@"
