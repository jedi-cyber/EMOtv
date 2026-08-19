# Primeros pasos — Proyecto UNHEVAL EMO TV

## 1. Descripción del proyecto

**UNHEVAL EMO TV** es un proyecto de visión por computadora orientado a visualizar, detectar, segmentar, reconocer y clasificar emociones a partir de imágenes o video.

El proyecto está preparado para crecer de forma modular, permitiendo incorporar nuevos modelos, fuentes de video, interfaces y mecanismos de despliegue sin mezclar la lógica principal con detalles de infraestructura.

## 2. Tecnologías principales

- **Python 3.12:** lenguaje principal del proyecto.
- **YOLO26n:** modelo ligero utilizado como base para tareas de visión por computadora.
- **Entorno virtual de Python:** aislamiento de dependencias.
- **Arquitectura modular por capas:** separación entre dominio, casos de uso, infraestructura e interfaces.

> El archivo de pesos `yolo26n.pt` se encuentra actualmente en la raíz del proyecto. Cuando se implemente la carga de modelos, se recomienda trasladarlo a `models/weights/` y mantener su ubicación configurable.

## 3. Requisitos previos

Antes de comenzar, verificar que estén instalados:

- Python 3.12.
- Git.
- Un editor de código, como Visual Studio Code.
- Controladores compatibles con CUDA, únicamente si se utilizará una GPU NVIDIA.

Comprobar la versión de Python:

```powershell
python --version
```

El resultado esperado debe comenzar con `Python 3.12`.

## 4. Preparación del entorno

Desde la raíz del proyecto, crear el entorno virtual si todavía no existe:

```powershell
python -m venv .venv
```

Activarlo en PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Actualizar las herramientas de instalación:

```powershell
python -m pip install --upgrade pip
```

Las dependencias se definirán posteriormente en `pyproject.toml`. No se incluyen todavía comandos de instalación porque el proyecto aún no contiene una implementación.

## 5. Arquitectura del proyecto

```text
EMOtv/
├── src/emotv/
│   ├── domain/                 # Entidades y reglas centrales del negocio
│   ├── application/
│   │   ├── use_cases/          # Casos de uso de la aplicación
│   │   └── ports/              # Contratos con servicios externos
│   ├── infrastructure/
│   │   ├── vision/             # Integración con YOLO y procesamiento visual
│   │   ├── persistence/        # Almacenamiento de resultados
│   │   └── messaging/          # Comunicación y procesamiento asíncrono
│   ├── interfaces/
│   │   ├── api/                # API y rutas de acceso
│   │   └── ui/                 # Interfaz de visualización
│   ├── pipelines/
│   │   ├── detection/          # Detección de personas, rostros u objetos
│   │   ├── segmentation/       # Segmentación de regiones de interés
│   │   ├── recognition/        # Extracción y reconocimiento de características
│   │   └── classification/     # Clasificación de emociones
│   └── shared/                 # Utilidades y elementos compartidos
├── configs/                    # Configuración de entornos y modelos
├── data/
│   ├── raw/                    # Datos originales sin modificar
│   ├── interim/                # Datos en procesamiento
│   ├── processed/              # Datos listos para entrenamiento o evaluación
│   └── external/               # Datos provenientes de terceros
├── models/
│   ├── weights/                # Pesos de modelos entrenados
│   └── artifacts/              # Métricas, etiquetas y artefactos generados
├── notebooks/                  # Exploración, experimentación y análisis
├── scripts/                    # Automatización de tareas operativas
├── tests/
│   ├── unit/                   # Pruebas de componentes aislados
│   ├── integration/            # Pruebas entre capas o servicios
│   ├── e2e/                    # Pruebas del flujo completo
│   └── fixtures/               # Recursos reutilizables para pruebas
├── deployment/                 # Docker y Kubernetes
├── monitoring/                 # Métricas, alertas y paneles
└── docs/                       # Documentación técnica y funcional
```

## 6. Flujo funcional previsto

El procesamiento seguirá, de forma general, estas etapas:

1. Obtener una imagen, archivo de video o transmisión de cámara.
2. Validar y preparar la entrada.
3. Detectar las regiones de interés.
4. Segmentar las regiones que requieran un análisis específico.
5. Reconocer características visuales relevantes.
6. Clasificar la emoción detectada.
7. Visualizar y, cuando corresponda, almacenar el resultado.

Cada etapa debe permanecer desacoplada para que un modelo pueda sustituirse sin modificar todo el flujo.

## 7. Convenciones iniciales

- Mantener el código de producción dentro de `src/emotv/`.
- Evitar incluir reglas de negocio en la API o la interfaz gráfica.
- Acceder a modelos y servicios externos mediante contratos definidos en `application/ports/`.
- No versionar entornos virtuales, conjuntos de datos grandes, secretos ni resultados temporales.
- Mantener los pesos de modelos fuera del paquete Python y cargarlos mediante configuración.
- Añadir pruebas junto con cada nueva funcionalidad.
- Documentar las decisiones importantes de arquitectura en `docs/`.

## 8. Próximos pasos recomendados

1. Definir las emociones que reconocerá la primera versión.
2. Establecer las fuentes de entrada: imagen, video o cámara en tiempo real.
3. Determinar el papel exacto de YOLO26n dentro del flujo.
4. Seleccionar y documentar el conjunto de datos.
5. Completar `pyproject.toml` con las dependencias y herramientas de calidad.
6. Definir contratos para captura de video, inferencia y almacenamiento.
7. Implementar primero un flujo mínimo de extremo a extremo.
8. Incorporar métricas de precisión, latencia y uso de recursos.

## 9. Estado actual

El proyecto se encuentra en su fase inicial. La estructura base ya está creada, pero todavía no contiene implementación. Esta guía sirve como punto de partida y debe actualizarse conforme se definan los requisitos funcionales, el conjunto de datos y la estrategia de entrenamiento o inferencia.
