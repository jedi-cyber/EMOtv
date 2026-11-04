from enum import Enum


class Role(str, Enum):
    """Papeles internos. En la interfaz se muestran como Usuario, Docente,
    Administrador y Superadministrador."""

    # Usuario: conduce sesiones propias o con otras personas.
    STUDENT = "student"
    # Docente: supervisa a su grupo (revisa reportes e imágenes) y conduce sesiones
    # propias solo como demostración, para enseñar a usar EMOtv.
    PSYCHOLOGIST = "psychologist"
    # Administrador: persona con cargo superior en la Facultad; gestiona cuentas y grupos.
    ADMIN = "admin"
    # Superadministrador: soporte técnico (modelos, configuración, cuenta de administrador).
    SUPERADMIN = "superadmin"


# Papeles que conducen sesiones y pueden ver sus datos.
CONDUCTOR_ROLES = frozenset({Role.STUDENT, Role.PSYCHOLOGIST})
# Papeles de gestión: nunca acceden a sesiones ni resultados.
MANAGEMENT_ROLES = frozenset({Role.ADMIN, Role.SUPERADMIN})
