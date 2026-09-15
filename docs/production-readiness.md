# Verificación y preparación para producción

Estado: base técnica de pruebas y configuración. **No equivale a aprobación de
un despliegue con estudiantes reales ni a certificación de accesibilidad o seguridad.**

## Comprobaciones automatizadas

```powershell
# Desde la raíz; pruebas unitarias e integración HTTP/WebSocket aislada.
python -m pytest -q -p no:cacheprovider
python -m alembic upgrade head --sql

# Frontend; instalación reproducible usando package-lock.json.
cd web
npm ci
npm test
npm run build
```

Las pruebas del frontend cubren avisos, carga, confirmaciones con teclado,
restauración de foco, rutas por rol, navegación y contrato HTTP. El analizador
cubre navegador sin soporte, permiso denegado, cámara ausente, consentimiento
ausente, progreso, finalización y limpieza ante desconexión o desmontaje.

La integración backend ejecuta peticiones REST y mensajes WebSocket contra
FastAPI con adaptadores SQLAlchemy aislados. Comprueba inicio, finalización,
cancelación, desconexión, propiedad estudiantil y revocación de cuenta o
consentimiento durante el análisis. El procesador es determinista: estas pruebas
no verifican precisión de IA, hardware ni transporte de red real.

Las pruebas PostgreSQL existentes requieren su entorno de integración específico.
SQLite y generación de SQL no sustituyen comprobar migraciones y restricciones
en una instancia PostgreSQL de pruebas. Nunca apuntar pruebas destructivas a
la base de producción.

## HTTP, CORS y WebSocket

El `.env` pertenece al servidor. No exponer DATABASE_URL ni JWT_SECRET_KEY en
variables `VITE_*`, porque estas se incorporan al JavaScript público.

Ejemplo de configuración, con valores reales suministrados por TI:

```dotenv
ENVIRONMENT=production
CORS_ORIGINS=https://emotv.example.edu
TRUSTED_HOSTS=api.emotv.example.edu
```

Producción requiere también DATABASE_URL y un secreto JWT aleatorio de al menos
32 caracteres. La configuración rechaza comodines, orígenes HTTP y valores
provisionales. Los hosts se escriben sin esquema ni puerto; los orígenes incluyen
esquema y puerto cuando corresponde. Las listas son separadas por comas.

La API permite Bearer sin cookies (`allow_credentials=False`), valida Host y
añade no-store, nosniff, bloqueo de marcos y política de referencia. En producción
añade HSTS y CSP restrictiva para respuestas de API. Los WebSockets validan Origin
por separado: CORS no los protege. En producción se exige Origin explícito de la
lista; los clientes no navegador deben enviarlo además del mensaje de autenticación.

El frontend debe servirse por separado, no usando el HTML antiguo de `/web`.
La CSP de producción de la API bloquea scripts de esa demostración antigua.
El proxy que sirve `web/dist` debe configurar sus propias cabeceras: la API no
protege automáticamente los archivos que sirve otro proceso.

Configurar HTTPS/WSS, cámara limitada a self, bloqueo de embedding y una CSP
del frontend que permita únicamente sus assets y los hosts HTTP/WSS de la API.
Tener en cuenta los estilos dinámicos actuales al definir la política. Verificarla
primero en modo report-only. La política de cámara debe permitir la cámara propia
del navegador; no habilitar micrófono, geolocalización o embedding innecesarios.

Vite es solo desarrollo. El proxy de desarrollo incluye usuarios, estudiantes,
sesiones, actividades, autenticación y WebSockets. Para despliegue, configurar
el proxy inverso equivalente o `VITE_API_URL` con la URL pública de la API.

## Accesibilidad y diseño adaptable

Implementado: enlace para saltar al contenido, foco visible, diálogo con foco
confinado, fondo inerte, Escape y restauración de foco; avisos con roles de
anuncio y barra con valor accesible. Los estados tienen texto además de color.
El diseño adapta navegación, cámara y formularios a pantallas pequeñas y reduce
animaciones cuando el usuario lo solicita.

Revisión manual pendiente antes de aceptar una versión:

- Recorrer login, navegación, formularios y diálogos solo con Tab/Shift+Tab/Enter/Escape.
- Probar lector de pantalla: etiquetas, errores, tablas, anuncios y progreso.
- Revisar contraste y zoom 200 % y 400 %, sin pérdida de controles.
- Probar anchos 320, 375, 768 y 1280 px; revisar emails e IDs largos.
- Probar cámara en Chrome/Edge/Firefox y Safari móvil bajo HTTPS.
- Denegar permiso, desconectar dispositivo/red y salir mientras llega el permiso.
- Comprobar que ninguna cámara permanece encendida tras cancelar o navegar.
- Probar sin consentimiento y revocándolo durante la actividad.

Las pruebas DOM no validan geometría, contraste calculado ni comportamiento
completo del lector de pantalla. Añadir auditoría automatizada de accesibilidad
y pruebas E2E de navegador al pipeline antes del lanzamiento.

## Seguridad y privacidad: puertas de salida pendientes

La política institucional está en [privacy-data-governance.md](privacy-data-governance.md).
Mantiene carácter preliminar: no se ha aprobado un plazo legal de retención ni
automatizado la eliminación por documentarlo.

- Aprobar consentimiento, versión vigente, responsables y canales de derechos.
- Implementar asignación psicólogo–estudiante y separar administración funcional
  de acceso a resultados. Actualmente esos roles tienen acceso amplio por rol;
  **no habilitar ese acceso indiscriminado en producción asistencial**.
- Implementar auditoría de accesos y modificaciones, sin tokens, contraseñas,
  imágenes ni cadenas de conexión en logs.
- Automatizar y verificar retención, purga y tratamiento de backups aprobados.
- Migrar autenticación a cookies HttpOnly/Secure con protección CSRF, o documentar
  formalmente la excepción Bearer del MVP; añadir revocación, rotación y MFA.
- Limitar intentos de login, conexiones simultáneas, tiempo de análisis y tamaño
  y frecuencia de frames en proxy y aplicación. El límite actual por frame no
  constituye protección completa contra agotamiento de recursos.
- Cifrar backups, usar usuario de base con mínimo privilegio y probar restauración.
- Usar bases y secretos distintos por entorno; revisar dependencias y lockfiles.
- Ejecutar pruebas de carga, revisión de seguridad y plan de respuesta a incidentes.

Los fotogramas se procesan en memoria; no se añade grabación de video. Revisar
también proxy, observabilidad y proveedores para evitar almacenamiento accidental.
La emoción facial no es diagnóstico; las posturas validan actividades corporales,
no reconocimiento de emociones corporales.

## Problemas de certificados npm

Si Node reciente no reconoce el certificado institucional pero Windows sí:

```powershell
$env:NODE_USE_SYSTEM_CA = "1"
npm ci
```

Si continúa el error, pedir a TI el certificado CA y configurar su confianza en
Node. No desactivar strict-ssl ni usar NODE_TLS_REJECT_UNAUTHORIZED=0.
