# Sesiones y persistencia

## Objetivo

Esta etapa transforma el resultado del MVP en una entidad estructurada y
persistible. La detección facial determina una expresión emocional inicial; el
análisis corporal se limita a guiar y validar actividades mediante posturas y no
intenta inferir emociones corporales.

```text
EmotionalActivityService
        -> EmotionalActivityStatus
        -> SessionService
        -> EmotionalSession
        -> SessionRepository
        -> InMemorySessionRepository o PostgresSessionRepository
```

La visión artificial no conoce el repositorio. El almacenamiento en memoria y
PostgreSQL son intercambiables sin modificar detectores ni validadores.

## Modelo y estados

`EmotionalSession` es una entidad inmutable con ID, timestamps con zona horaria,
estado, emoción inicial, confianza, actividad, resultado y duración. Sus estados
son `created`, `in_progress`, `completed` y `cancelled`.

```text
CREATED -> IN_PROGRESS -> COMPLETED
    |            |
    +------------+------> CANCELLED
```

Una sesión completada exige todos los datos del resultado. Una cancelada puede
conservar información parcial. No se permite modificar una sesión terminal.

## Aplicación e infraestructura

`SessionRepository` es un puerto (`Protocol`) con estas operaciones:

```python
save(session) -> EmotionalSession
get_by_id(session_id) -> EmotionalSession | None
list_all() -> tuple[EmotionalSession, ...]
list_by_student(student_id) -> tuple[EmotionalSession, ...]
```

`SessionService` genera IDs y timestamps, controla las transiciones y adapta el
resultado mediante `complete_from_activity_status()`. El adaptador
`InMemorySessionRepository` mantiene una sola versión por ID durante la vida del
proceso. La etapa PostgreSQL incorpora la configuración, el motor SQLAlchemy,
el modelo ORM `SessionRecord` y `PostgresSessionRepository`. Este adaptador no
crea el esquema automáticamente; las tablas serán administradas con Alembic.

### Diseño de `sessions`

| Columna | Tipo PostgreSQL | Nulo | Propósito |
| --- | --- | --- | --- |
| `id` | `varchar(64)` | No | Identificador y clave primaria |
| `state` | `varchar(32)` | No | Estado del ciclo de sesión |
| `started_at` | `timestamptz` | No | Inicio con zona horaria |
| `completed_at` | `timestamptz` | Sí | Cierre o cancelación |
| `initial_emotion` | `varchar(64)` | Sí | Expresión facial estabilizada |
| `emotion_confidence` | `double precision` | Sí | Confianza entre 0 y 1 |
| `activity_id` | `varchar(128)` | Sí | Actividad corporal recomendada |
| `exercise_result` | `varchar(32)` | Sí | Resultado del ejercicio |
| `exercise_duration_seconds` | `double precision` | Sí | Duración no negativa |
| `student_id` | `varchar(64)` | Sí | Estudiante asociado, con clave foránea |

La tabla indexa `state` y `started_at`. Sus restricciones comprueban estados
válidos, rangos numéricos, registro conjunto de emoción y confianza, coherencia
de `completed_at` y presencia del resultado cuando el estado es `completed`.

## API de sesiones

Las rutas requieren un token Bearer obtenido mediante OAuth2:

| Método | Ruta | Operación |
| --- | --- | --- |
| `POST` | `/sessions` | Iniciar una sesión |
| `POST` | `/sessions/{session_id}/cancel` | Cancelar una sesión abierta |
| `GET` | `/sessions/{session_id}` | Consultar una sesión por ID |
| `GET` | `/sessions` | Listar sesiones autorizadas |
| `GET` | `/sessions?student_id={id}` | Consultar sesiones de un estudiante |

Un estudiante solo accede a sesiones asociadas a su perfil. Psicología y
administración pueden consultar sesiones de estudiantes. Una sesión asociada
no puede iniciarse si el estudiante no tiene consentimiento activo.

## Prueba manual

Con `.venv` activo y los modelos descargados:

```powershell
python scripts/run_session_test.py
```

Controles:

- `ESPACIO`: iniciar inmediatamente la actividad seleccionada;
- `R`: cancelar la sesión actual y comenzar otra;
- `Q`: cancelar la sesión abierta y salir.

Al completar una actividad, la consola muestra ID, timestamps, emoción,
confianza, actividad, resultado y duración. El registro existe hasta que termina
el proceso.

## Verificación arquitectónica

Desde la raíz del repositorio:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m compileall -q src scripts
git diff --check
```

Comprobar que dominio y aplicación no conocen persistencia concreta ni SQL:

```powershell
rg -n "infrastructure\.persistence|InMemorySessionRepository|sqlalchemy|psycopg|postgres" src/emotv/domain src/emotv/application
```

Comprobar que visión no conoce sesiones ni persistencia:

```powershell
rg -n "SessionService|SessionRepository|InMemorySessionRepository|PostgreSQL|SQLAlchemy" src/emotv/infrastructure/vision
```

Ambas búsquedas deben quedar vacías, salvo menciones no ejecutables que se hayan
revisado manualmente. Para inspeccionar el commit:

```powershell
git status --short
git diff --stat
git diff
git check-ignore -v models/weights/pose_landmarker_lite.task
```

El último comando debe confirmar que los pesos están ignorados. No deben entrar
al commit `.venv`, cachés, modelos, secretos ni resultados generados.

## Criterio de cierre

La subfase puede versionarse cuando las pruebas pasan, no aparecen dependencias
prohibidas, las migraciones están en `head`, `run_session_test.py` completa una
sesión con webcam y Git contiene únicamente cambios intencionales.

## Configuración de PostgreSQL

La conexión se configura únicamente mediante `DATABASE_URL`. Para el
desarrollo local, copia `.env.example` a `.env` y reemplaza sus valores:

```powershell
Copy-Item .env.example .env
$env:DATABASE_URL = "postgresql+psycopg://usuario:clave@localhost:5432/emotv"
```

El archivo `.env` está ignorado por Git y se carga automáticamente al importar
la configuración. SQLAlchemy crea conexiones de forma diferida, únicamente al
utilizar el engine. Psycopg 3 es el controlador PostgreSQL instalado. En
despliegue, `DATABASE_URL` debe provenir del gestor de secretos o de variables
del entorno, nunca del repositorio.

Una vez aplicada la migración, el repositorio se construye así:

```python
engine = create_database_engine()
session_factory = create_session_factory(engine)
repository = PostgresSessionRepository(session_factory)
service = SessionService(repository)
```

## Migraciones con Alembic

Alembic obtiene la conexión desde `DATABASE_URL`; `alembic.ini` no contiene
credenciales. La primera revisión crea `sessions` y sus índices:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
```

Para generar una migración futura después de modificar los modelos ORM:

```powershell
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describir cambio"
```

Revisa siempre el archivo generado antes de ejecutar `upgrade head`. Para
revertir exclusivamente la última revisión se puede usar `alembic downgrade -1`,
pero esta operación modifica el esquema y puede eliminar datos.

Las pruebas de integración ejercitan `PostgresSessionRepository` y
`SessionService` contra PostgreSQL real. Cada prueba se revierte mediante una
transacción externa:

```powershell
.venv\Scripts\python.exe -m pytest tests/integration -m integration
```
