"""Guía de uso de EMOtv: tareas paso a paso para cada papel.

Es la única fuente de la guía: la página «Guía de uso» muestra los temas del
papel de cada cuenta y Emi recibe los de Usuario y Docente en su conocimiento
(sin las notas, que ya cubren sus otras secciones). Solo describe lo que hay en
la interfaz, con los nombres de sus botones, y respeta las reglas del proyecto:
EMOtv estima una expresión, no diagnostica ni evalúa a nadie, y no guarda
imágenes de las personas evaluadas. Las funciones congeladas (actividades
corporales, imágenes abstractas, examen) no aparecen.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from emotv.domain.role import Role

USER, DOCENTE, ADMIN, SUPERADMIN = Role.STUDENT, Role.PSYCHOLOGIST, Role.ADMIN, Role.SUPERADMIN
# Emi responde a usuarios y docentes.
EMI_ROLES = (USER, DOCENTE)
# Temas que el conocimiento de Emi ya cubre en otra sección.
EMI_SKIPPED = frozenset({"statistics"})
ROLE_NAMES = {USER: "Usuario", DOCENTE: "Docente"}


@dataclass(frozen=True, slots=True)
class GuideTopic:
    id: str
    title: str
    roles: frozenset[Role]
    steps: tuple[str, ...]
    note: str | None = None


def _topic(id: str, title: str, roles: Iterable[Role], *steps: str, note: str | None = None) -> GuideTopic:
    return GuideTopic(id, title, frozenset(roles), tuple(steps), note)


GUIDE: tuple[GuideTopic, ...] = (
    _topic("first-steps", "Antes de la primera sesión", (USER, DOCENTE),
           "Entra con tu cuenta. Si la contraseña es provisional, EMOtv te pide cambiarla.",
           "Acepta el compromiso de confidencialidad: sin él no inicias sesiones con otras personas. Lo vuelves a ver "
           "en «Consentimiento»."),
    _topic("material", "Preparar el material", (USER, DOCENTE),
           "En «Cuestionarios», «Usar la plantilla inicial» o «Nuevo cuestionario».",
           "En «Protocolos», «Usar la plantilla inicial» agrega «Emociones básicas 4 a 6 años», para niños. «Copiar y "
           "modificar» copia una plantilla de tu docente.",
           "«Nuevo protocolo» pregunta si es para adultos o para niños. «Modo accesible» pone pictogramas, botones "
           "grandes y pausas más largas.",
           "Los pasos pueden ser una imagen, «¿Qué emoción es?», un ejercicio de práctica o «Haz la misma cara» (la "
           "imagen es el modelo).",
           note="Con niños solo se ofrecen imágenes «Para niños» aprobadas. EMOtv no calcula puntajes."),
    _topic("own-images", "Subir imágenes propias", (USER,),
           "En «Imágenes», «Subir imágenes». Nunca fotografías de personas evaluadas.",
           "EMOtv busca personas en cada imagen y luego la revisa tu docente: se usa solo si la aprueba."),
    _topic("conduct", "Conducir una sesión", (USER, DOCENTE),
           "En el «Analizador» elige un protocolo, o ninguno y con quién es la sesión: Conmigo, Un adulto o Un niño o "
           "niña.",
           "Confirma la autorización y anota el código de la sesión (por ejemplo, S-4F7K2Q) en el formato firmado.",
           "Con protocolo, «Crear el enlace de la pantalla de la persona» y «Abrir la pantalla de la persona» (o "
           "«Copiar enlace» para otro dispositivo). Esa pantalla no muestra resultados.",
           "Calibra con la cara tranquila; los pasos avanzan solos. Puedes saltar un paso, apagar la señal de la "
           "práctica y marcar «Se distrajo», «Se rió», «Lloró» o «Pidió parar».",
           "Si la persona o su tutor lo piden, detén la sesión: «La persona pidió parar» o «El tutor pidió parar».",
           note="La cámara se abre en el navegador; cada imagen se analiza en memoria y se descarta."),
    _topic("after", "Después de la sesión", (USER,),
           "En «Mis sesiones» ves la línea de tiempo y las métricas, que describen lo ocurrido sin valorar a nadie.",
           "«Redactar el reporte» y «Enviar a revisión». Si vuelve con observaciones, corrígelo y reenvíalo.",
           "«Pedir que se elimine» borra la sesión cuando tu docente lo ejecuta."),
    _topic("supervise", "Supervisar al grupo", (DOCENTE,),
           "No estás en cada sesión: «Por revisar» reúne los reportes enviados y los pedidos de eliminación, del más "
           "antiguo al más nuevo.",
           "En un reporte, «Comentar» cada sección y luego «Aprobar» o «Devolver con observaciones».",
           "En un pedido de eliminación, abre la sesión y «Eliminar la sesión».",
           "En «Imágenes por revisar» apruebas o eliminas las que subió tu grupo.",
           note="Revisas resultados y textos, nunca imágenes de las personas evaluadas: EMOtv no las guarda."),
    _topic("teach", "Material del grupo y demostraciones", (DOCENTE,),
           "En «Estímulos» subes imágenes para tu grupo.",
           "«Compartir con mi grupo» convierte un protocolo o cuestionario en plantilla.",
           "Tus sesiones propias son de demostración, para enseñar: no cuentan en las estadísticas."),
    _topic("statistics", "Estadísticas", (USER, DOCENTE),
           "«Estadísticas» cuenta sesiones, nunca personas. La del docente resume a su grupo."),
    _topic("admin-accounts", "Cuentas y grupos", (ADMIN,),
           "En «Cuentas y grupos», «Crear cuenta» da de alta a docentes y usuarios, y «Asignar usuarios» arma el "
           "grupo de cada docente. Cada usuario tiene un solo docente.",
           "«Restablecer clave» da una contraseña provisional; el cambio queda en la auditoría.",
           note="La administración no accede a sesiones, reportes ni resultados."),
    _topic("admin-stimuli", "Estímulos institucionales", (ADMIN,),
           "«Agregar el banco inicial» incorpora 18 dibujos de creación propia: seis emociones básicas en tres "
           "versiones. Los usa la plantilla «Emociones básicas 4 a 6 años».",
           "«Agregar estímulo» sube una imagen para toda la Facultad, con su origen y su licencia. Nunca fotografías "
           "de personas evaluadas.",
           "«Retirar» deja de ofrecer una imagen sin cambiar las sesiones que ya la usaron."),
    _topic("audit", "Auditoría", (ADMIN, SUPERADMIN),
           "«Auditoría» registra quién hizo qué y cuándo, sin el contenido de sesiones ni reportes."),
    _topic("support", "Soporte técnico", (SUPERADMIN,),
           "En «Modelos» se elige el modelo de expresión: HSEmotion (principal) o FER+ (respaldo).",
           "En «Catálogo de expresiones» se editan los textos educativos del resultado, que también usa Emi.",
           "En «Cuenta de administrador» se crea o restablece la cuenta de la administración."),
)


def guide_for(role: Role) -> tuple[GuideTopic, ...]:
    """Temas de un papel, en el orden de la guía."""
    return tuple(topic for topic in GUIDE if role in topic.roles)


def guide_knowledge() -> str:
    """Los temas de Usuario y Docente en el formato del conocimiento de Emi."""
    lines = ["## Guía de uso (cómo hacer cada tarea)"]
    for topic in GUIDE:
        roles = [ROLE_NAMES[role] for role in EMI_ROLES if role in topic.roles]
        if roles and topic.id not in EMI_SKIPPED:
            lines.append(f"### {topic.title} ({', '.join(roles)})")
            lines.extend(f"{number}. {step}" for number, step in enumerate(topic.steps, start=1))
    return "\n".join(lines)
