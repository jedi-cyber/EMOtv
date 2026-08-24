from pathlib import Path

from emotv.infrastructure.vision.camera.opencv_camera import (
    CameraConfig,
    OpenCVCamera,
)
from emotv.infrastructure.vision.face_detection.yunet_face_detector import (
    YuNetFaceDetector,
)
from emotv.interfaces.ui.face_detection_preview import (
    FaceDetectionPreview,
)
from emotv.shared.performance.monitor import PerformanceMonitor


# Ruta del modelo YuNet
MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "weights"
    / "yunet"
    / "face_detection_yunet_2026may.onnx"
)


def main() -> None:
    print("========================================")
    print(" EMOtv - Face Detection Test")
    print("========================================")
    print()

    # ---------------------------------------------------------
    # 1. Comprobar modelo
    # ---------------------------------------------------------

    print("[1] Comprobando modelo YuNet...")

    if not MODEL_PATH.exists():
        print("[ERROR] No se encontró el modelo YuNet.")
        print(f"Ruta esperada: {MODEL_PATH}")
        return

    print(f"[OK] Modelo encontrado:")
    print(f"     {MODEL_PATH}")
    print()

    # ---------------------------------------------------------
    # 2. Configuración de cámara
    # ---------------------------------------------------------

    config = CameraConfig(
        device_index=0,
        width=640,
        height=480,
        fps=15,
    )

    print("[2] Configuración de cámara:")
    print(f"     Dispositivo: {config.device_index}")
    print(f"     Resolución: {config.width}x{config.height}")
    print(f"     FPS objetivo: {config.fps}")
    print()

    # ---------------------------------------------------------
    # 3. Crear componentes
    # ---------------------------------------------------------

    print("[3] Inicializando componentes...")

    camera = OpenCVCamera(config)

    monitor = PerformanceMonitor()

    detector = YuNetFaceDetector(
        model_path=MODEL_PATH,
        input_size=(config.width, config.height),
        confidence_threshold=0.6,
        nms_threshold=0.3,
    )

    print("[OK] Cámara preparada.")
    print("[OK] Monitor preparado.")
    print("[OK] YuNet preparado.")
    print()

    # ---------------------------------------------------------
    # 4. Ejecutar prueba
    # ---------------------------------------------------------

    try:
        print("[4] Abriendo cámara...")

        camera.open()

        print("[OK] Cámara abierta.")
        print()

        properties = camera.get_actual_properties()

        print("========================================")
        print(" CONFIGURACIÓN REAL")
        print("========================================")

        print(
            f"Resolución real: "
            f"{int(properties['width'])}x"
            f"{int(properties['height'])}"
        )

        print(
            f"FPS reportados: "
            f"{properties['fps']:.2f}"
        )

        print()

        # -----------------------------------------------------
        # 5. Crear preview
        # -----------------------------------------------------

        preview = FaceDetectionPreview(
            camera=camera,
            detector=detector,
            monitor=monitor,
            window_name="EMOtv - Face Detection",
            exit_key="q",
        )

        print("[5] Iniciando detección facial...")
        print("    Presiona Q para salir.")
        print()

        preview.run()

    except RuntimeError as error:
        print(f"[ERROR] {error}")

    except KeyboardInterrupt:
        print()
        print("[INFO] Prueba interrumpida por el usuario.")

    except Exception as error:
        print()
        print(
            f"[ERROR INESPERADO] "
            f"{type(error).__name__}: {error}"
        )

    finally:
        camera.release()

        print()
        print("========================================")
        print(" Cámara liberada.")
        print(" Prueba finalizada.")
        print("========================================")


if __name__ == "__main__":
    main()