import unittest
from datetime import datetime, timedelta

from app.progress import progress_due, progress_text

NOW = datetime(2026, 10, 4, 12, 0)
EVERY = timedelta(minutes=15)


class Due(unittest.TestCase):
    def test_not_before_the_interval(self):
        self.assertFalse(progress_due(NOW - timedelta(minutes=14, seconds=59), NOW, EVERY))

    def test_exactly_at_the_interval(self):
        self.assertTrue(progress_due(NOW - EVERY, NOW, EVERY))

    def test_zero_interval_turns_updates_off(self):
        self.assertFalse(progress_due(NOW - timedelta(days=1), NOW, timedelta(0)))


class Text(unittest.TestCase):
    def test_on_the_way(self):
        self.assertIn("About 25 min to go", progress_text("Neha", "clg", 25))

    def test_about_now(self):
        self.assertIn("about now", progress_text("Neha", "clg", 0))

    def test_overdue_says_so_plainly(self):
        t = progress_text("Neha", "clg", -7)
        self.assertIn("7 min past", t)
        self.assertIn("clg", t)


if __name__ == "__main__":
    unittest.main()
