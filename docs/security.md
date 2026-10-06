# Seguridad del repositorio y credenciales

## Credencial antigua en el historial público

El commit `8c00d0a` agregó el script temporal `.tmp_check_login.py`, que
contenía en texto plano la contraseña de la cuenta `admin` de una base local de
desarrollo. El commit `e7ab22f` lo eliminó, pero el archivo **sigue en el
historial público** de GitHub: cualquiera puede leerlo.

Estado de esa credencial:

- Pertenecía a una base PostgreSQL local que ya no existe; la base actual se
  creó desde cero y su administrador tiene otra contraseña. Por eso se
  considera **rotada** y no da acceso a ningún sistema de EMOtv.
- Si esa misma contraseña se usó en cualquier otro servicio o cuenta, cámbiala
  allí también.
- Ningún despliegue (local, Docker o en la nube) debe reutilizarla. Crea el
  administrador con `scripts/security/create_admin.py`, que genera una
  contraseña nueva cada vez.

El detector de secretos incluye dos reglas pensadas para este caso: contraseñas
literales pasadas a `authenticate()`/`login()` y scripts temporales `.tmp_*`
versionados.

## Detector de secretos y hook de pre-commit

`scripts/security/check_secrets.py` (Python estándar, sin dependencias) busca
credenciales en lo que se va a confirmar:

```powershell
python scripts/security/check_secrets.py          # archivos en staging
python scripts/security/check_secrets.py --all    # todos los archivos versionados
```

Devuelve 0 si no hay hallazgos y 1 si los hay. Muestra la ruta, la línea y la
regla, con el valor enmascarado (`abc***`). Los archivos binarios o que no son
UTF-8 se omiten con un aviso.

### Activar el hook (una vez por clon)

```powershell
git config core.hooksPath .githooks
```

Desde entonces, cada `git commit` ejecuta `.githooks/pre-commit`, que corre el
detector sobre los archivos en staging y bloquea el commit si encuentra algo.
El hook usa el Python de `.venv` si existe y comprueba que el intérprete
realmente funcione (en Windows, `python3` puede ser el acceso directo de
Microsoft Store). Si no encuentra Python, bloquea el commit.

El hook pasa el código de prueba por stdin y ejecuta el detector como módulo
(`python -m scripts.security.check_secrets`). Con el servicio de sandbox de
Codex activo en Windows, Python lanzado desde Git Bash termina sin ejecutar
nada y con código 0 si recibe `-c` o la ruta de un archivo existente; esta
forma de invocarlo evita el problema. Para revisar a mano desde Git Bash en
ese equipo usa también `python -m scripts.security.check_secrets --all`.

Además, el workflow `.github/workflows/secrets.yml` ejecuta el detector con
`--all` en cada push y pull request, por si alguien no activó el hook.

### Si el detector encuentra algo

1. Si es una credencial real: quítala del código, léela de una variable de
   entorno (`.env`, que no se versiona) y **rótala**, aunque el commit no se
   haya publicado.
2. Si es un dato ficticio de prueba: agrega una entrada a `.secrets-allowlist`
   con el formato `ruta:patrón`, por ejemplo
   `tests/unit/test_login.py:wrong-password`. La ruta admite comodines y el
   patrón es una expresión regular que se busca en la línea. Explica la
   entrada con un comentario. La allowlist se lee desde el índice: prepárala
   con `git add` para que tenga efecto.

No uses `git commit --no-verify` para saltar el detector.

## Restablecer la contraseña de un administrador

```powershell
python scripts/security/reset_admin_password.py --email admin@ejemplo.local
# En Docker:
docker compose --env-file .env.docker exec api python scripts/security/reset_admin_password.py --email admin@ejemplo.local
```

El script genera una contraseña aleatoria, guarda solo su hash, cierra las
sesiones abiertas (incrementa `token_version`) y obliga a cambiarla en el
primer acceso. La contraseña se muestra una sola vez en la terminal; no se
acepta por argumento para que no quede en el historial del shell.

Solo funciona si `DATABASE_URL` apunta a `localhost` o a un host listado en
`ALLOWED_ADMIN_RESET_HOSTS` (en Docker vale `db`). Así no se puede usar por
error contra una base remota.

## Inicio de sesión

### Límite de intentos

`POST /auth/token` cuenta los fallos en la tabla `login_attempts` de
PostgreSQL, así que el límite se respeta aunque la API corra en varios
procesos. Por defecto:

