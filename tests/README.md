# Pruebas de EMOtv

Las pruebas unitarias se encuentran en `tests/unit/` y no necesitan webcam.
Utilizan resultados simulados para validar la lógica de forma determinista.

Con las dependencias de desarrollo instaladas:

```powershell
python -m pytest
```

Alternativa con la biblioteca estándar:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Cobertura funcional de la etapa corporal

- configuración y descarga segura del modelo;
- frames inválidos y ausencia de pose;
- conversión BGR a RGB;
- mapeo de landmarks y cálculo de confianza;
- timestamps crecientes y cierre del detector;
- dibujo, visibilidad y coordenadas fuera del frame;
- altura de muñecas y ángulos de codos;
- tolerancias configurables;
- transiciones de la máquina de estados;
- progreso normalizado, reinicio y estado terminal;
- barra visual y mensajes del ejercicio.

## Cobertura del MVP emocional

- catálogo local y validación de actividades;
- asociaciones emoción–actividad y referencias inválidas;
- ventana móvil, confianza, consenso y empates emocionales;
- estados y transiciones del controlador integrado;
- espera de postura, progreso, finalización y reinicio;
- construcción del resultado final en memoria;
- compatibilidad de `PoseService` con posturas genéricas.

## Cobertura de sesiones

- valores serializables de `SessionState`;
- invariantes, timestamps e inmutabilidad de `EmotionalSession`;
- contrato estructural `SessionRepository`;
- creación, inicio, finalización y cancelación con `SessionService`;
- prevención de transiciones repetidas e IDs duplicados;
- conversión de `EmotionalActivityStatus` en una sesión completada;
- almacenamiento, actualización, recuperación y listado en memoria.
- mapeo ORM y operaciones de `PostgresSessionRepository` en una base aislada;
- intercambiabilidad entre el repositorio SQLAlchemy y `SessionService`.
- consultas de sesiones por ID y por estudiante;
- restricciones de propiedad de sesiones según el rol autenticado;
- ciclo CRUD y permisos del catálogo de actividades.

Las pruebas automatizadas no reemplazan la prueba manual con distintas
personas, distancias, fondos e iluminación.

## Pruebas de integración PostgreSQL

Requieren una `DATABASE_URL` válida y el esquema actualizado. Cada caso usa IDs
únicos y una transacción externa con savepoints que se revierte al terminar.

```powershell
python -m alembic upgrade head
python -m pytest tests/integration -m integration
```

Para ejecutar únicamente las pruebas unitarias:

```powershell
python -m pytest tests/unit
```

La integración de autenticación comprueba login OAuth2, JWT, `/auth/me`, roles
y PostgreSQL real sin conservar usuarios de prueba:

```powershell
python -m pytest tests/integration/test_authentication_api.py -m integration
```
