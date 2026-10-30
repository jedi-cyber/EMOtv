from enum import Enum


class Role(str, Enum):
    """Papeles internos. En la interfaz se muestran como Usuario, Docente,
    Administrador y Superadministrador."""

    # Usuario: conduce sesiones propias o con otras personas.
    STUDENT = "student"
    # Docente: tiene un grupo de usuarios y también conduce sesiones propias.
    PSYCHOLOGIST = "psychologist"
    # Administrador: persona con cargo superior en la Facultad; gestiona cuentas y grupos.
    ADMIN = "admin"
    # Superadministrador: soporte técnico (modelos, configuración, cuenta de administrador).
    SUPERADMIN = "superadmin"


# Papeles que conducen sesiones y pueden ver sus datos.
CONDUCTOR_ROLES = frozenset({Role.STUDENT, Role.PSYCHOLOGIST})
# Papeles de gestión: nunca acceden a sesiones ni resultados.
MANAGEMENT_ROLES = frozenset({Role.ADMIN, Role.SUPERADMIN})
