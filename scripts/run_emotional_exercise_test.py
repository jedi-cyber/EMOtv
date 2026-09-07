from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from emotv.application import EmotionalActivityService
from emotv.application.pose_service import PoseService
from emotv.config import (
    CAMERA_INDEX,
    EMOTION_MODEL_PATH,
    EMOTIONAL_ACTIVITY_INSTRUCTION_SECONDS,
    FRAME_SKIP_INTERVAL,
    POSE_MODEL_PATH,
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
    YUNET_PATH,
)
from emotv.domain import EmotionalActivityState, EmotionalActivityStatus
from emotv.infrastructure.vision.camera.opencv_camera import (
    CameraConfig,
    OpenCVCamera,
)
from emotv.infrastructure.vision.face_detection.yunet_face_detector import (
    FaceDetection,
    YuNetFaceDetector,
)
from emotv.infrastructure.vision.face_processing.face_preprocessor import (
    FacePreprocessor,
)
from emotv.interfaces.ui.pose_drawer import PoseDrawer, PoseDrawingStyle
from emotv.shared.performance.monitor import PerformanceMonitor


WINDOW_NAME = "EMOtv - Emotional Activity Test"
SUCCESS_COLOR = (0, 255, 0)
HOLDING_COLOR = (0, 215, 255)
ERROR_COLOR = (0, 0, 255)
INFO_COLOR = (255, 255, 255)


def build_final_result(status: EmotionalActivityStatus) -> dict[str, Any]:
    if not status.completed:
        raise ValueError("El flujo todavía no está completado")
    assert status.emotion is not None
    assert status.activity is not None
    assert status.exercise is not None
    return {
        "initial_emotion": status.emotion.emotion,
        "emotion_confidence": status.emotion.confidence,
        "activity": status.activity.id,
        "exercise_result": status.exercise.state.value,
        "elapsed_seconds": status.exercise.elapsed_seconds,
    }


def draw_progress_bar(
    frame: np.ndarray,
    progress: float,
    color: tuple[int, int, int],
    label: str,
) -> None:
    progress = min(max(float(progress), 0.0), 1.0)
    height, width = frame.shape[:2]
    margin = 20
    top = height - 48
    bottom = height - 20
    right = width - margin
    cv2.rectangle(frame, (margin, top), (right, bottom), (35, 35, 35), -1)
    fill_right = margin + round((right - margin) * progress)
    if fill_right > margin:
        cv2.rectangle(frame, (margin, top), (fill_right, bottom), color, -1)
    cv2.rectangle(frame, (margin, top), (right, bottom), INFO_COLOR, 2)
    cv2.putText(
        frame,
        f"{label}: {progress * 100:.0f}%",
        (margin, top - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        INFO_COLOR,
        2,
        cv2.LINE_AA,
    )


def draw_face(frame: np.ndarray, detection: FaceDetection) -> None:
    x, y, width, height = detection.bbox
    cv2.rectangle(frame, (x, y), (x + width, y + height), SUCCESS_COLOR, 2)


def draw_lines(
    frame: np.ndarray,
    lines: tuple[tuple[str, tuple[int, int, int]], ...],
) -> None:
    overlay = frame.copy()
    panel_height = min(frame.shape[0] - 70, 20 + len(lines) * 27)
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], panel_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    for index, (text, color) in enumerate(lines):
        cv2.putText(
            frame,
            text,
            (15, 27 + index * 27),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.56,
            color,
            2,
            cv2.LINE_AA,
        )


def validate_models() -> bool:
    missing = tuple(
        path for path in (YUNET_PATH, EMOTION_MODEL_PATH, POSE_MODEL_PATH)
        if not path.is_file()
    )
    if not missing:
        return True
    print("[ERROR] Faltan modelos:")
    for path in missing:
        print(f"  - {path}")
    print("Revisa scripts/emotion/ y scripts/poses/download_pose_model.py")
    return False


