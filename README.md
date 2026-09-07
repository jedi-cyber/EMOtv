# EMOtv

EMOtv es un sistema experimental de apoyo al bienestar emocional para la
Facultad de Psicología de la Universidad Nacional Hermilio Valdizán. Combina
visión por computadora, análisis corporal y aplicaciones interactivas.

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
- validación de `arms_up`, `arms_open` y `hands_on_hips`;
- catálogo local con una actividad para cada postura implementada;
- estabilización de emociones a partir de múltiples predicciones;
- recomendación local de actividades a partir de la emoción estabilizada;
- controlador del flujo emoción → actividad → postura → ejercicio;
- ejercicio temporizado con estados `incorrect`, `holding` y `completed`;
- progreso normalizado y barra visual en tiempo real;
- pruebas unitarias de pose, postura, dibujo y ejercicio.

## Inicio rápido

Requiere Python 3.12 y una webcam compatible con OpenCV.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/poses/download_pose_model.py
```

Pruebas disponibles:

```powershell
python scripts/poses/run_pose_detection_test.py
python scripts/poses/run_posture_test.py
python scripts/poses/run_exercise_test.py
python scripts/run_emotional_exercise_test.py
```

En las ventanas de prueba, `Q` finaliza la ejecución. En la prueba del
ejercicio, `R` reinicia el estado después de completarlo o durante un intento.

Para ejecutar las pruebas automatizadas:

```powershell
python -m pytest
```

También pueden ejecutarse sin pytest:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Documentación

- [Primeros pasos](docs/primeros-pasos.md)
- [Arquitectura](docs/architecture.md)
- [Etapa de reconocimiento corporal](docs/pose-estimation.md)
- [MVP de actividad emocional](docs/emotional-activity-mvp.md)
- [Modelos y pesos](models/README.md)
- [Scripts disponibles](scripts/README.md)
- [Pruebas](tests/README.md)

## Próximas etapas

1. Validar manualmente el MVP integrado con webcam y registrar resultados.
2. Calibrar umbrales y revisar actividades con profesionales de Psicología.
3. Registrar sesiones y resultados de ejercicios.
4. Integrar el flujo con la aplicación web.
5. Admitir fuentes de video adicionales, incluida ESP32-CAM.
