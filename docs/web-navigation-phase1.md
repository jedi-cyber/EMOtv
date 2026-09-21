# Fase 1 — Navegación web

La fase se limita a que cada usuario encuentre sus módulos, reconozca dónde
está y pueda seguir el recorrido sin perder el contexto. No redefine la API,
los modelos de IA ni las reglas clínicas.

## Recorridos por rol

| Rol | Recorrido principal |
| --- | --- |
| Estudiante | Inicio → analizador facial → expresión reconocida → actividad sugerida → postura → resultado/sesiones. |
| Psicología | Inicio → estudiantes → sesiones del estudiante; también sesiones generales autorizadas. |
| Administración | Inicio → usuarios, administración de actividades y sesiones. |

Los accesos directos del inicio llevan a módulos permitidos para cada rol. La
vista de estudiantes usa `GET /students` y muestra el código institucional para
abrir `/students/:studentId/sessions`. Los permisos efectivos y el filtrado de
datos siguen siendo responsabilidad del backend.

## Casos especiales

- Una URL inexistente muestra 404 con regreso al inicio.
- Una ruta fuera del rol muestra acceso restringido sin detalles internos.
- Un JWT vencido redirige al login con un aviso claro; un fallo de conexión no
  elimina el token y ofrece reintentar.
- Una sesión de análisis activa advierte antes de salir, cancela en la API antes
  de navegar y mantiene la pantalla si la cancelación falla.
- Las consultas lentas muestran carga y los fallos del servicio ofrecen reintento.
- El menú móvil cierra con Escape, al tocar fuera o al elegir una ruta; el foco
  queda en el contenido tras navegar.

## Verificación mínima

`cd web`, `npm test` y `npm run build` verifican rutas por rol, 403/404, sesión
vencida, conexión, análisis activo, menú adaptable y acceso por teclado. Los
tests de componentes usan DOM simulado: **no validan visualmente los puntos de
corte CSS**. Antes de declarar el cierre visual, revisar manualmente en un
navegador aproximadamente a 1440, 900 y 390 px: menú, encabezado, tablas,
tarjetas, cámara, barra de progreso, foco y ausencia de desplazamiento horizontal.

## Orden y límites

Orden aplicado: rutas y permisos → layout/menú → contexto de ubicación y retorno
→ protección de sesión activa → estados de carga/error → recorridos y pruebas.
El sidebar colapsable queda como mejora opcional de baja prioridad.

No incluir en esta fase: rediseño profundo del dashboard, nuevos modelos de IA,
procesamiento corporal adicional, informes clínicos, cambios en persistencia o
administración completa de usuarios. Son fases funcionales posteriores.

El criterio funcional de navegación se cumple cuando el usuario puede recorrer
EMOtv, identificar sus funciones según el rol, su ubicación, la acción en curso
y su siguiente paso. La validación visual responsive indicada arriba sigue
siendo una comprobación manual previa al cierre definitivo de la fase.
