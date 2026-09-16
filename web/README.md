# Frontend web de EMOtv

Aplicación React + TypeScript construida con Vite. Durante el desarrollo, Vite
redirige las rutas de API hacia FastAPI en `http://127.0.0.1:8000`.

```powershell
# Terminal 1, desde la raíz
.venv\Scripts\python.exe scripts/run_api.py

# Terminal 2
cd web
npm ci
npm run dev
```

Abre `http://localhost:5173`. Para usar otra dirección de API, copia
`.env.example` como `.env.local` y configura `VITE_API_URL`.

Comprobaciones locales:

```powershell
npm run typecheck
npm test
npm run build
```

La autenticación actual conserva el token solamente en `sessionStorage`. Antes
de un despliegue público debe evaluarse el cambio a cookies seguras `HttpOnly`.

## Acceso por roles

- `student`: analizador, actividades y sesiones propias;
- `psychologist`: seguimiento de estudiantes, sesiones y actividades;
- `admin`: usuarios, actividades y sesiones generales.

El frontend consulta `/auth/me` al iniciar, protege las rutas y cierra la sesión
cuando vence el JWT o cuando una petición autenticada devuelve `401`. Las rutas
de otro rol redirigen a una pantalla de acceso restringido. El endpoint de
estudiantes ya está disponible. Los estudiantes solo acceden a sus recursos;
los permisos institucionales por psicólogo asignado siguen pendientes.

## Actividades y cámara

El analizador recibe cámara propia con getUserMedia y envía JPEG por
`/ws/activity`. Incluye instrucciones, landmarks opcionales, progreso y limpieza
al cancelar, completar o abandonar. El servidor valida token, sesión y consentimiento.
El selector permite FER+ ONNX (predeterminado) o HardlyHumans ViT/PyTorch
(experimental). La inferencia ocurre en FastAPI: la RAM y CPU relevantes son las
del servidor, no las del navegador del estudiante. `GET /analysis/models`
requiere autenticación y muestra disponibilidad, advertencias o bloqueo según
informes de benchmark y recursos actuales. El WebSocket reevalúa antes de
cargar; no hay cambio silencioso de modelo ni conmutación durante la sesión.
Para instalar, medir y habilitar cada modelo, consultar
[modelos faciales y admisión](../docs/emotion-model-candidates.md).

Las actividades se administran por API y persisten en PostgreSQL. Antes de arrancar
FastAPI, aplicar las migraciones desde la raíz. Para dominios separados configurar
CORS/hosts/orígenes y el proxy de producción:
[preparación para producción](../docs/production-readiness.md).
