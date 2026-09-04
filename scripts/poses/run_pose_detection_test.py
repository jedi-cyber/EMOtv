from __future__ import annotations

import cv2

from emotv.config import (
    CAMERA_INDEX,
    POSE_MODEL_PATH,
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)
from emotv.infrastructure.vision.camera.opencv_camera import CameraConfig, OpenCVCamera
from emotv.infrastructure.vision.pose_detection import PoseDetector
from emotv.interfaces.ui.pose_drawer import PoseDrawer
from emotv.shared.performance.monitor import PerformanceMonitor


WINDOW_NAME = "EMOtv - Pose Detection"


def main() -> None:
    if not POSE_MODEL_PATH.is_file():
        print(f"[ERROR] No se encontro el modelo de pose: {POSE_MODEL_PATH}")
        print("Ejecuta: python scripts/poses/download_pose_model.py")
        return

    config = CameraConfig(
        device_index=CAMERA_INDEX,
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        fps=TARGET_FPS,
    )
    camera = OpenCVCamera(config)
    drawer = PoseDrawer()
    monitor = PerformanceMonitor()

    print("=== EMOtv - Pose Detection Test ===")
    print(f"Modelo: {POSE_MODEL_PATH}")
    print("Presiona Q para salir.")

    try:
        with camera, PoseDetector() as detector:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

            while True:
                frame = camera.read()
                result = detector.detect(frame)
                monitor.update_frame()

                if result.detected and result.landmarks is not None:
                    display = drawer.draw(frame, result.landmarks)
                    status = f"Pose detectada ({result.confidence * 100:.1f}%)"
                    status_color = (0, 255, 0)
                else:
                    display = frame.copy()
                    status = "Sin pose detectada"
                    status_color = (0, 0, 255)

                stats = monitor.get_stats()
                lines = (
                    status,
                    f"FPS: {stats.fps:.1f}",
                    f"CPU: {stats.cpu_percent:.1f}%",
                    f"RAM: {stats.ram_mb:.1f} MB",
                )
                for index, text in enumerate(lines):
                    color = status_color if index == 0 else (255, 255, 255)
                    cv2.putText(
                        display,
                        text,
                        (15, 30 + index * 28),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        color,
                        2,
                        cv2.LINE_AA,
                    )

                cv2.imshow(WINDOW_NAME, display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    break
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break

    except (RuntimeError, ValueError, FileNotFoundError) as error:
        print(f"[ERROR] {error}")
    except KeyboardInterrupt:
        print("\nPrueba interrumpida por el usuario.")
    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Prueba finalizada y recursos liberados.")


if __name__ == "__main__":
    main()
