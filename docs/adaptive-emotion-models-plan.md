# Próxima subfase: selección adaptativa de modelos faciales

Estado: **plan, no implementación**. Basado en el contexto de continuación 3,
revisado el 15 de septiembre de 2026. Sus ejemplos de resultados y umbrales
son ilustrativos, no mediciones de EMOtv.

## Punto de partida versionable

Ya existen `EmotionModel`, `EmotionModelCatalog`, el contrato `EmotionClassifier`
y el adaptador `FerPlusEmotionClassifier`. `create_emotion_classifier()` resuelve
`ferplus_onnx` como predeterminado para los analizadores existentes. Se conservan
pesos, CPU, etiquetas y preprocesamiento. Todavía no hay perfiles, benchmark,
selector, monitor de degradación ni nuevos modelos integrados.

También están implementados cámara web, sesiones, endpoints administrativos,
actividades PostgreSQL, migración `20260915_04`, pruebas frontend/backend y
configuración básica de seguridad. No confundir estas capacidades con la
aprobación institucional de producción.

## Método recomendado

1. **Línea base FER+.** Definir protocolo y medir el adaptador existente en el
   equipo que realmente ejecuta inferencia, sin cambiar su comportamiento.
2. **Investigación de candidatos.** Consultar publicaciones, repositorios y
   fichas oficiales; documentar licencia del código, pesos y datasets por separado.
   Comparar métricas solo cuando protocolo y dataset permitan hacerlo.
3. **Validación controlada.** Probar preprocesamiento, clases, salida, conversión
   ONNX y equivalencia con el framework original. Evaluar una colección consentida
   o pública compatible, sin reutilizar sesiones de estudiantes para entrenamiento.
4. **Perfiles.** Mantener FER+ como DEFAULT y candidato inicial LIGHT. Incorporar
   otro LIGHT solo si aporta una ventaja medida; elegir PRECISE después de medir,
   no por el nombre o tamaño de la red.
5. **Selector puro.** Definir requisitos configurables y resultados SUPPORTED,
   WARNING y BLOCKED. Probar decisiones con mediciones simuladas antes de conectarlo
   a clasificadores reales. AUTO queda como política recomendada futura.
6. **Protección sostenida.** Medir ventanas temporales, usar histéresis y cooldown
   para evitar cambios por frames aislados. Preferir cambios entre actividades;
   si se permite cambio durante una actividad, reiniciar explícitamente la ventana
   de estabilización emocional y comunicar el evento al consumidor.
7. **Integración posterior.** Solo con mediciones y políticas verificadas, exponer
   disponibilidad/advertencias por API y luego diseñar el selector web.

El primer incremento de código recomendado es el contrato de métricas/resultados,
un medidor de FER+ y `scripts/emotion/run_emotion_models_benchmark.py`. Todavía
no descargar ni seleccionar automáticamente modelos candidatos sin revisión.

## Qué hardware evaluar

Los frames del navegador se procesan en FastAPI. Por tanto, para la web se mide
**el servidor y su concurrencia**, no CPU/RAM del dispositivo del estudiante.
En scripts locales se mide el equipo local. Una futura inferencia dentro del
navegador requeriría otro evaluador y otra política.

La capacidad para una conexión no garantiza capacidad para varios estudiantes.
Medir también el coste de una instancia por conexión y la competencia entre
inferencia facial, pose, decodificación y otras peticiones.

## Protocolo reproducible de benchmark

- Registrar modelo/versión, hash de pesos, runtime/proveedor, versiones,
  CPU, memoria del equipo, hilos y concurrencia.
- Separar carga y warmup de inferencias medidas; repetir suficientes muestras
  y corridas para estimar variación.
- Registrar latencia media y p50/p95, throughput, CPU de proceso y RSS
  (memoria residente), con definiciones y unidades explícitas.
- Distinguir CPU de proceso normalizada por núcleo de utilización total del host.
- Medir el pipeline completo por separado del `predict(face)` aislado.
- El inverso de la latencia no es el FPS observado del navegador: actualmente
  se intentan enviar frames cada 250 ms y se espera respuesta antes de enviar otro.
- No fijar mínimos de 12 FPS sobre una ruta limitada a unos 4 envíos/s.
  Calibrar presupuesto de latencia, carga y frecuencia según el flujo real.
- Guardar resultados JSON/CSV sin rostros, tokens, credenciales ni rutas sensibles.

## Selección y fallback

El servicio de aplicación depende de un puerto de evaluación y una fábrica de
`EmotionClassifier`; los detalles de ONNX y medición quedan en infraestructura.
Metadatos/requisitos/resultados no deben importar React, psutil u ONNX Runtime.

Un resultado válido debe identificar equipo, modelo, protocolo y vigencia.
Una evaluación ausente, fallida o desactualizada no autoriza PRECISE.
DEFAULT es el modelo de compatibilidad, **no una garantía de rendimiento**:
también necesita evaluación. Si ningún modelo cumple, bloquear el análisis y
dar un error claro en vez de forzar un fallback que sobrecargue el servidor.

Fallback solo a un adaptador instalado y evaluado. Un ID desconocido sigue
produciendo error explícito; no convertir errores de configuración en cambios
silenciosos. No aceptar archivos de pesos elegidos directamente por usuarios.

## Entregables y aceptación

- Ficha de candidatos con clases, dataset, métrica/protocolo, licencia, versión,
  tamaño, framework, soporte ONNX, fuentes y observaciones.
- Elección LIGHT/PRECISE sustentada en mediciones locales comparables.
- Benchmark común y script comparativo con CPU, RAM, latencia y throughput.
- Selector AUTO/LIGHT/PRECISE con SUPPORTED/WARNING/BLOCKED y razones.
- Monitor PERFORMANCE_DEGRADED con ventana e histéresis; fallback controlado.
- Tests de límites, datos ausentes, errores, recuperación, concurrencia y fallback.

La subfase termina cuando estas decisiones son reproducibles bajo límites
calibrados, no cuando solo se agregan metadatos al catálogo.

## Antes del commit de esta etapa

```powershell
python -m pytest -q -p no:cacheprovider
git diff --check
git status --short
cd web
npm test
npm run build
```

Últimas ejecuciones registradas durante el desarrollo: 231 pruebas backend y
32 subpruebas; 23 pruebas frontend y compilación correctas. Son una referencia
de ejecución, no una garantía de cobertura ni mediciones de modelos candidatos.

Revisar el diff y preparar archivos explícitamente antes del commit. No incluir
`.env`, pesos, caches, `node_modules`, `dist` ni scripts temporales de credenciales.
No se crea un commit automáticamente por actualizar estos documentos.
