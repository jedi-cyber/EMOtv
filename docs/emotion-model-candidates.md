# Revisión de candidatos y adaptador experimental

Revisión: 16 de septiembre de 2026. Público no equivale a dominio público ni
a ausencia de obligaciones. Se interpreta «libre» como licencia de uso permisiva;
ninguno de estos modelos se presenta como libre de toda licencia. Para exigir
literalmente dominio público habría que seleccionar otro artefacto verificable.

| Candidato | Compatibilidad y licencia observada | Decisión de esta etapa |
| --- | --- | --- |
| mo-thecreator/vit-Facial-Expression-Recognition | 7 clases, ViT, Safetensors; ficha sin licencia declarada | Descartado para incorporación hasta aclarar permisos de pesos |
| EmotiEffLib enet_b2_8 | 8 clases y ONNX oficial; Apache-2.0 declarada para código | Compatible técnicamente; no integrado hasta aclarar alcance de licencia sobre pesos |
| HSEmotion enet_b0_8 | Nombre incompleto: variantes best_afew, best_vgaf y va_mtl; ONNX disponible | Pendiente elegir artefacto exacto y confirmar permisos de pesos; no cargar por nombre ambiguo |
| HardlyHumans/Facial-expression-detection | 8 clases, ViT/Safetensors; ficha declara MIT para el modelo | Adaptador experimental y selector web; no predeterminado |

