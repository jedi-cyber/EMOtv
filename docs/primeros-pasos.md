# Primeros pasos

## Requisitos

- Windows con PowerShell (los comandos pueden adaptarse a otros sistemas).
- Python 3.12.
- Git.
- Node.js reciente y npm para el frontend.
- Webcam compatible con OpenCV.

No se requiere CUDA: MediaPipe puede ejecutar el modelo Lite en CPU.

## Preparar el entorno

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Es importante instalar las dependencias después de activar `.venv`. Ejecutar
el script con otro intérprete puede producir `ModuleNotFoundError` aunque el
paquete esté instalado globalmente.

Comprueba el intérprete activo con:

```powershell
python -c "import sys; print(sys.executable)"
```

## Descargar los modelos

Los pesos no están incluidos en Git. Para pose corporal:

```powershell
python scripts/poses/download_pose_model.py
```

El archivo esperado es:

```text
models/weights/pose/pose_landmarker_lite.task
```

Consulta [models/README.md](../models/README.md) para más información.

Para el modelo emocional facial predeterminado:

```powershell
python scripts/emotion/download_emotion_model.py
```

## Ejecutar la aplicación web

Crear `.env` a partir de `.env.example`, definir DATABASE_URL/JWT_SECRET_KEY
locales y aplicar las migraciones. No versionar el archivo con credenciales.

```powershell
python -m alembic upgrade head
python -m uvicorn emotv.interfaces.web.app:app --reload
```

En otra terminal:

```powershell
cd web
npm ci
npm run dev
```

El estudiante prepara una actividad y autoriza su cámara en el navegador.
Se exige consentimiento activo. La captura requiere HTTPS o localhost;
la inferencia ocurre en FastAPI. No es necesario iniciar la cámara del servidor.
Las rutas administrativas y preparación de despliegue están en
[API administrativa](administrative-api.md) y
[preparación para producción](production-readiness.md).

## Verificar la etapa corporal

Ejecuta los flujos en este orden:

```powershell
python scripts/poses/run_pose_detection_test.py
python scripts/poses/run_posture_test.py
python scripts/poses/run_exercise_test.py
```

La primera prueba verifica landmarks y esqueleto. La segunda muestra si ambos
brazos están levantados y extendidos. La tercera exige mantener esa postura
durante cinco segundos y muestra una barra de progreso.

Para iniciar la prueba de postura con otro objetivo:

```powershell
python scripts/poses/run_posture_test.py --posture arms_open
```

## Ejecutar el MVP integrado

Cuando las pruebas individuales funcionen:

```powershell
python scripts/run_emotional_exercise_test.py
```

El flujo analiza varias expresiones, selecciona una actividad y luego cambia a
pose corporal. Usa `ESPACIO` para iniciar, `R` para reiniciar y `Q` para salir.
Consulta [MVP de actividad emocional](emotional-activity-mvp.md) para el alcance
y protocolo de validación manual.

## Ejecutar pruebas automatizadas

```powershell
python -m pytest
```

Resultado esperado para esta etapa: todas las pruebas unitarias aprobadas.

## Problemas frecuentes

### No se encuentra MediaPipe

Confirma que `.venv` esté activo y reinstala el proyecto:

```powershell
python -m pip install -e ".[dev]"
```

### No se encuentra el modelo

Ejecuta nuevamente:

```powershell
python scripts/poses/download_pose_model.py
```

### No se abre la cámara

Cierra otras aplicaciones que estén usando la webcam y revisa `CAMERA_INDEX`
en `src/emotv/config.py`.
