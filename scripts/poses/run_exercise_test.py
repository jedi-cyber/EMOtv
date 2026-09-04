from __future__ import annotations

import cv2
import numpy as np

from emotv.application.exercise_service import ExerciseService
from emotv.config import (
    ARMS_UP_HOLD_SECONDS,
    CAMERA_INDEX,
    POSE_MODEL_PATH,
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)
from emotv.domain.exercise_status import ExerciseState, ExerciseStatus
from emotv.infrastructure.vision.camera.opencv_camera import (
    CameraConfig,
    OpenCVCamera,
)
from emotv.infrastructure.vision.movement_analysis import PostureValidator
from emotv.infrastructure.vision.pose_detection import PoseDetector
from emotv.interfaces.ui.pose_drawer import PoseDrawer, PoseDrawingStyle
from emotv.shared.performance.monitor import PerformanceMonitor


WINDOW_NAME = "EMOtv - Exercise Test: Hold Both Arms Up"
SUCCESS_COLOR = (0, 255, 0)
HOLDING_COLOR = (0, 215, 255)
ERROR_COLOR = (0, 0, 255)
INFO_COLOR = (255, 255, 255)


def state_presentation(status: ExerciseStatus) -> tuple[str, tuple[int, int, int]]:
    if status.state is ExerciseState.COMPLETED:
        return "EJERCICIO COMPLETADO - pulsa R para reiniciar", SUCCESS_COLOR
    if status.state is ExerciseState.HOLDING:
        return "MANTEN LOS BRAZOS ARRIBA", HOLDING_COLOR
    return "SUBE Y EXTIENDE AMBOS BRAZOS", ERROR_COLOR


def draw_progress_bar(
    frame: np.ndarray,
    progress: float,
    color: tuple[int, int, int],
) -> None:
    """Dibuja una barra inferior con progreso limitado entre cero y uno."""

    progress = min(max(float(progress), 0.0), 1.0)
    height, width = frame.shape[:2]
    margin = max(10, width // 32)
    bar_height = max(18, height // 24)
    left = margin
    right = max(left + 1, width - margin)
    bottom = max(bar_height + 8, height - margin)
    top = bottom - bar_height

    cv2.rectangle(frame, (left, top), (right, bottom), (35, 35, 35), -1)
    fill_right = left + round((right - left) * progress)
    if fill_right > left:
        cv2.rectangle(frame, (left, top), (fill_right, bottom), color, -1)
    cv2.rectangle(frame, (left, top), (right, bottom), INFO_COLOR, 2)

    label = f"Progreso: {progress * 100:.0f}%"
    text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    text_x = max(left, (width - text_size[0]) // 2)
    text_y = max(text_size[1] + 2, top - 8)
    cv2.putText(
        frame,
        label,
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        INFO_COLOR,
        2,
        cv2.LINE_AA,
    )


def draw_status(
    frame: np.ndarray,
    status: ExerciseStatus,
    pose_detected: bool,
    fps: float,
) -> None:
    message, color = state_presentation(status)
    remaining = max(0.0, ARMS_UP_HOLD_SECONDS - status.elapsed_seconds)
    lines = (
        (message, color),
        (
            f"Tiempo: {status.elapsed_seconds:.1f}/{ARMS_UP_HOLD_SECONDS:.1f}s "
            f"| restante: {remaining:.1f}s",
            INFO_COLOR,
        ),
        (f"Pose detectada: {'si' if pose_detected else 'no'}", INFO_COLOR),
        (f"FPS: {fps:.1f}", INFO_COLOR),
        ("Q: salir | R: reiniciar", INFO_COLOR),
    )
    for index, (text, text_color) in enumerate(lines):
        cv2.putText(
            frame,
            text,
            (15, 30 + index * 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            text_color,
            2,
            cv2.LINE_AA,
        )
    draw_progress_bar(frame, status.progress, color)


def main() -> None:
    if not POSE_MODEL_PATH.is_file():
        print(f"[ERROR] No se encontro el modelo de pose: {POSE_MODEL_PATH}")
        print("Ejecuta: python scripts/poses/download_pose_model.py")
        return

    camera = OpenCVCamera(
        CameraConfig(
            device_index=CAMERA_INDEX,
            width=TARGET_WIDTH,
            height=TARGET_HEIGHT,
            fps=TARGET_FPS,
        )
    )
    validator = PostureValidator()
    exercise = ExerciseService(duration_seconds=ARMS_UP_HOLD_SECONDS)
    monitor = PerformanceMonitor()
    correct_drawer = PoseDrawer(
        PoseDrawingStyle(connection_color=SUCCESS_COLOR),
    )
    incorrect_drawer = PoseDrawer(
        PoseDrawingStyle(connection_color=ERROR_COLOR),
    )

    print("=== EMOtv - Exercise Test ===")
    print(
        "Levanta ambos brazos extendidos y mantenlos durante "
        f"{ARMS_UP_HOLD_SECONDS:.1f} segundos."
    )
    print("Presiona Q para salir o R para reiniciar.")

    try:
        with camera, PoseDetector() as detector:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

            while True:
                frame = camera.read()
                pose_result = detector.detect(frame)
                pose_detected = (
                    pose_result.detected and pose_result.landmarks is not None
                )
                posture_correct = False

                if pose_detected:
                    assert pose_result.landmarks is not None
                    posture_correct = validator.both_arms_up(pose_result.landmarks)
                    drawer = correct_drawer if posture_correct else incorrect_drawer
                    display = drawer.draw(frame, pose_result.landmarks)
                else:
                    display = frame.copy()

                status = exercise.update(posture_correct)
                monitor.update_frame()
                stats = monitor.get_stats()
                draw_status(display, status, pose_detected, stats.fps)
                cv2.imshow(WINDOW_NAME, display)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    break
                if key in (ord("r"), ord("R")):
                    exercise.reset()
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
    main()
