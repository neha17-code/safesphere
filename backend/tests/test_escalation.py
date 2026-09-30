import unittest
from datetime import datetime, timedelta

from app.escalation import Policy, Stage, pending_transitions, target_stage

ETA = datetime(2026, 9, 30, 20, 0)
P = Policy(grace=timedelta(minutes=10), second_level=timedelta(minutes=15))


class TargetStage(unittest.TestCase):
    def test_before_eta_nothing_happens(self):
        self.assertEqual(target_stage(ETA, ETA - timedelta(seconds=1), P), Stage.NONE)

    def test_at_eta_user_is_nudged(self):
        self.assertEqual(target_stage(ETA, ETA, P), Stage.NUDGED)

    def test_inside_grace_still_nudged(self):
        self.assertEqual(target_stage(ETA, ETA + timedelta(minutes=9, seconds=59), P), Stage.NUDGED)

    def test_after_grace_contacts_alerted(self):
        self.assertEqual(target_stage(ETA, ETA + timedelta(minutes=10), P), Stage.CONTACTS_ALERTED)

    def test_after_second_level_escalated(self):
        self.assertEqual(target_stage(ETA, ETA + timedelta(minutes=25), P), Stage.ESCALATED)


class Transitions(unittest.TestCase):
    def test_no_change(self):
        self.assertEqual(pending_transitions(Stage.NUDGED, Stage.NUDGED), [])

    def test_never_goes_backwards(self):
        self.assertEqual(pending_transitions(Stage.ESCALATED, Stage.NONE), [])

    def test_single_step(self):
        self.assertEqual(pending_transitions(Stage.NONE, Stage.NUDGED), [Stage.NUDGED])

    def test_downtime_does_not_skip_levels(self):
        self.assertEqual(
            pending_transitions(Stage.NONE, Stage.ESCALATED),
            [Stage.NUDGED, Stage.CONTACTS_ALERTED, Stage.ESCALATED],
        )


if __name__ == "__main__":
    unittest.main()
