# Modelo de datos

Derivado de las migraciones de `migrations/versions/` (de `20260908_01` a
`20261009_16`), aplicadas con `alembic upgrade head` sobre PostgreSQL 16 y
leído del esquema resultante (`information_schema`). Si este documento y las
migraciones difieren, mandan las migraciones.

PostgreSQL es la única base de datos. **No hay tablas de imágenes**: los
frames se procesan en memoria y se descartan.

```mermaid
erDiagram
  users ||--o| students : "user_id (CASCADE)"
  users ||--o{ chat_conversations : "user_id (CASCADE)"
  chat_conversations ||--o{ chat_messages : "conversation_id (CASCADE)"
  students ||--o{ consents : "student_id (CASCADE)"
  students |o--o{ sessions : "student_id (SET NULL)"
  users ||--o{ psychologist_assignments : "psychologist_user_id (CASCADE)"
  students ||--o{ psychologist_assignments : "student_id (CASCADE)"
  users |o--o{ psychologist_assignments : "assigned_by_user_id (SET NULL)"
  activities ||--o{ emotion_activity_recommendations : "activity_id (CASCADE)"
  expression_info ||--o{ emotion_activity_recommendations : "expression_key (CASCADE)"
  users |o--o{ expression_info : "reviewed_by_user_id (SET NULL)"

  users {
    varchar id PK
    varchar email UK
    varchar password_hash "argon2"
    varchar role "student | psychologist | admin"
    boolean is_active
    timestamptz created_at
    boolean must_change_password
    integer token_version
    boolean is_test_account "cuentas PRUEBA-NN"
  }
  students {
    varchar id PK
    varchar user_id FK,UK
    varchar student_code UK
  }
  consent_policies {
    varchar id PK "código:versión"
    varchar code UK "con version"
    varchar version UK "con code"
    varchar title
    varchar content
    timestamptz effective_at
    boolean is_demo
    boolean approved
    boolean is_active
  }
  consents {
    varchar id PK
    varchar student_id FK
    varchar policy_version "id de la política aceptada"
    timestamptz granted_at
    timestamptz revoked_at "nulo si sigue vigente"
  }
  sessions {
    varchar id PK
    varchar state "created | in_progress | recognized | completed | cancelled"
    timestamptz started_at
    timestamptz completed_at
    varchar student_id FK
    varchar initial_emotion "clave de la expresión registrada"
    float emotion_confidence
    timestamptz recognized_at
    varchar emotion_model_id
    varchar emotion_model_version
    varchar activity_id "sin FK: conserva el historial"
    varchar exercise_result "completed | skipped | cancelled"
    float exercise_duration_seconds
    integer exercise_steps_completed
    integer exercise_steps_total
    integer exercise_repetitions
  }
  activities {
    varchar id PK
    varchar name
    varchar description
    varchar required_posture
    float duration_seconds
    integer repetitions
    json steps "posture, instruction, duration_seconds"
  }
  expression_info {
    varchar expression_key PK
    varchar label_es
    varchar what_it_is
    varchar why_it_occurs
    varchar facial_cues
    varchar practice_tip
    varchar limitation_note
    varchar review_status "draft | reviewed"
    varchar reviewed_by_user_id FK
    timestamptz reviewed_at
    timestamptz updated_at
  }
  emotion_activity_recommendations {
    varchar expression_key PK,FK
    varchar activity_id PK,FK
    integer priority
  }
  psychologist_assignments {
    varchar psychologist_user_id PK,FK
    varchar student_id PK,FK
    timestamptz assigned_at
    varchar assigned_by_user_id FK
  }
  login_attempts {
    varchar id PK
    varchar email_hash "SHA-256, sin el correo"
    varchar ip
    timestamptz created_at
    boolean success
  }
  chat_conversations {
    varchar id PK
    varchar user_id FK
    timestamptz created_at
    timestamptz last_message_at
  }
  chat_messages {
    integer id PK
    varchar conversation_id FK
    varchar role "user | assistant"
    text content
    boolean in_scope
    varchar category
    timestamptz created_at
  }
  chat_rejection_counts {
    varchar category PK
    integer count
    timestamptz last_at
  }
```

## Tablas

| Tabla | Migración | Contenido |
| --- | --- | --- |
| `sessions` | `20260908_01`, `_02`, `20260916_05`, `20261008_11`, `20261009_14` | una sesión de análisis: estado, expresión registrada y su confianza, modelo usado y resultado de la actividad |
| `users`, `students`, `consents` | `20260908_03`, `20260918_06`, `20261009_16` | cuentas, perfil estudiantil (código, nunca nombre) y consentimientos con fecha de aceptación y revocación |
| `activities` | `20260915_04`, `20260921_08` | actividades con su secuencia de pasos (`steps` en JSON) y repeticiones |
| `consent_policies` | `20260918_07` | políticas de consentimiento versionadas; una sola activa |
| `login_attempts` | `20261006_09` | intentos de inicio de sesión para el límite por cuenta e IP; guarda el hash del correo |
| `psychologist_assignments` | `20261006_10` | qué estudiantes puede consultar cada cuenta de Psicología |
| `expression_info` | `20261008_12` | textos educativos de cada expresión y su estado de revisión |
| `emotion_activity_recommendations` | `20261009_13` | actividades recomendadas por expresión, en orden de prioridad |
| `chat_conversations`, `chat_messages`, `chat_rejection_counts` | `20261009_15` | conversaciones con Emi (retención de 90 días) y contadores agregados de preguntas rechazadas por categoría |

## Reglas que se leen en el esquema

- **Borrado de una cuenta.** `students`, `consents`, `chat_conversations`,
  `chat_messages` y las asignaciones se borran en cascada. `sessions.student_id`
  queda en nulo (`SET NULL`): por eso `scripts/testdata/delete_test_data.py`
  borra las sesiones de forma explícita antes de eliminar a un voluntario.
- **Historial estable.** `sessions.activity_id` y `consents.policy_version` no
  tienen clave foránea: si se elimina una actividad o cambia la política, el
  historial conserva el identificador registrado y la interfaz muestra
  «Actividad no disponible».
- **Sin imágenes ni lecturas en vivo.** Solo se guarda la expresión que el
  estudiante registró (`initial_emotion`, `emotion_confidence`,
  `recognized_at`); las lecturas en vivo no se persisten.
- **Sin el correo en los intentos de login.** `login_attempts.email_hash`
  guarda el SHA-256 del correo.
- **Emi.** `chat_rejection_counts` guarda solo un contador por categoría, sin
  texto ni usuario.
