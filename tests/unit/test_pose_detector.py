from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from emotv.infrastructure.vision.pose_detection import pose_detector as pose_detector_module
from emotv.infrastructure.vision.pose_detection.pose_detector import PoseDetector


def mediapipe_landmarks() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(x=index / 100, y=index / 100, z=0.1, visibility=0.8)
        for index in range(33)
    ]


class PoseDetectorTests(unittest.TestCase):
    def create_detector(self, pose_landmarks: list | None) -> tuple[PoseDetector, Mock]:
        landmarker = Mock()
        landmarker.detect_for_video.return_value = SimpleNamespace(
            pose_landmarks=pose_landmarks or [],
        )

        with (
            patch("pathlib.Path.is_file", return_value=True),
            patch.object(
                pose_detector_module.mp.tasks.vision.PoseLandmarker,
                "create_from_options",
                return_value=landmarker,
            ),
        ):
            detector = PoseDetector(model_path="fake.task")

        return detector, landmarker

    def test_returns_not_detected_when_mediapipe_finds_no_pose(self) -> None:
        detector, _ = self.create_detector(None)

        result = detector.detect(np.zeros((2, 2, 3), dtype=np.uint8))

        self.assertFalse(result.detected)
        self.assertIsNone(result.landmarks)

    def test_converts_bgr_frame_and_maps_landmarks(self) -> None:
        detector, landmarker = self.create_detector([mediapipe_landmarks()])
        frame = np.array([[[10, 20, 30]]], dtype=np.uint8)

        result = detector.detect(frame)

        self.assertTrue(result.detected)
        self.assertIsNotNone(result.landmarks)
        assert result.landmarks is not None
        self.assertAlmostEqual(result.landmarks.left_shoulder.x, 0.11)
        self.assertAlmostEqual(result.landmarks.right_ankle.x, 0.28)
        self.assertAlmostEqual(result.confidence, 0.8)

        image = landmarker.detect_for_video.call_args.args[0]
        self.assertEqual(image.numpy_view()[0, 0].tolist(), [30, 20, 10])

    def test_generates_strictly_increasing_timestamps(self) -> None:
        detector, landmarker = self.create_detector(None)
        frame = np.zeros((2, 2, 3), dtype=np.uint8)

        with patch("time.monotonic_ns", return_value=1_000_000):
            detector.detect(frame)
            detector.detect(frame)

        timestamps = [call.args[1] for call in landmarker.detect_for_video.call_args_list]
        self.assertEqual(timestamps, [1, 2])

    def test_rejects_invalid_frame(self) -> None:
        detector, _ = self.create_detector(None)

        with self.assertRaises(ValueError):
            detector.detect(np.zeros((2, 2), dtype=np.uint8))

    def test_close_is_idempotent(self) -> None:
        detector, landmarker = self.create_detector(None)

        detector.close()
        detector.close()

        landmarker.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
