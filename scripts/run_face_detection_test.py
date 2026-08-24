from pathlib import Path

from emotv.config import TARGET_WIDTH, TARGET_HEIGHT, TARGET_FPS, YUNET_PATH
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


def main() -> None:
    print("========================================")
    print(" EMOtv - Face Detection Test")
    print("========================================")
    print()

    # ---------------------------------------------------------
    # 1. Comprobar modelo
    # ---------------------------------------------------------

    print("[1] Comprobando modelo YuNet...")

    if not YUNET_PATH.exists():
        print("[ERROR] No se encontró el modelo YuNet.")
        print(f"Ruta esperada: {YUNET_PATH}")
        print("Ejecuta 'python scripts/download_weights.py' para descargarlo.")
        return

    print(f"[OK] Modelo encontrado:")
    print(f"     {YUNET_PATH}")
    print()

    # ---------------------------------------------------------
    # 2. Configuración de cámara (usando valores centralizados)
    # ---------------------------------------------------------

    config = CameraConfig(
        device_index=0,
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        fps=TARGET_FPS,
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

    # El detector usará YUNET_PATH por defecto (definido en config)
    detector = YuNetFaceDetector(
        input_size=(TARGET_WIDTH, TARGET_HEIGHT),
        # Los umbrales también se toman de config por defecto
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