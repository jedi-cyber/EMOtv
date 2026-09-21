# EMOtv

EMOtv es un sistema experimental de apoyo al bienestar emocional para la
Facultad de Psicología de la Universidad Nacional Hermilio Valdizán. Combina
visión por computadora y actividades guiadas mediante posturas corporales.

El sistema es una herramienta de apoyo y seguimiento. No realiza diagnósticos
ni sustituye la evaluación de un profesional de psicología.

## Estado actual

La base funcional incluye:

- captura de webcam con OpenCV;
- detección facial con YuNet;
- clasificación básica de expresiones emocionales con ONNX Runtime;
- estimación corporal con MediaPipe Pose Landmarker;
- representación de landmarks independiente de MediaPipe;
- dibujo de puntos y conexiones corporales;
- validación de `arms_up`, `arms_open`, `arms_forward`, `hands_on_hips` y `squat`;
- catálogo de actividades en memoria o PostgreSQL mediante un adaptador;
- estabilización de emociones a partir de múltiples predicciones;
- recomendación local de actividades a partir de la emoción estabilizada;
- controlador del flujo emoción → actividad → postura → ejercicio;
- ejercicio temporizado con estados `incorrect`, `holding` y `completed`;
- progreso normalizado y barra visual en tiempo real;
- sesiones estructuradas con estados y timestamps;
- persistencia desacoplada mediante `SessionRepository`;
- repositorio local `InMemorySessionRepository`;
- persistencia PostgreSQL con SQLAlchemy y migraciones Alembic;
- usuarios, estudiantes, roles, consentimiento y autenticación OAuth2/JWT;
- API de sesiones con consultas por ID y por estudiante;
- endpoints de estudiantes, usuarios y consentimientos con acceso por rol;
- administración autenticada de actividades persistidas en PostgreSQL;
- frontend React, TypeScript y Vite con autenticación, actividades y sesiones;
- cámara del navegador y análisis remoto por WebSocket autenticado;
- FER+ ONNX como modelo predeterminado mediante catálogo, contrato y fábrica;
- HardlyHumans ViT/PyTorch como alternativa experimental opcional;
- selector web por tipo de modelo y admisión `SUPPORTED`/`WARNING`/`BLOCKED`
  según informe de rendimiento y recursos del servidor;
- pruebas de componentes, accesibilidad básica y configuración CORS/Host/Origin;
- pruebas unitarias y de integración para el flujo implementado.

## Inicio rápido

Requiere Python 3.12. El frontend usa Node.js reciente; la cámara web requiere
HTTPS o localhost. Los scripts locales usan una webcam compatible con OpenCV.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/poses/download_pose_model.py
python scripts/emotion/download_emotion_model.py
```

Pruebas disponibles:

```powershell
python scripts/poses/run_pose_detection_test.py
python scripts/poses/run_posture_test.py
python scripts/poses/run_exercise_test.py
python scripts/run_emotional_exercise_test.py
python scripts/run_session_test.py
```

En las ventanas de prueba, `Q` finaliza la ejecución. En la prueba del
ejercicio, `R` reinicia el estado después de completarlo o durante un intento.

Para ejecutar las pruebas automatizadas:

```powershell
python -m pytest
```

Para iniciar el frontend en desarrollo, ejecuta FastAPI y Vite en terminales
separadas:

```powershell
# Configurar .env y aplicar migraciones antes de iniciar.
python -m alembic upgrade head
python -m uvicorn emotv.interfaces.web.app:app --reload
# En otra terminal:
cd web
npm ci
npm run dev
```

Aplicar el esquema PostgreSQL configurado en `.env`:

```powershell
python -m alembic upgrade head
python -m alembic current
```

La ejecución con unittest cubre solo los casos escritos con esa biblioteca,
no la suite completa de pytest:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Documentación

- [Primeros pasos](docs/primeros-pasos.md)
- [Arquitectura](docs/architecture.md)
- [Etapa de reconocimiento corporal](docs/pose-estimation.md)
- [MVP de actividad emocional](docs/emotional-activity-mvp.md)
- [Sesiones y persistencia](docs/sessions.md)
- [API HTTP](docs/api.md)
- [Frontend web](web/README.md)
- [Privacidad y gobierno de datos](docs/privacy-data-governance.md)
- [API administrativa](docs/administrative-api.md)
- [Modelo emocional predeterminado](docs/emotion-models.md)
- [Modelos faciales, mediciones y admisión](docs/emotion-model-candidates.md)
- [Línea base FER+](docs/ferplus-baseline.md)
- [Preparación para producción](docs/production-readiness.md)
- [Plan de selección adaptativa de modelos](docs/adaptive-emotion-models-plan.md)
- [Modelos y pesos](models/README.md)
- [Scripts disponibles](scripts/README.md)
- [Pruebas](tests/README.md)

## Próximas etapas

1. Repetir las mediciones de ambos modelos en el servidor de despliegue y
   configurar informes vigentes; medir también carga, pipeline y concurrencia.
2. Evaluar calidad de reconocimiento sobre datos con permiso y protocolo común;
   las métricas publicadas de modelos distintos no permiten ordenar su precisión.
3. Calibrar los umbrales de admisión y añadir control de concurrencia; actualmente
   la evaluación protege nuevos inicios, no supervisa sesiones activas.
4. Validar cámaras reales y calibrar actividades con Psicología.
5. Resolver las puertas de salida de privacidad y seguridad antes de producción.
