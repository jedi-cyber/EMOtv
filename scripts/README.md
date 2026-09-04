# Scripts de EMOtv

Ejecuta los scripts desde la raíz del repositorio y con `.venv` activado.

## Pose corporal

### Descargar el modelo

```powershell
python scripts/poses/download_pose_model.py
```

Descarga Pose Landmarker Lite en la ruta configurada. Si el archivo ya existe,
no lo sobrescribe.

### Detectar landmarks

```powershell
python scripts/poses/run_pose_detection_test.py
```

Abre la webcam, detecta una persona y dibuja sus landmarks y conexiones.

### Validar una postura

```powershell
python scripts/poses/run_posture_test.py
```

Valida ambos brazos levantados mediante visibilidad, altura relativa de las
muñecas y ángulos de los codos.

### Completar el ejercicio

```powershell
python scripts/poses/run_exercise_test.py
```

Solicita mantener la postura durante el tiempo configurado. Muestra estado,
tiempo y una barra de progreso. Teclas:

- `Q`: salir;
- `R`: reiniciar el ejercicio.

## Emociones

- `scripts/emotion/download_weights.py`: descarga pesos de YuNet.
- `scripts/emotion/download_emotion_model.py`: descarga el clasificador.
- `scripts/emotion/run_face_detection_test.py`: prueba rostro y emoción.

## Otros

- `scripts/run_camera_test.py`: verifica la captura básica.
- `scripts/run_api.py`: inicia la interfaz web existente.
