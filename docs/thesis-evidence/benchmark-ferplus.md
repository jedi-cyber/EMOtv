# Benchmark de FER+ en el entorno evaluado

> **Qué es y qué no es.** Es una **medición de rendimiento en un equipo
> concreto**, hecha el 15 de septiembre de 2026. **No es una garantía**: otro
> equipo, otra carga o varias sesiones a la vez darán otros valores. **No mide
> precisión**: la entrada son imágenes sintéticas que no son rostros.

Fuente: `reports/benchmarks/ferplus-baseline.json` y
`reports/benchmarks/ferplus-check-01.json`, generados con
`scripts/emotion/run_emotion_models_benchmark.py`. Explicación detallada en
[docs/ferplus-baseline.md](../ferplus-baseline.md).

## Entorno evaluado

| Dato | Valor |
| --- | --- |
| Sistema | Windows 11, AMD64 |
| CPU | Intel64 Family 6 Model 154 (10 núcleos físicos, 12 lógicos) |
| RAM | 11 959 MiB |
| Software | Python 3.12.10, NumPy 2.5.2, ONNX Runtime 1.29.0 (`CPUExecutionProvider`) |
| Modelo | `ferplus_onnx` versión 1.0, 35 040 571 bytes, SHA-256 `a2a2ba6a…efa61c` |

## Qué se midió

`predict(CroppedFace)`: una sola llamada al clasificador a la vez, en un
proceso, sin pausas. Tres corridas, cada una con 20 predicciones de
calentamiento, al menos 100 muestras y al menos 3 segundos. Entrada: 16
imágenes sintéticas en escala de grises de 64 × 64 (semilla 2026).

No incluye la detección de rostro (YuNet), la pose (MediaPipe), la red, el
WebSocket ni FastAPI.

## Resultados

Medición base (14:34 UTC):

| Corrida | Muestras | p50 (ms) | p95 (ms) | Predicciones/s | CPU normalizada | RSS pico (MiB) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 106 | 28,7 | 35,5 | 35,0 | 48,8 % | 151,7 |
| 2 | 107 | 27,5 | 34,5 | 35,6 | 48,7 % | 151,8 |
| 3 | 100 | 30,8 | 43,6 | 31,6 | 44,6 % | 151,8 |

Repetición en el mismo equipo (17:01 UTC, `ferplus-check-01.json`):

| Corrida | Muestras | p50 (ms) | p95 (ms) | Predicciones/s | CPU normalizada | RSS pico (MiB) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 343 | 7,0 | 17,5 | 114,1 | 77,2 % | 152,4 |
| 2 | 307 | 7,7 | 17,2 | 102,2 | 76,8 % | 152,5 |
| 3 | 402 | 6,9 | 11,0 | 133,8 | 80,5 % | 152,6 |

Carga del modelo: 0,43 s (base) y 0,18 s (repetición), con unos 43 MiB más de
memoria del proceso.

## Cómo leerlo

- Las dos mediciones, en el mismo equipo y el mismo día, difieren cerca de 4
  veces en latencia. El rendimiento depende del estado del equipo (otras
  aplicaciones, energía, temperatura), así que una sola medición no basta.
- «Predicciones/s» son llamadas al clasificador, no cuadros por segundo del
  navegador. El analizador envía como máximo 4 cuadros por segundo.
- La «CPU normalizada» divide el uso del proceso entre las 12 CPU lógicas; no
  es el uso total del equipo.
- En Docker, `docs/docker.md` registra un p95 de 18 a 25 ms por predicción en
  el contenedor del mismo equipo.
- La API solo admite FER+ si existe un benchmark vigente medido en el mismo
  entorno (`EMOTION_BENCHMARK_MAX_AGE_DAYS`); el servicio `models` lo vuelve a
  medir en Docker cuando falta o vence.
