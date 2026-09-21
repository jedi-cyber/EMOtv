import math


def calculate_angle(a, b, c) -> float:
    """
    Calcula el ángulo ABC.
    El punto B es el vértice.
    """

    ba_x = a.x - b.x
    ba_y = a.y - b.y

    bc_x = c.x - b.x
    bc_y = c.y - b.y

    dot = ba_x * bc_x + ba_y * bc_y

    mag_ba = math.sqrt(ba_x**2 + ba_y**2)
    mag_bc = math.sqrt(bc_x**2 + bc_y**2)

    if mag_ba == 0 or mag_bc == 0:
        return 0.0

    cos_angle = dot / (mag_ba * mag_bc)
    cos_angle = max(-1.0, min(1.0, cos_angle))

    return math.degrees(math.acos(cos_angle))


def calculate_3d_angle(a, b, c) -> float:
    """Calcula el ángulo ABC con profundidad normalizada (x, y, z)."""
    ba = (a.x - b.x, a.y - b.y, a.z - b.z)
    bc = (c.x - b.x, c.y - b.y, c.z - b.z)
    magnitude = math.sqrt(sum(value * value for value in ba)) * math.sqrt(
        sum(value * value for value in bc)
    )
    if magnitude == 0:
        return 0.0
    cosine = sum(left * right for left, right in zip(ba, bc)) / magnitude
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
