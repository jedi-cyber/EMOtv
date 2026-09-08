# API HTTP de EMOtv

## Ejecución

Configura `DATABASE_URL` y `JWT_SECRET_KEY` en `.env`, aplica las migraciones y
arranca FastAPI desde la raíz del proyecto:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe scripts/run_api.py
```

La documentación interactiva queda disponible en `/docs`. `.env.example` solo
debe contener valores de referencia seguros para versionar, nunca credenciales.

## Autenticación

`POST /auth/token` recibe el formulario OAuth2 con `username` (correo) y
`password`. Las demás rutas protegidas usan:

```http
Authorization: Bearer <access_token>
```

`GET /auth/me` devuelve la identidad actual. `GET /auth/users` requiere permiso
administrativo.

## Sesiones

| Método | Ruta | Acceso |
| --- | --- | --- |
| `POST` | `/sessions` | Estudiante propio, psicología o administración |
| `POST` | `/sessions/{id}/cancel` | Propietario o rol autorizado |
| `GET` | `/sessions/{id}` | Propietario o rol autorizado |
| `GET` | `/sessions` | Sesiones permitidas para el usuario |
| `GET` | `/sessions?student_id={id}` | Sesiones del estudiante indicado |

Para estudiantes, el servidor fuerza el alcance al perfil propio y rechaza un
`student_id` ajeno con `403`. Una sesión inexistente devuelve `404`. Iniciar una
sesión asociada exige consentimiento activo.

## Actividades

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET` | `/activities` | Cualquier usuario autenticado |
| `GET` | `/activities/{id}` | Cualquier usuario autenticado |
| `POST` | `/activities` | Administración |
| `PUT` | `/activities/{id}` | Administración |
| `DELETE` | `/activities/{id}` | Administración |

Ejemplo para crear o reemplazar una actividad:

```json
{
  "id": "arms_open_8s",
  "name": "Apertura de brazos",
  "description": "Mantén ambos brazos abiertos a la altura de los hombros.",
  "required_posture": "arms_open",
  "duration_seconds": 8.0,
  "repetitions": 2
}
```

Al actualizar, el ID del cuerpo y el de la ruta deben coincidir. El catálogo es
local y se reconstruye al reiniciar la aplicación; persistirlo en PostgreSQL es
parte de la siguiente etapa.

## Respuestas de error

- `401`: token ausente, inválido o vencido;
- `403`: el rol o la propiedad no permite la operación;
- `404`: recurso inexistente;
- `409`: estado incompatible, ID duplicado o actualización inconsistente;
- `422`: cuerpo o parámetros inválidos;
- `503`: servicio no configurado.

## Verificación previa al commit

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q src scripts tests
.venv\Scripts\python.exe -m alembic current
git diff --check
git status --short
git diff --stat
```

Revisa que `.env`, pesos, entornos virtuales y cachés no aparezcan entre los
archivos que se versionarán. Evita ejecutar `git add .` antes de revisar el
estado del repositorio.
