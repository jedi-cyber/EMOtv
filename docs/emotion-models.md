# Modelo facial predeterminado

El modelo actual FER+ ONNX queda registrado como `ferplus_onnx` en
`EmotionModelCatalog`, con `is_default=True`. Su adaptador explícito es
`FerPlusEmotionClassifier`, que satisface el contrato común `EmotionClassifier`.

`create_emotion_classifier()` resuelve el modelo predeterminado del catálogo.
La cámara del navegador (`EmotionFrameAnalyzer`) y el servicio de visión existente
utilizan esta fábrica. Un ID desconocido o sin adaptador no cambia silenciosamente
al modelo predeterminado.

Se conservan CPUExecutionProvider, entrada float32 NCHW de 64×64, escala del
preprocesador actual y orden de ocho etiquetas FER+. Los imports antiguos de la
clase concreta `EmotionClassifier` siguen funcionando mediante un alias.

Los pesos se obtienen desde `EMOTION_MODEL_PATH`, actualmente:
`models/weights/emotion/emotion-ferplus-8.onnx`. Para descargarlos:

```powershell
python scripts/emotion/download_emotion_model.py
```

Se añadió el adaptador opcional experimental `hardlyhumans_vit`; no sustituye
a FER+ como predeterminado. El selector web distingue FER+ (ONNX) y HardlyHumans
(ViT/PyTorch experimental), fijados antes de iniciar. La elección depende de la
disponibilidad y el rendimiento del servidor, pues allí se ejecuta la inferencia;
el equipo del estudiante solo captura y envía imágenes. Su descarga, licencia declarada,
preprocesamiento y límites están en [revisión de candidatos](emotion-model-candidates.md).
No se afirma mayor precisión sin evaluación comparable en EMOtv.