def main() -> None:
    if not validate_models():
        return

    camera = OpenCVCamera(
        CameraConfig(
            device_index=CAMERA_INDEX,
            width=TARGET_WIDTH,
            height=TARGET_HEIGHT,
            fps=TARGET_FPS,
        )
    )
    face_detector = YuNetFaceDetector(input_size=(TARGET_WIDTH, TARGET_HEIGHT))
    face_preprocessor = FacePreprocessor()
    pose_service = PoseService()
    controller = EmotionalActivityService(pose_service=pose_service)
    pose_drawer = PoseDrawer(
        PoseDrawingStyle(connection_color=ERROR_COLOR),
    )
    correct_pose_drawer = PoseDrawer(
        PoseDrawingStyle(connection_color=SUCCESS_COLOR),
    )
    monitor = PerformanceMonitor()
    frame_counter = 0
    selected_at: float | None = None
    last_emotion: tuple[str, float] | None = None
    final_result: dict[str, Any] | None = None

    print("========================================")
    print(" EMOtv - Emotional Activity Test")
    print("========================================")
    print("Mira a la cámara durante el análisis emocional.")
    print("Q: salir | R: reiniciar | ESPACIO: iniciar actividad")

    try:
        with camera:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

            while True:
                frame = camera.read()
                display = frame.copy()
                frame_counter += 1
                status = controller.status

                if status.state is EmotionalActivityState.ANALYZING_EMOTION:
                    selected_at = None
                    if frame_counter % FRAME_SKIP_INTERVAL == 0:
                        detections = face_detector.detect(frame)
                        if detections:
                            detection = detections[0]
                            draw_face(display, detection)
                            cropped_face = face_preprocessor.process(frame, detection)
                            if cropped_face is not None and cropped_face.is_valid:
                                emotion, confidence = controller.emotion_classifier.predict(
                                    cropped_face
                                )
                                last_emotion = (emotion, confidence)
                                status = controller.observe_emotion(emotion, confidence)

                elif status.state is EmotionalActivityState.ACTIVITY_SELECTED:
                    if selected_at is None:
                        selected_at = time.monotonic()
                        assert status.activity is not None
                        print(f"Emoción: {status.emotion.emotion}")
                        print(f"Actividad: {status.activity.name}")
                        print(f"Instrucción: {status.activity.description}")
                    if (
                        time.monotonic() - selected_at
                        >= EMOTIONAL_ACTIVITY_INSTRUCTION_SECONDS
                    ):
                        status = controller.begin_activity()

                elif status.state in {
                    EmotionalActivityState.WAITING_FOR_POSTURE,
                    EmotionalActivityState.PERFORMING_EXERCISE,
                }:
                    status = controller.process_pose_frame(frame)
                    last_pose = pose_service.last_pose_result
                    if last_pose is not None and last_pose.landmarks is not None:
                        drawer = (
                            correct_pose_drawer
                            if status.posture is not None and status.posture.detected
                            else pose_drawer
                        )
                        display = drawer.draw(frame, last_pose.landmarks)

                if status.completed and final_result is None:
                    final_result = build_final_result(status)
                    print("========================================")
                    print(" ACTIVIDAD COMPLETADA")
                    print("========================================")
                    for key, value in final_result.items():
                        print(f"{key}: {value}")

                monitor.update_frame()
                stats = monitor.get_stats()
                lines: list[tuple[str, tuple[int, int, int]]] = [
                    (f"Estado: {status.state.value}", INFO_COLOR),
                    (status.message, INFO_COLOR),
                ]
                if last_emotion is not None:
                    lines.append(
                        (
                            f"Emoción actual: {last_emotion[0]} "
                            f"({last_emotion[1] * 100:.1f}%)",
                            INFO_COLOR,
                        )
                    )
                if status.emotion is not None:
                    lines.append(
                        (
                            f"Emoción estable: {status.emotion.emotion} "
                            f"({status.emotion.agreement * 100:.0f}% acuerdo)",
                            SUCCESS_COLOR,
                        )
                    )
                if status.activity is not None:
                    lines.append((f"Actividad: {status.activity.name}", INFO_COLOR))
                    lines.append((status.activity.description, INFO_COLOR))
                if status.posture is not None and status.posture.failed_rules:
                    lines.append(
                        ("Ajustar: " + ", ".join(status.posture.failed_rules[:2]), ERROR_COLOR)
                    )
                lines.append((f"FPS: {stats.fps:.1f}", INFO_COLOR))
                draw_lines(display, tuple(lines))

                if status.exercise is not None:
                    bar_color = SUCCESS_COLOR if status.completed else HOLDING_COLOR
                    draw_progress_bar(
                        display,
                        status.exercise.progress,
                        bar_color,
                        "Ejercicio",
                    )
                elif status.state is EmotionalActivityState.ANALYZING_EMOTION:
                    analysis_progress = min(
                        controller.emotion_stabilizer.sample_count
                        / controller.emotion_stabilizer.min_samples,
                        1.0,
                    )
                    draw_progress_bar(
                        display,
                        analysis_progress,
                        HOLDING_COLOR,
                        "Análisis emocional",
                    )

                cv2.imshow(WINDOW_NAME, display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    break
                if key in (ord("r"), ord("R")):
                    controller.reset()
                    selected_at = None
                    last_emotion = None
                    final_result = None
                if (
                    key == ord(" ")
                    and controller.status.state
                    is EmotionalActivityState.ACTIVITY_SELECTED
                ):
                    status = controller.begin_activity()
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break

    except (RuntimeError, ValueError, FileNotFoundError, cv2.error) as error:
        print(f"[ERROR] {error}")
    except KeyboardInterrupt:
        print("\nPrueba interrumpida por el usuario.")
    finally:
        controller.close()
        camera.release()
        cv2.destroyAllWindows()
        print("Prueba finalizada y recursos liberados.")


if __name__ == "__main__":
    main()
