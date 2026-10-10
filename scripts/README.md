# Scripts de EMOtv

## Auditoría de actividades PostgreSQL

```powershell
python scripts/audit_postgres_activities.py
python scripts/audit_postgres_activities.py --repair
```

El primer comando es de solo lectura. Comprueba que las actividades usadas por
la recomendación automática existan, tengan al menos dos pasos y que todas sus
posturas cuenten con un validador. `--repair` solo crea candidatas ausentes o
restaura candidatas con menos de dos pasos desde el catálogo predeterminado.

Ejecuta los scripts desde la raíz del repositorio y con `.venv` activado.

## Diagnóstico local con webcam (fuera del producto)

Los scripts de pose, emoción, ejercicio y sesión de las secciones siguientes
(y `run_camera_test.py`) abren la webcam **de este equipo** con OpenCV y
muestran ventanas de vista previa. Sirven solo para probar modelos a mano:

- se apoyan en `scripts/diagnostics/` (`OpenCVCamera`, vista previa, `PoseDrawer`);
- la API no los importa y no se ejecutan en Docker;
- en el producto, la cámara se obtiene en el navegador y los frames llegan por
  `/ws/activity`;
- no usarlos con voluntarios.

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

- `scripts/download_models.py`: descarga y verifica (SHA-256) todos los pesos
  requeridos, incluido YuNet `face_detection_yunet_2026may.onnx`. Es la misma
  descarga que usa el servicio `models` de Docker.
- `scripts/emotion/download_emotion_model.py`: descarga solo el clasificador.
- `scripts/emotion/run_face_detection_test.py`: prueba rostro y emoción (diagnóstico local).
- `scripts/emotion/check_model_availability.py`: muestra si FER+ y ViT están
  habilitados por los pesos, benchmarks y recursos locales. No modifica archivos.

## Evaluación de Emi

```powershell
python scripts/chatbot/run_eval.py --base-url http://localhost:8080
```

Envía las 35 preguntas de `tests/chatbot/emi_eval.md` a `/chat` con una cuenta
de prueba (`PRUEBA-NN`, consentimiento aceptado) y guarda en
`reports/chatbot/` (ignorado por git) un informe con fecha para revisión
humana. No califica las respuestas. Pide el correo y la contraseña por consola
o los lee de `EMOTV_EVAL_EMAIL` y `EMOTV_EVAL_PASSWORD`; no los escribe en el
informe. Consume cuota de Groq y espera cuando EMOtv responde 429.

## Otros

- `scripts/run_camera_test.py`: verifica la captura básica.
- `scripts/run_api.py`: inicia la API FastAPI.

### Cuentas locales de prueba por rol

Con PostgreSQL local y las migraciones aplicadas, crea una cuenta de Psicología
y una de Estudiante con contraseñas aleatorias:

```powershell
python scripts/create_demo_role_accounts.py --create
```

El script rechaza bases de datos remotas, no modifica usuarios existentes y
muestra las credenciales solo en la terminal. Guárdalas fuera del repositorio.
No crea consentimiento para la cuenta estudiantil: debe registrarse de forma
válida antes de iniciar sesiones asociadas.

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

## Prueba completa de sesión

Ejecuta el flujo integrado y guarda el resultado final mediante
`SessionService` e `InMemorySessionRepository`:

```powershell
python scripts/run_session_test.py
```

La salida incluye el ID de sesión, timestamps, emoción inicial, actividad,
resultado del ejercicio y duración. Las sesiones interrumpidas o reiniciadas
se registran como canceladas mientras el proceso permanezca abierto.