Fuentes primarias:
[mo-thecreator](https://huggingface.co/mo-thecreator/vit-Facial-Expression-Recognition),
[HardlyHumans](https://huggingface.co/HardlyHumans/Facial-expression-detection),
[EmotiEffLib](https://github.com/sb-ai-lab/EmotiEffLib),
[ONNX oficiales](https://github.com/sb-ai-lab/EmotiEffLib/tree/main/models/affectnet_emotions/onnx),
[HSEmotion](https://github.com/av-savchenko/hsemotion).

## Métricas: no son un ranking EMOtv

mo-thecreator publica accuracy 0.8434 sobre su evaluación de FER2013/MMI/AffectNet.
HardlyHumans publica 0.922 sobre una evaluación FER2013/AffectNet; la ficha no
permite reconstruir por completo la partición y protocolo. Estos números no
demuestran cuál modelo funciona mejor en EMOtv.
Ambos ViT tienen unos 85.8 millones de parámetros y pesos Safetensors de unos
343 MB. HardlyHumans no ofrece ONNX listo en los archivos revisados: este
adaptador usa PyTorch CPU. La conversión ONNX y equivalencia quedan pendientes.

EmotiEffLib publica enet_b2_8 con 63.03 % AffectNet8, unos 30 MB y 191 ± 18 ms;
las variantes B0 tienen unos 16 MB y 59 ± 26 ms. Esas latencias se midieron en
Samsung Fold 3/Qualcomm 888, no en el servidor EMOtv. No son comparables directamente
con [la línea base FER+](ferplus-baseline.md).

## Instalar y probar HardlyHumans

```powershell
python -m pip install -e ".[emotion-vit]"
python scripts/emotion/download_hardlyhumans_model.py
python scripts/emotion/run_emotion_model_test.py --model hardlyhumans_vit
```

Si la red usa una CA de confianza en Windows que Python no reconoce, ejecutar
la descarga con `--system-ca` para usar truststore. No desactivar verificación
TLS ni aceptar certificados arbitrarios. Las dependencias opcionales ya incluyen
truststore; el flag solo modifica el contexto de la herramienta de descarga.

El script técnico usa entrada sintética si no se indica `--image` con un rostro
ya recortado. No almacena imágenes ni activa una cámara. No mide precisión.
Para FER+ el mismo script admite `--model ferplus_onnx`.

Descarga fijada al commit `736c91353cf79a0e0c9a86256982be7d9d7c1591`, solo
configuración, ficha y Safetensors. Verifica arquitectura, clases, declaración MIT,
tamaño y SHA-256 de pesos según los metadatos del snapshot. La instalación se
publica después de verificar y no sobrescribe instalaciones existentes. Conserva
`emotv-source.json` y la ficha en `models/weights/hardlyhumans_vit/`, fuera de Git.
La declaración del autor no sustituye revisar derechos de datasets ni preservar
los avisos de licencia al redistribuir. La ficha MIT no es dominio público.

La fábrica admite `create_emotion_classifier("hardlyhumans_vit")`; sin ID sigue
usando FER+. El analizador acepta inyección del adaptador y mantiene el recorte
BGR uint8 sin reducirlo a grises. ViT convierte a RGB y deja resize/rescale/normalize
al procesador oficial local. Se traducen happy/sad/angry a happiness/sadness/anger
manteniendo el orden del config, no el orden FER+.

No hay descargas en el arranque/inferencia, código remoto ni carga pickle.
El analizador web permite seleccionar FER+ (ONNX, predeterminado) o HardlyHumans
(ViT/PyTorch, experimental) antes de iniciar. No los clasifica por precisión.
El mensaje autenticado de
`/ws/activity` incluye `emotion_model_id`; el servidor solo admite estos dos IDs
y confirma el elegido y su versión en `ready`. Clientes anteriores conservan FER+.
Después de cargar el modelo, ambos valores se guardan en la sesión mediante
`SessionService`; no se inventan valores para sesiones históricas o canceladas
antes de la carga.
No cambia modelos durante una sesión ni aplica fallback silencioso. Si faltan
pesos/dependencias, devuelve un error y cancela la sesión activa. La carga ocurre
en un hilo, no en el event loop. Las dependencias ViT siguen siendo opcionales.
La inferencia se ejecuta en el servidor: lo que importa para admitir un modelo
es la capacidad del servidor, no la CPU o RAM del dispositivo del estudiante.
Antes de uso productivo con estudiantes, medir RAM/latencia del pipeline y
calibrar la política de admisión existente. Mayor tamaño o accuracy publicada
no garantizan un mejor resultado en este equipo.

## Verificación de implementación

### Advertencia y bloqueo automáticos

`GET /analysis/models` requiere autenticación y devuelve `SUPPORTED`, `WARNING`
o `BLOCKED` por modelo, razones y métricas. La web refresca cada 10 segundos
antes de iniciar; un fallo de consulta o estado bloqueado deshabilita el inicio.
El WebSocket reevalúa antes de cargar y rechaza el inicio aunque el cliente
omita o manipule el selector. WARNING permite continuar y muestra sus razones.

La evaluación verifica instalación, hash/tamaño/versión de pesos, entorno CPU,
Python/runtime y vigencia del informe. Requiere tres corridas con al menos
100 muestras y 3 segundos por corrida, todas con `target_reached=true`.
Sin informe válido bloquea ambos modelos, incluido FER+: que sea predeterminado
no constituye una excepción. HardlyHumans queda bloqueado hasta generar un
informe completo y válido en el servidor.

Defaults configurables en `.env.example`: aviso p95 ≥250 ms, bloqueo ≥1000 ms;
aviso CPU actual ≥75 %, bloqueo ≥95 %; RAM requerida = pico RSS del benchmark
×1.5 +512 MiB, bloqueo si la RAM disponible es menor, aviso si el margen no
alcanza 1.5 veces ese requisito. Informes válidos durante 30 días. Son límites
iniciales de ingeniería, no umbrales calibrados clínicamente ni SLA.

Las rutas `FERPLUS_BENCHMARK_PATH` y `HARDLYHUMANS_BENCHMARK_PATH` pueden
apuntar a informes nuevos. Reiniciar FastAPI tras cambiar configuración.
Por defecto se usan `ferplus-baseline.json` y `hardlyhumans-check-01.json`.
No ejecutar benchmarks automáticamente en una petición ni descargar pesos.

Los informes `*-check-01.json` son resultados locales del operador: no se
presupone que estén presentes en otro checkout. En este repositorio, el informe
de ejemplo disponible para FER+ es `ferplus-baseline.json`. Si se generan otros
informes, revisar que no contengan rutas, usuarios ni datos sensibles antes de
versionarlos; los pesos siguen fuera de Git.

Esta es admisión preventiva de nuevas sesiones; no interrumpe las existentes
ni implementa AUTO, histéresis o fallback. CPU es una muestra de 100 ms y RAM
es una instantánea: no reserva capacidad de forma atómica entre workers ni
garantiza concurrencia. Aún deben medirse carga/picos de inicialización, pose
y pipeline completo; producción requiere límites de concurrencia distribuidos.

### Medir latencia, CPU y RAM

Ejecutar cada comando en un proceso nuevo, desde la raíz y con `.venv` activo:

```powershell
python scripts/emotion/run_emotion_models_benchmark.py --model ferplus_onnx --output reports/benchmarks/ferplus-check-01.json
python scripts/emotion/run_emotion_models_benchmark.py --model hardlyhumans_vit --output reports/benchmarks/hardlyhumans-check-01.json
```

Por defecto realiza tres corridas con 20 predicciones de calentamiento por
corrida, al menos 100 muestras y 3 segundos de medición. El límite de 30 segundos
se verifica entre predicciones: no interrumpe una inferencia ni limita la carga
o el calentamiento. Si `target_reached` es falso, repetir con `--max-seconds 120`.
No sobrescribe informes. Para repetir, cambiar el sufijo de salida.
Para HardlyHumans, si el informe indica `target_reached: false` en alguna
corrida, repetir con `--max-seconds 120` y otro nombre de salida, por ejemplo
`hardlyhumans-check-02.json`; luego configurar
`HARDLYHUMANS_BENCHMARK_PATH=reports/benchmarks/hardlyhumans-check-02.json`
en `.env` y reiniciar FastAPI. Lo mismo aplica a `FERPLUS_BENCHMARK_PATH` si
se elige un informe FER+ diferente. No borrar ni sobrescribir el informe previo.

Comparar media, p95, `ram_peak_mib`, `load.rss_after_mib`, tiempo de carga y CPU.
Los informes v2 registran backend y número de hilos; los antiguos FER+ siguen
siendo válidos. ViT recibe BGR 224x224 y FER+ grises 64x64: se compara el contrato
`predict` con entrada nativa, no exclusivamente el forward de la red. La RAM
incluye todo el proceso y el pico se muestrea cada 50 ms durante inferencia,
no durante carga. La carga incluye imports diferidos del adaptador.
Esto no mide cámara, WebSocket, concurrencia ni precisión. No existen umbrales
de admisión validados todavía. Los otros tres candidatos no tienen adaptador
habilitado y se rechazan en la CLI; no se descargan ni prueban automáticamente.

El 15 de septiembre de 2026 se descargó el snapshot y se verificaron tamaño y
SHA-256. La inferencia real en CPU con la entrada sintética del script devolvió
`neutral` con confianza aproximada de `0.5656`. Esto confirma carga, preprocesado
y salida compatibles, no precisión clínica ni rendimiento en tiempo real.
La suite completa pasó con 241 pruebas y 32 subpruebas; tras corregir la descarga
secuencial para Windows, las siete pruebas del adaptador volvieron a pasar.
