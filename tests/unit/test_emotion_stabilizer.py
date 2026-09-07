from __future__ import annotations

import unittest

from emotv.application import EmotionStabilizer
from emotv.domain import StabilizedEmotion


class EmotionStabilizerTests(unittest.TestCase):
    def test_requires_minimum_number_of_eligible_samples(self) -> None:
        stabilizer = EmotionStabilizer(window_size=5, min_samples=3)

        self.assertIsNone(stabilizer.update("sadness", 0.8))
        self.assertIsNone(stabilizer.update("sadness", 0.8))
        self.assertIsNotNone(stabilizer.update("sadness", 0.8))

    def test_selects_dominant_emotion_and_averages_its_confidence(self) -> None:
        stabilizer = EmotionStabilizer(
            window_size=5,
            min_samples=5,
            min_agreement=0.6,
        )
        predictions = (
            ("sadness", 0.8),
            ("sadness", 0.7),
            ("neutral", 0.9),
            ("sadness", 0.9),
            ("sadness", 0.6),
        )

        result = None
        for prediction in predictions:
            result = stabilizer.update(*prediction)

        assert result is not None
        self.assertEqual(result.emotion, "sadness")
        self.assertEqual(result.votes, 4)
        self.assertEqual(result.samples, 5)
        self.assertAlmostEqual(result.agreement, 0.8)
        self.assertAlmostEqual(result.confidence, 0.75)

    def test_low_confidence_observations_do_not_vote(self) -> None:
        stabilizer = EmotionStabilizer(
            window_size=4,
            min_samples=3,
            min_confidence=0.6,
        )

        stabilizer.update("anger", 0.9)
        stabilizer.update("anger", 0.5)
        stabilizer.update("anger", 0.9)
        result = stabilizer.update("anger", 0.9)

        assert result is not None
        self.assertEqual(result.samples, 3)
        self.assertEqual(result.votes, 3)

    def test_rejects_tied_emotions(self) -> None:
        stabilizer = EmotionStabilizer(
            window_size=4,
            min_samples=4,
            min_agreement=0.5,
        )
        for emotion in ("sadness", "neutral", "sadness"):
            stabilizer.update(emotion, 0.8)

        self.assertIsNone(stabilizer.update("neutral", 0.8))

    def test_rejects_winner_below_agreement_threshold(self) -> None:
        stabilizer = EmotionStabilizer(
            window_size=5,
            min_samples=5,
            min_agreement=0.8,
        )
        for emotion in ("sadness", "sadness", "sadness", "neutral"):
            stabilizer.update(emotion, 0.8)

        self.assertIsNone(stabilizer.update("anger", 0.8))

    def test_window_discards_old_observations(self) -> None:
        stabilizer = EmotionStabilizer(
            window_size=3,
            min_samples=3,
            min_agreement=2 / 3,
        )
        for _ in range(3):
            stabilizer.update("sadness", 0.8)

        stabilizer.update("happiness", 0.9)
        stabilizer.update("happiness", 0.9)
        result = stabilizer.update("happiness", 0.9)

        assert result is not None
        self.assertEqual(result.emotion, "happiness")
        self.assertEqual(stabilizer.sample_count, 3)

    def test_normalizes_emotion_name(self) -> None:
        stabilizer = EmotionStabilizer(window_size=1, min_samples=1)

        result = stabilizer.update("  Sadness  ", 0.8)

        assert result is not None
        self.assertEqual(result.emotion, "sadness")

    def test_reset_clears_observations_and_result(self) -> None:
        stabilizer = EmotionStabilizer(window_size=1, min_samples=1)
        stabilizer.update("neutral", 0.9)

        stabilizer.reset()

        self.assertEqual(stabilizer.sample_count, 0)
        self.assertIsNone(stabilizer.current())

    def test_rejects_invalid_prediction(self) -> None:
        stabilizer = EmotionStabilizer(window_size=3, min_samples=1)

        for emotion, confidence in (("", 0.5), ("sadness", -0.1), ("sadness", 1.1)):
            with self.subTest(emotion=emotion, confidence=confidence):
                with self.assertRaises(ValueError):
                    stabilizer.update(emotion, confidence)

    def test_rejects_invalid_configuration(self) -> None:
        invalid_configurations = (
            {"window_size": 0},
            {"window_size": 3, "min_samples": 4},
            {"min_confidence": 1.1},
            {"min_agreement": 0.0},
        )

        for configuration in invalid_configurations:
            with self.subTest(configuration=configuration):
                with self.assertRaises(ValueError):
                    EmotionStabilizer(**configuration)


class StabilizedEmotionTests(unittest.TestCase):
    def test_rejects_incoherent_vote_counts(self) -> None:
        with self.assertRaises(ValueError):
            StabilizedEmotion("sadness", 0.8, 0.8, votes=4, samples=3)


if __name__ == "__main__":
    unittest.main()
