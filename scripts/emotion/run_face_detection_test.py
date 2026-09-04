from pathlib import Path

from emotv.config import (
    TARGET_WIDTH, TARGET_HEIGHT, TARGET_FPS,
    YUNET_PATH, EMOTION_MODEL_PATH
)
from emotv.infrastructure.vision.camera.opencv_camera import (
    CameraConfig,
    OpenCVCamera,
)
from emotv.infrastructure.vision.face_detection.yunet_face_detector import (
    YuNetFaceDetector,
)
from emotv.infrastructure.vision.face_processing.face_preprocessor import (
    FacePreprocessor,
)
from emotv.infrastructure.vision.emotion_classifier.emotion_classifier import (
    EmotionClassifier,
)
from emotv.shared.performance.monitor import PerformanceMonitor
import cv2
import numpy as np


def main() -> None:
    print("========================================")
    print(" EMOtv - Face Detection + Emotion Test")
    print("========================================")
    print()

    # ---------------------------------------------------------
    # 1. Comprobar modelos
    # ---------------------------------------------------------

    print("[1] Comprobando modelos...")

    if not YUNET_PATH.exists():
        print("[ERROR] No se encontró YuNet.")
        return
    if not EMOTION_MODEL_PATH.exists():
        print("[ERROR] No se encontró el modelo de emociones.")
        print(f"Ruta: {EMOTION_MODEL_PATH}")
        print("Ejecuta 'python scripts/download_emotion_model.py'")
        return

    print("[OK] Modelos encontrados.")
    print()

    # ---------------------------------------------------------
    # 2. Configuración de cámara
    # ---------------------------------------------------------

    config = CameraConfig(
        device_index=0,
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
        fps=TARGET_FPS,
    )

    print(f"[2] Cámara: {config.width}x{config.height} @ {config.fps} FPS")
    print()

    # ---------------------------------------------------------
    # 3. Crear componentes
    # ---------------------------------------------------------

    print("[3] Inicializando componentes...")

    camera = OpenCVCamera(config)
    monitor = PerformanceMonitor()
    detector = YuNetFaceDetector(input_size=(TARGET_WIDTH, TARGET_HEIGHT))
    preprocessor = FacePreprocessor()
    classifier = EmotionClassifier()

    print("[OK] Todos los componentes listos.")
    print()

    # ---------------------------------------------------------
    # 4. Ejecutar prueba
    # ---------------------------------------------------------

    try:
        camera.open()
        print("[4] Cámara abierta. Presiona Q para salir.")
        print("    Se mostrará la emoción en la ventana principal.\n")

        cv2.namedWindow("EMOtv - Face Detection + Emotion", cv2.WINDOW_NORMAL)
        cv2.namedWindow("EMOtv - Cropped Face", cv2.WINDOW_NORMAL)

        running = True
        frame_counter = 0
        last_detections = []
        last_emotion = ("neutral", 0.0)  # (emoción, confianza)

        while running:
            frame = camera.read()
            if frame is None:
                break

            monitor.update_frame()

            # Frame skipping
            frame_counter += 1
            if frame_counter % 2 == 0:
                detections = detector.detect(frame)
                last_detections = detections
            else:
                detections = last_detections

            # Copiar frame para dibujar
            display_frame = frame.copy()

            # Dibujar detecciones y emociones
            for face in detections:
                x, y, w, h = face.bbox
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Preprocesar el rostro
                cropped = preprocessor.process(frame, face)

                if cropped and cropped.is_valid:
                    # Clasificar emoción (solo en el frame de detección)
                    if frame_counter % 2 == 0:
                        emotion, conf = classifier.predict(cropped)
                        last_emotion = (emotion, conf)
                    else:
                        emotion, conf = last_emotion

                    # Mostrar emoción encima del rectángulo
                    label = f"{emotion} ({conf*100:.1f}%)"
                    cv2.putText(
                        display_frame,
                        label,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                    )

                    # Mostrar el rostro recortado en la otra ventana
                    cropped_display = (cropped.image * 255).astype(np.uint8) if cropped.image.dtype == np.float32 else cropped.image
                    cv2.imshow("EMOtv - Cropped Face", cropped_display)

            # Mostrar métricas
            stats = monitor.get_stats()
            lines = [
                f"FPS: {stats.fps:.1f}",
                f"CPU: {stats.cpu_percent:.1f}%",
                f"RAM: {stats.ram_mb:.1f} MB",
                f"Faces: {len(detections)}",
                f"Emotion: {last_emotion[0]} ({last_emotion[1]*100:.1f}%)",
            ]
            for i, line in enumerate(lines):
                cv2.putText(
                    display_frame,
                    line,
                    (15, 30 + i * 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                )

            cv2.imshow("EMOtv - Face Detection + Emotion", display_frame)

            # Control de cierre
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                running = False

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("\nPrueba finalizada.")


if __name__ == "__main__":
    main()