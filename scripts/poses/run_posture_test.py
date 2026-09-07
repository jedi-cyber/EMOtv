from __future__ import annotations

import argparse
from dataclasses import dataclass

import cv2
import numpy as np

from emotv.config import (
    CAMERA_INDEX,
    POSE_MODEL_PATH,
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)
from emotv.domain import PoseLandmarks, PostureId, PostureResult
from emotv.infrastructure.vision.camera.opencv_camera import (
    CameraConfig,
    OpenCVCamera,
)
from emotv.infrastructure.vision.movement_analysis import (
    PostureValidator,
    calculate_angle,
)
from emotv.infrastructure.vision.pose_detection import PoseDetector
from emotv.interfaces.ui.pose_drawer import PoseDrawer, PoseDrawingStyle
from emotv.shared.performance.monitor import PerformanceMonitor


WINDOW_NAME = "EMOtv - Posture Test"
SUCCESS_COLOR = (0, 255, 0)
ERROR_COLOR = (0, 0, 255)
INFO_COLOR = (255, 255, 255)


@dataclass(frozen=True, slots=True)
class PosturePresentation:
    name: str
    instruction: str


POSTURE_PRESENTATIONS = {
    PostureId.ARMS_UP: PosturePresentation(
        name="Brazos levantados",
        instruction="Levanta y extiende ambos brazos sobre los hombros.",
    ),
    PostureId.ARMS_OPEN: PosturePresentation(
        name="Brazos abiertos",
        instruction="Extiende ambos brazos hacia los lados a la altura de hombros.",
    ),
    PostureId.HANDS_ON_HIPS: PosturePresentation(
        name="Manos en las caderas",
        instruction="Coloca ambas manos en las caderas y abre los codos.",
    ),
}

KEY_TO_POSTURE = {
    ord("1"): PostureId.ARMS_UP,
    ord("2"): PostureId.ARMS_OPEN,
    ord("3"): PostureId.HANDS_ON_HIPS,
}


def arm_angles(pose: PoseLandmarks) -> tuple[float, float]:
    """Mantiene disponible el cálculo usado por pruebas y diagnóstico."""

    left = calculate_angle(
        pose.left_shoulder,
        pose.left_elbow,
        pose.left_wrist,
    )
    right = calculate_angle(
        pose.right_shoulder,
        pose.right_elbow,
        pose.right_wrist,
    )
    return left, right


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prueba interactiva de posturas corporales de EMOtv.",
    )
    parser.add_argument(
        "--posture",
        choices=[posture.value for posture in POSTURE_PRESENTATIONS],
        default=PostureId.ARMS_UP.value,
        help="Postura objetivo inicial (por defecto: arms_up).",
    )
    return parser


def diagnostic_lines(result: PostureResult) -> tuple[str, ...]:
    measurements = result.measurements
    lines: list[str] = []

    if "left_elbow_angle" in measurements:
        lines.append(
            "Codos: "
            f"izq {measurements['left_elbow_angle']:.1f} | "
            f"der {measurements['right_elbow_angle']:.1f} grados"
        )
    if result.posture_id is PostureId.ARMS_OPEN:
        lines.append(
            "Altura munecas: "
            f"izq {measurements['left_wrist_height_delta']:.3f} | "
            f"der {measurements['right_wrist_height_delta']:.3f}"
        )
    if result.posture_id is PostureId.HANDS_ON_HIPS:
        lines.append(
            "Distancia mano-cadera: "
            f"izq {measurements['left_wrist_hip_distance']:.3f} | "
            f"der {measurements['right_wrist_hip_distance']:.3f}"
        )
    if result.failed_rules:
        lines.append("Ajustar: " + ", ".join(result.failed_rules[:2]))

    return tuple(lines)


def draw_text_lines(
    frame: np.ndarray,
    lines: tuple[tuple[str, tuple[int, int, int]], ...],
) -> None:
    for index, (text, color) in enumerate(lines):
        cv2.putText(
            frame,
            text,
            (15, 30 + index * 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            color,
            2,
            cv2.LINE_AA,
        )


def main(initial_posture: PostureId = PostureId.ARMS_UP) -> None:
    if initial_posture not in POSTURE_PRESENTATIONS:
        raise ValueError(f"Postura no disponible: {initial_posture.value}")
    if not POSE_MODEL_PATH.is_file():
        print(f"[ERROR] No se encontro el modelo de pose: {POSE_MODEL_PATH}")
        print("Ejecuta: python scripts/poses/download_pose_model.py")
        return

    validator = PostureValidator()
    correct_drawer = PoseDrawer(
        PoseDrawingStyle(connection_color=SUCCESS_COLOR),
    )
    incorrect_drawer = PoseDrawer(
        PoseDrawingStyle(
            landmark_color=(0, 165, 255),
            connection_color=ERROR_COLOR,
        ),
    )
    camera = OpenCVCamera(
        CameraConfig(
            device_index=CAMERA_INDEX,
            width=TARGET_WIDTH,
            height=TARGET_HEIGHT,
            fps=TARGET_FPS,
        )
    )
    monitor = PerformanceMonitor()
    selected_posture = initial_posture

    print("=== EMOtv - Posture Test ===")
    print("1: arms_up | 2: arms_open | 3: hands_on_hips")
    print("Q: salir")

    try:
        with camera, PoseDetector() as detector:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

            while True:
                presentation = POSTURE_PRESENTATIONS[selected_posture]
                frame = camera.read()
                pose_result = detector.detect(frame)
                monitor.update_frame()

                if pose_result.detected and pose_result.landmarks is not None:
                    posture_result = validator.validate(
                        pose_result.landmarks,
                        selected_posture,
                    )
                    drawer = (
                        correct_drawer if posture_result.detected else incorrect_drawer
                    )
                    display = drawer.draw(frame, pose_result.landmarks)
                    status = (
                        "POSTURA CORRECTA"
                        if posture_result.detected
                        else "POSTURA INCORRECTA"
                    )
                    status_color = (
                        SUCCESS_COLOR if posture_result.detected else ERROR_COLOR
                    )
                    diagnostics = tuple(
                        (line, INFO_COLOR) for line in diagnostic_lines(posture_result)
                    )
                else:
                    display = frame.copy()
                    status = "SIN POSE: muestra el cuerpo completo"
                    status_color = ERROR_COLOR
                    diagnostics = ()

                stats = monitor.get_stats()
                lines = (
                    (f"Objetivo: {presentation.name}", INFO_COLOR),
                    (presentation.instruction, INFO_COLOR),
                    (status, status_color),
                ) + diagnostics + (
                    (f"FPS: {stats.fps:.1f}", INFO_COLOR),
                    ("1/2/3: cambiar postura | Q: salir", INFO_COLOR),
                )
                draw_text_lines(display, lines)
                cv2.imshow(WINDOW_NAME, display)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    break
                if key in KEY_TO_POSTURE:
                    selected_posture = KEY_TO_POSTURE[key]
                    print(f"Postura objetivo: {selected_posture.value}")
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break

    except (RuntimeError, ValueError, FileNotFoundError, cv2.error) as error:
        print(f"[ERROR] {error}")
    except KeyboardInterrupt:
        print("\nPrueba interrumpida por el usuario.")
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Prueba finalizada y recursos liberados.")


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    main(PostureId(arguments.posture))
