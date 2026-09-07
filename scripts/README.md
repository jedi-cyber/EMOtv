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

La postura inicial puede seleccionarse con:

```powershell
python scripts/poses/run_posture_test.py --posture arms_open
python scripts/poses/run_posture_test.py --posture hands_on_hips
```

Durante la ejecución, `1`, `2` y `3` cambian entre `arms_up`, `arms_open` y
`hands_on_hips`. La ventana muestra instrucciones, mediciones geométricas y las
reglas que todavía no se cumplen.

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

## Flujo emocional integrado

```powershell
python scripts/run_emotional_exercise_test.py
```

Analiza varias predicciones faciales, estabiliza la emoción, selecciona una
actividad local y cambia a detección corporal hasta completar el ejercicio.
Muestra el resultado final en la consola y lo mantiene en memoria. Controles:

- `ESPACIO`: comenzar inmediatamente la actividad seleccionada;
- `R`: reiniciar el flujo completo;
- `Q`: salir.
