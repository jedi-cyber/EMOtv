from __future__ import annotations

import unittest
from unittest.mock import patch

from emotv.config import POSE_MODEL_PATH
from scripts.poses.download_pose_model import download_pose_model


class PoseConfigurationTests(unittest.TestCase):
    def test_pose_model_uses_the_expected_directory(self) -> None:
        self.assertEqual(POSE_MODEL_PATH.parent.name, "pose")
        self.assertEqual(POSE_MODEL_PATH.suffix, ".task")

    def test_downloader_does_not_replace_an_existing_model(self) -> None:
        with (
            patch("pathlib.Path.is_file", return_value=True),
            patch("urllib.request.urlretrieve") as urlretrieve,
        ):
            result = download_pose_model()

        self.assertEqual(result, POSE_MODEL_PATH)
        urlretrieve.assert_not_called()
