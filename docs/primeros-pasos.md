# Primeros pasos

## Requisitos

- Windows con PowerShell (los comandos pueden adaptarse a otros sistemas).
- Python 3.12.
- Git.
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