| Límite | Valor | Variable |
|--------|-------|----------|
| Fallos por correo + IP | 5 | `LOGIN_MAX_FAILURES_PER_ACCOUNT` |
| Fallos por IP | 20 | `LOGIN_MAX_FAILURES_PER_IP` |
| Ventana | 15 minutos | `LOGIN_ATTEMPT_WINDOW_MINUTES` |

Al superar cualquiera de los dos, la API responde `429` con el mismo mensaje
genérico y la cabecera `Retry-After`. Un acceso correcto reinicia el contador
de esa combinación correo + IP; el contador por IP no se reinicia, porque si
no alguien podría intercalar accesos con su propia cuenta para probar
contraseñas de otras. Mientras está bloqueado, el intento no se verifica ni se
registra.

El correo se guarda como SHA-256, no en claro. Es un seudónimo, no un
anonimato: quien tenga la base puede comprobar si un correo concreto intentó
entrar. Los registros de más de 24 horas se eliminan al insertar uno nuevo.

Límites conocidos:

- **IP compartida en Docker Desktop.** Docker Desktop (Windows y macOS) no
  conserva la IP del cliente: todas las conexiones llegan con la IP interna de
  Docker o de Caddy. El límite por IP actúa entonces como un límite global; si
  bloquea a usuarios legítimos (por ejemplo, en una prueba con varias
  personas), sube `LOGIN_MAX_FAILURES_PER_IP`. El límite por correo sigue
  funcionando por cuenta.
- **`X-Forwarded-For`.** nginx reemplaza esa cabecera con la IP de la
  conexión. Si se agregara a la que envía el cliente, uvicorn tomaría una IP
  inventada y el límite se podría saltar. Un despliegue en la nube con otro
  proxy debe configurar qué proxy es de confianza antes de usar su IP.
- **Concurrencia.** El conteo y el registro no son atómicos: varios intentos
  simultáneos pueden superar el límite por unos pocos antes de bloquearse.

### Respuesta uniforme

Usuario inexistente, contraseña incorrecta y cuenta inactiva devuelven el
mismo `401 Correo o contraseña incorrectos`. En los tres casos se verifica un
hash argon2 (uno ficticio si el usuario no existe), para que el tiempo de
respuesta no revele qué correos están registrados.

### Política de contraseñas

En `/auth/change-password`, que también usa el primer acceso:

- al menos 12 caracteres (el sistema ya exigía 12, que cumple el mínimo de 10
  pedido para esta etapa);
- distinta del correo;
- distinta de la contraseña anterior.

## Token de acceso en `sessionStorage`

El navegador guarda el JWT en `sessionStorage` y lo envía en la cabecera
`Authorization`; no se usan cookies. Es una decisión consciente para esta
etapa:

- **Ventajas:** no hay riesgo de CSRF (el navegador no envía el token solo),
  el token desaparece al cerrar la pestaña y el WebSocket de análisis se
  autentica con el mismo token.
- **Riesgo:** cualquier JavaScript que se ejecute en la página puede leer
  `sessionStorage`. Un XSS permitiría robar el token y usarlo desde otro
  equipo hasta que venza (`ACCESS_TOKEN_EXPIRE_MINUTES`, 30 minutos). Una
  cookie `HttpOnly` evitaría la lectura, aunque no el uso del token desde la
  propia página comprometida.
- **Mitigaciones actuales:** React escapa el contenido por defecto; nginx
  envía una `Content-Security-Policy` que solo permite scripts propios, sin
  `inline` ni dominios externos; el token dura 30 minutos; cambiar la
  contraseña o desactivar la cuenta incrementa `token_version` e invalida los
  tokens anteriores, también en el WebSocket.

Si el token vence o se revoca durante un análisis, el WebSocket cierra con el
código `4401`, el servidor cancela la sesión en curso y el navegador apaga la
cámara y vuelve al login con el aviso "Tu sesión venció".

## Reescribir el historial (opcional)

Se puede borrar `.tmp_check_login.py` de todo el historial con
[`git filter-repo`](https://github.com/newren/git-filter-repo), pero:

- cambia el hash de todos los commits posteriores, así que exige
  `git push --force` y que cada clon se vuelva a clonar o se rehaga;
- no borra copias que ya existan en forks, clones o cachés de terceros;
- debe coordinarse con todas las personas que trabajan en el repositorio.

Como la credencial ya está rotada, **no es necesario**. No lo ejecutes sin
acordarlo antes.
