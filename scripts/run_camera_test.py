"""DIAGNÓSTICO LOCAL, FUERA DEL PRODUCTO.

Abre la webcam de este equipo con OpenCV para probar modelos a mano.
La API nunca abre una cámara: en EMOtv la captura ocurre en el navegador.
"""

import sys
from pathlib import Path

# Permite importar scripts.diagnostics al ejecutar el archivo directamente.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from emotv.config import TARGET_WIDTH, TARGET_HEIGHT, TARGET_FPS
from scripts.diagnostics.opencv_camera import (
    CameraConfig,
    OpenCVCamera,
)
from scripts.diagnostics.camera_preview import CameraPreview
from emotv.shared.performance.monitor import PerformanceMonitor


def main() -> None:
    # Usamos los valores centralizados
    config = CameraConfig(
        device_index=0,
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        fps=TARGET_FPS,
    )

    camera = OpenCVCamera(config)
    monitor = PerformanceMonitor()

    try:
        camera.open()

        properties = camera.get_actual_properties()

        print("=== EMOtv - Camera Test ===")
        print(f"Resolución solicitada: {config.width}x{config.height}")
        print(
            "Resolución real: "
            f"{int(properties['width'])}x{int(properties['height'])}"
        )
        print(f"FPS solicitados: {config.fps}")
        print(f"FPS reportados: {properties['fps']:.2f}")
        print("Presiona Q para cerrar.")
        print()

        preview = CameraPreview(
            camera=camera,
            monitor=monitor,
        )

        preview.run()

    except RuntimeError as error:
        print(f"[ERROR] {error}")

    except KeyboardInterrupt:
        print("\nPrueba interrumpida por el usuario.")

    finally:
        camera.release()
        print("Cámara liberada correctamente.")


if __name__ == "__main__":
    main()
