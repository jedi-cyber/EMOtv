from __future__ import annotations

import unittest

from emotv.domain import SessionState


class SessionStateTests(unittest.TestCase):
    def test_states_have_stable_serializable_values(self) -> None:
        self.assertEqual(SessionState.CREATED.value, "created")
        self.assertEqual(SessionState.IN_PROGRESS.value, "in_progress")
        self.assertEqual(SessionState.COMPLETED.value, "completed")
        self.assertEqual(SessionState.CANCELLED.value, "cancelled")

    def test_state_can_be_created_from_serialized_value(self) -> None:
        self.assertIs(SessionState("in_progress"), SessionState.IN_PROGRESS)

    def test_unknown_state_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SessionState("unknown")


if __name__ == "__main__":
    unittest.main()
