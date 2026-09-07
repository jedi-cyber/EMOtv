# Sesiones y persistencia en memoria

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
        -> InMemorySessionRepository
```

La visión artificial no conoce el repositorio. Esto permitirá reemplazar el
almacenamiento en memoria por PostgreSQL sin modificar detectores ni validadores.

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
```

`SessionService` genera IDs y timestamps, controla las transiciones y adapta el
resultado mediante `complete_from_activity_status()`. El adaptador
`InMemorySessionRepository` mantiene una sola versión por ID durante la vida del
proceso. Esta subfase no incorpora SQL, SQLAlchemy ni PostgreSQL.

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
prohibidas, `run_session_test.py` completa una sesión con webcam y el listado de
Git contiene únicamente cambios intencionales. PostgreSQL y Alembic corresponden
a la siguiente subfase.
