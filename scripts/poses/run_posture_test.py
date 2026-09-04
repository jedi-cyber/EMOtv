from __future__ import annotations

import cv2
import numpy as np

from emotv.config import (
    CAMERA_INDEX,
    POSE_MODEL_PATH,
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)
from emotv.domain.pose_landmarks import PoseLandmarks
from emotv.infrastructure.vision.camera.opencv_camera import (
    CameraConfig,
    OpenCVCamera,
)
from emotv.infrastructure.vision.movement_analysis import (
    ArmsUpThresholds,
    PostureValidator,
    calculate_angle,
)
from emotv.infrastructure.vision.pose_detection import PoseDetector
from emotv.interfaces.ui.pose_drawer import PoseDrawer, PoseDrawingStyle
from emotv.shared.performance.monitor import PerformanceMonitor


WINDOW_NAME = "EMOtv - Posture Test: Both Arms Up"
SUCCESS_COLOR = (0, 255, 0)
ERROR_COLOR = (0, 0, 255)
INFO_COLOR = (255, 255, 255)


def arm_angles(pose: PoseLandmarks) -> tuple[float, float]:
    """Devuelve los angulos de los codos izquierdo y derecho."""

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
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )


def main() -> None:
    if not POSE_MODEL_PATH.is_file():
        print(f"[ERROR] No se encontro el modelo de pose: {POSE_MODEL_PATH}")
        print("Ejecuta: python scripts/poses/download_pose_model.py")
        return

    thresholds = ArmsUpThresholds()
    validator = PostureValidator(thresholds)
    correct_drawer = PoseDrawer(
        PoseDrawingStyle(
            landmark_color=(0, 255, 255),
            connection_color=SUCCESS_COLOR,
        ),
        min_visibility=thresholds.min_visibility,
    )
    incorrect_drawer = PoseDrawer(
        PoseDrawingStyle(
            landmark_color=(0, 165, 255),
            connection_color=ERROR_COLOR,
        ),
        min_visibility=thresholds.min_visibility,
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

    minimum_angle = 180.0 - thresholds.elbow_straight_tolerance_degrees
    print("=== EMOtv - Posture Test ===")
    print("Postura objetivo: levantar ambos brazos extendidos.")
    print(f"Visibilidad minima: {thresholds.min_visibility:.2f}")
    print(f"Margen de munecas: {thresholds.wrist_above_shoulder_margin:.2f}")
    print(f"Angulo minimo de codos: {minimum_angle:.1f} grados")
    print("Presiona Q para salir.")

    try:
        with camera, PoseDetector() as detector:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

            while True:
                frame = camera.read()
                pose_result = detector.detect(frame)
                monitor.update_frame()
                stats = monitor.get_stats()

                if pose_result.detected and pose_result.landmarks is not None:
                    pose = pose_result.landmarks
                    posture_correct = validator.both_arms_up(pose)
                    left_angle, right_angle = arm_angles(pose)
                    drawer = correct_drawer if posture_correct else incorrect_drawer
                    display = drawer.draw(frame, pose)
                    status = (
                        "POSTURA CORRECTA: ambos brazos arriba"
                        if posture_correct
                        else "AJUSTA: sube y extiende ambos brazos"
                    )
                    status_color = SUCCESS_COLOR if posture_correct else ERROR_COLOR
                    posture_lines = (
                        (status, status_color),
                        (
                            f"Codos: izq {left_angle:.1f} | der {right_angle:.1f} "
                            f"(min {minimum_angle:.1f})",
                            INFO_COLOR,
                        ),
                        (
                            f"Confianza de pose: {pose_result.confidence * 100:.1f}%",
                            INFO_COLOR,
                        ),
                    )
                else:
                    display = frame.copy()
                    posture_lines = (
                        ("SIN POSE: coloca el cuerpo completo en camara", ERROR_COLOR),
                        ("Levanta ambos brazos y mantenlos extendidos", INFO_COLOR),
                    )

                performance_lines = (
                    (f"FPS: {stats.fps:.1f}", INFO_COLOR),
                    (f"CPU: {stats.cpu_percent:.1f}%", INFO_COLOR),
                    (f"RAM: {stats.ram_mb:.1f} MB", INFO_COLOR),
                )
                draw_text_lines(display, posture_lines + performance_lines)
                cv2.imshow(WINDOW_NAME, display)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    break
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
