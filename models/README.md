# Modelos y pesos de EMOtv

Los pesos no se almacenan en Git. Cada modelo debe ubicarse bajo
`models/weights/` y su ruta debe declararse en `src/emotv/config.py`.

## MediaPipe Pose Landmarker

EMOtv utiliza inicialmente la variante Lite (`float16`) en esta ruta:

```text
models/weights/pose/pose_landmarker_lite.task
```

Para descargarla desde el repositorio oficial de modelos de MediaPipe:

```powershell
python scripts/poses/download_pose_model.py
```

El script no sobrescribe un modelo existente. Para sustituirlo de forma
explícita, llama a `download_pose_model(overwrite=True)` desde Python.

La ruta y URL se configuran mediante `POSE_MODEL_PATH` y `POSE_MODEL_URL` en
`src/emotv/config.py`. El archivo procede del repositorio oficial de modelos de
MediaPipe y no se incluye en Git (`*.task` está ignorado).

## Modelos emocionales

Los modelos existentes de YuNet y clasificación emocional se almacenan bajo:

```text
models/weights/yunet/
models/weights/emotion/
```

Los scripts de descarga relacionados se encuentran en `scripts/emotion/`.

El clasificador facial predeterminado es FER+ ONNX, ID `ferplus_onnx`, adaptado
por `FerPlusEmotionClassifier` y resuelto por una fábrica común. Sus pesos están
en `models/weights/emotion/emotion-ferplus-8.onnx`:

```powershell
python scripts/emotion/download_emotion_model.py
```

Consultar [modelo predeterminado](../docs/emotion-models.md). La selección
LIGHT/PRECISE y su benchmark aún son una subfase planificada, no implementada:
[plan adaptativo](../docs/adaptive-emotion-models-plan.md).

## Política de versionado

- No confirmar pesos `.task`, `.onnx`, `.pt`, `.pth` o `.tflite`.
- Sí confirmar scripts de descarga, rutas configurables y documentación.
- No reemplazar un modelo local silenciosamente.
- Registrar el origen y variante cuando se incorpore un modelo nuevo.
