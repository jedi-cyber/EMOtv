# Línea base FER+ — 15 de septiembre de 2026

Medición real de `predict(CroppedFace)` con ONNX Runtime CPU, un proceso,
un clasificador y una llamada a la vez, sin pausas de envío. No mide precisión,
captura, YuNet, pose, FastAPI, red, ni concurrencia de estudiantes.

Equipo observado: Windows 11, Intel Family 6 Model 154, 10 núcleos físicos,
12 CPU lógicas y 11 959 MiB de RAM. Python 3.12.10, ONNX Runtime 1.29.0.
Hilos ONNX con configuración automática del adaptador existente.

## Protocolo

Tres corridas con 20 predicciones de calentamiento por corrida, al menos
100 muestras y 3 segundos medidos por corrida. Entrada sintética reproducible:
16 imágenes de grises uint8 de 64×64, semilla 2026. Se conserva la escala del
adaptador. Estas imágenes no son rostros ni sirven para evaluar calidad emocional.
RSS muestreado aproximadamente cada 50 ms y al inicio/final de cada corrida.

## Resultados

| Corrida | Muestras | Media ms | p50 ms | p95 ms | Predicciones/s | CPU normalizada | RSS pico MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 106 | 28.57 | 28.67 | 35.52 | 35.00 | 48.76 % | 151.67 |
| 2 | 107 | 28.07 | 27.53 | 34.50 | 35.62 | 48.72 % | 151.80 |
| 3 | 100 | 31.65 | 30.76 | 43.56 | 31.59 | 44.64 % | 151.82 |

Carga del modelo, medida por separado: 0.43 s. RSS antes de carga: 102.82 MiB;
después: 145.52 MiB; incremento observado: 42.70 MiB. No es una medición exacta
de memoria exclusiva de pesos. El archivo pesa 35 040 571 bytes.

Datos completos, hash SHA-256 y definiciones:
[ferplus-baseline.json](../reports/benchmarks/ferplus-baseline.json).

## Interpretación

La CPU se calcula mediante tiempo user+system del proceso dividido por tiempo
de pared. Su valor sin normalizar fue 536–585 %, equivalente aproximadamente a
5.4–5.9 CPU lógicas ocupadas; dividido por 12 da 44.64–48.76 %.
No representa el uso total del host ni el consumo de un único núcleo.

La RAM es RSS de todo el proceso de benchmark, incluidos imports y runtime.
El pico muestreado puede omitir transitorios menores a 50 ms. La carga y warmup
quedan fuera de las métricas de inferencia. El throughput utiliza duración de
pared y llamadas completadas, no FPS suavizados ni el inverso del p95.

FER+ tiene margen de latencia para la cadencia actual de unos 4 envíos/s del
navegador en este ensayo aislado. Eso no demuestra capacidad del pipeline
completo, estabilidad térmica a largo plazo ni número de estudiantes concurrentes.
La CPU de esta prueba es carga sostenida sin throttling, no el uso habitual a
4 envíos/s. La admisión preventiva implementada posteriormente asigna estados
SUPPORTED/WARNING/BLOCKED con límites iniciales configurables; esta tabla
histórica no equivale a una evaluación del pipeline completo.

## Repetir

```powershell
python scripts/emotion/run_emotion_models_benchmark.py --output reports/benchmarks/ferplus-baseline-next.json
python -m pytest tests/unit/test_model_benchmark.py -q -p no:cacheprovider
```

Cada corrida se detiene al cumplir mínimos o llegar al máximo de 30 s,
comprobado entre llamadas; no interrumpe una inferencia bloqueada. El informe
indica si se cumplieron los mínimos. No sobrescribe informes existentes.
Para un ensayo más largo usar `--samples 500 --min-seconds 15 --max-seconds 60`.

Siguiente paso: medir pipeline facial y actividad completa a cadencia real y
concurrencia representativa; contrastar ambos modelos con informes completos
del mismo servidor. Mantener esta línea base sin sustituir FER+.
