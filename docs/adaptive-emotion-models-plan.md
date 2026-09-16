# Selección de modelos faciales: estado y trabajo pendiente

Estado revisado el 16 de septiembre de 2026. La selección manual y la admisión
preventiva están implementadas; el monitoreo sostenido y el control de
concurrencia siguen pendientes. Los umbrales de admisión son configuraciones
iniciales de ingeniería, no una validación clínica ni garantía de servicio.

## Punto de partida versionable

`EmotionModelCatalog` registra FER+ ONNX (`ferplus_onnx`, predeterminado) y
HardlyHumans ViT/PyTorch (`hardlyhumans_vit`, experimental). Ambos implementan
`EmotionClassifier` mediante adaptadores. La web presenta **tipos de modelo**,
no categorías LIGHT/PRECISE ni una comparación de exactitud que no se ha medido.

El benchmark común mide carga, latencia, CPU y RSS de `predict` con entradas
nativas. Existe una [línea base FER+](ferplus-baseline.md). La consulta autenticada
`GET /analysis/models` devuelve `SUPPORTED`, `WARNING` o `BLOCKED` por modelo;
la web la refresca y el WebSocket la verifica de nuevo antes de cargar. El
informe debe ser local, vigente y corresponder a los pesos y al runtime. No hay
fallback silencioso. La selección se usa durante la actividad y no se persiste
todavía como campo de sesión. Véase [procedimiento operativo](emotion-model-candidates.md).

También están implementados cámara web, sesiones, endpoints administrativos,
actividades PostgreSQL, migración `20260915_04`, pruebas frontend/backend y
configuración básica de seguridad. No confundir estas capacidades con la
aprobación institucional de producción.

## Método recomendado

1. Repetir el benchmark de ambos adaptadores en el servidor de despliegue y
   conservar informes válidos; los generados en otro equipo no habilitan modelos.
2. Medir pipeline completo (detección, pose, WebSocket, carga e inferencia),
   disponibilidad de RAM y concurrencia representativa antes de recalibrar límites.
3. Evaluar la calidad de reconocimiento con datos autorizados y un protocolo
   común; no inferir mejor precisión del tamaño de pesos o métricas publicadas.
4. Añadir un límite de admisiones entre procesos/workers. La instantánea actual
   de CPU/RAM no reserva memoria de forma atómica.
5. Si se desea protección sostenida, usar ventanas, histéresis y cooldown;
   definir cómo comunicar degradación sin cambiar modelos a mitad de actividad.
   AUTO o fallback solo se considerarán después de validar esa política.

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
Una evaluación ausente, fallida o desactualizada no autoriza ningún modelo.
DEFAULT es el modelo de compatibilidad, **no una garantía de rendimiento**:
también necesita evaluación. Si ningún modelo cumple, bloquear el análisis y
dar un error claro en vez de forzar un fallback que sobrecargue el servidor.

Fallback solo a un adaptador instalado y evaluado. Un ID desconocido sigue
produciendo error explícito; no convertir errores de configuración en cambios
silenciosos. No aceptar archivos de pesos elegidos directamente por usuarios.

## Entregables y aceptación

- Ficha de candidatos con clases, dataset, métrica/protocolo, licencia, versión,
  tamaño, framework, soporte ONNX, fuentes y observaciones.
- Benchmark común y script comparativo con CPU, RAM, latencia y throughput:
  implementados para los dos adaptadores disponibles.
- Selector manual por tecnología y estados SUPPORTED/WARNING/BLOCKED:
  implementados para **nuevos inicios**, pendientes de calibración operativa.
- Evaluación de calidad comparable, concurrencia y pipeline completo: pendientes.
- Monitor de degradación con ventana e histéresis, y eventual fallback
  controlado: pendientes; no forman parte del comportamiento actual.

La subfase operativa termina cuando estas decisiones sean reproducibles bajo
límites calibrados y concurrencia representativa, no solo por tener un selector.

## Antes del commit de esta etapa

```powershell
python -m pytest -q -p no:cacheprovider
git diff --check
git status --short
cd web
npm test
npm run build
```

Registrar los resultados actuales de las pruebas al preparar el commit; no
reutilizar conteos de ejecuciones anteriores como verificación de esta revisión.

Revisar el diff y preparar archivos explícitamente antes del commit. No incluir
`.env`, pesos, caches, `node_modules`, `dist` ni scripts temporales de credenciales.
No se crea un commit automáticamente por actualizar estos documentos.
