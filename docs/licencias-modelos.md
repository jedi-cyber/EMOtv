# Licencias de los modelos

Este documento registra qué modelos usa EMOtv, de dónde salen sus pesos y qué
licencia permite usarlos. Los textos completos de cada licencia están en
[`licenses/`](../licenses/). Revisado el 23 de noviembre de 2026.

**Regla del proyecto:** solo se integran modelos con licencias permisivas (MIT,
Apache-2.0 o similares). No se integra ningún modelo cuya licencia obligue a
publicar el código de EMOtv (GPL, AGPL, LGPL aplicada al conjunto, CC-BY-SA u
otras con *copyleft*), ni modelos con licencias que prohíban el uso que hace
la Facultad.

## Modelos en uso

| Modelo | Para qué | Archivo | Origen fijado | Licencia | Texto |
| --- | --- | --- | --- | --- | --- |
| HSEmotion `enet_b0_8_best_afew` | Expresión facial en vivo (predeterminado) | `models/weights/emotion/enet_b0_8_best_afew.onnx` | `sb-ai-lab/EmotiEffLib`, commit `af83348` | Apache-2.0 | [EmotiEffLib-Apache-2.0.txt](../licenses/EmotiEffLib-Apache-2.0.txt) |
| EmotiEffLib `enet_b2_8` | Expresión facial en vivo (alternativa más precisa y más pesada) | `models/weights/emotion/enet_b2_8.onnx` | `sb-ai-lab/EmotiEffLib`, commit `af83348` | Apache-2.0 | [EmotiEffLib-Apache-2.0.txt](../licenses/EmotiEffLib-Apache-2.0.txt) |
| FER+ (`emotion-ferplus-8`) | Expresión facial (respaldo) | `models/weights/emotion/emotion-ferplus-8.onnx` | ONNX Model Zoo (`onnxmodelzoo/emotion-ferplus-8`) | MIT (modelo); etiquetas FER+ de Microsoft, MIT | [FERPlus-MIT.txt](../licenses/FERPlus-MIT.txt), [ONNX-Model-Zoo-Apache-2.0.txt](../licenses/ONNX-Model-Zoo-Apache-2.0.txt) |
| YuNet (`face_detection_yunet_2026may`) | Detectar el rostro antes de clasificar; buscar personas en imágenes subidas | `models/weights/yunet/face_detection_yunet_2026may.onnx` | `opencv/opencv_zoo` | MIT | [YuNet-MIT.txt](../licenses/YuNet-MIT.txt) |
| MediaPipe Pose Landmarker Lite | Verificar posturas (congelado) y buscar cuerpos en imágenes subidas | `models/weights/pose/pose_landmarker_lite.task` | Google, repositorio oficial de modelos de MediaPipe | Apache-2.0 | [MediaPipe-Apache-2.0.txt](../licenses/MediaPipe-Apache-2.0.txt) |

Los pesos no se guardan en Git: los descarga `python scripts/download_models.py`,
que verifica el SHA-256 de cada archivo. EMOtv no modifica los pesos.

### EmotiEffLib y HSEmotion

- EmotiEffLib (antes `HSE-asavchenko/face-emotion-recognition`, la biblioteca
  conocida como HSEmotion) es de Andrey Savchenko y colaboradores. Su
  repositorio se publica con la licencia Apache-2.0, y su README dice que
  la licencia no limita el uso académico ni el comercial.
- Los dos archivos ONNX se toman de ese mismo repositorio
  (`models/affectnet_emotions/onnx/`) en el commit
  `af833487321c3efdcb1768a91a6c656a1986fdf6`. Ninguno cambió después de ese
  commit. El repositorio no publica una licencia aparte para los pesos, así que
  se usan bajo la licencia del repositorio que los distribuye.
- EMOtv no instala el paquete `emotiefflib` de PyPI. Usa directamente los
  archivos ONNX con `onnxruntime` y aplica el mismo preprocesamiento del código
  oficial (`emotiefflib/facial_analysis.py`): RGB, redimensionar a 224×224 (B0)
  o 260×260 (B2) y normalizar con la media y la desviación de ImageNet. El
  orden de las ocho clases es Anger, Contempt, Disgust, Fear, Happiness,
  Neutral, Sadness, Surprise.
- Apache-2.0 pide conservar el aviso de licencia y señalar los cambios cuando
  se redistribuye la obra. EMOtv cumple con este documento y con la copia de la
  licencia en `licenses/`.

### Conjuntos de datos de entrenamiento

Los modelos se entrenaron con conjuntos de datos públicos de investigación:
VGGFace2 y AffectNet para EmotiEffLib, y FER2013 con las etiquetas FER+ para
FER+. Esos conjuntos tienen sus propios términos, en general para
investigación y docencia. EMOtv no redistribuye ninguna imagen de esos
conjuntos y no entrena modelos. Su uso en la UNHEVAL, académico y sin fines de
lucro, encaja con esos términos. Antes de cualquier uso comercial conviene
revisar los términos de AffectNet y FER2013 con sus autores.

## Modelos quitados

| Modelo | Motivo |
| --- | --- |
| HardlyHumans ViT (`hardlyhumans_vit`) | Ninguna sesión lo usó: era experimental y solo administración podía elegirlo. Necesitaba PyTorch y Transformers (extra `emotion-vit`). Su ficha declaraba MIT, pero se quitó por estar sin uso. |
| Ultralytics YOLO (`yolo26n.pt`) | Era un archivo suelto en `models/weights/experimental/` y ningún código lo usaba. Ultralytics se publica con la licencia **AGPL-3.0**, que obliga a publicar el código de quien lo integra, incluso cuando el sistema solo se ofrece por la red. Por esa licencia no puede formar parte de EMOtv. |

La detección de personas en las imágenes que suben los usuarios usa YuNet y
MediaPipe, ambos con licencia permisiva. No necesita YOLO.

## Antes de agregar un modelo nuevo

1. Leer la licencia del código y la de los pesos. Si no hay una licencia
   aparte para los pesos, vale la del repositorio que los distribuye.
2. Rechazar GPL, AGPL, CC-BY-SA, las licencias "solo uso no comercial" que
   excluyan a la Facultad y los pesos sin licencia.
3. Fijar el commit o la revisión y el SHA-256 en `scripts/download_models.py`.
4. Copiar el texto de la licencia en `licenses/` y agregar una fila a este
   documento.
