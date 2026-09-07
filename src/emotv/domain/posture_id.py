from enum import Enum


class PostureId(str, Enum):
    """Identificadores estables de las posturas conocidas por EMOtv."""

    ARMS_UP = "arms_up"
    ARMS_OPEN = "arms_open"
    ARMS_FORWARD = "arms_forward"
    HANDS_ON_HIPS = "hands_on_hips"
    SQUAT = "squat"
