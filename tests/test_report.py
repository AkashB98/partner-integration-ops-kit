import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bundle import generate_bundle  # noqa: E402
from report import build_markdown_report  # noqa: E402


class TestReport(unittest.TestCase):
    def setUp(self):
        self.md = build_markdown_report(generate_bundle())

    def test_deterministic(self):
        self.assertEqual(self.md, build_markdown_report(generate_bundle()))

    def test_honesty_line_present(self):
        self.assertIn("rule-based", self.md)
        self.assertIn("no AI or ML", self.md)

    def test_missed_breaking_named(self):
        self.assertIn("MISSED BREAKING: C12", self.md)

    def test_false_alarm_named(self):
        self.assertIn("FALSE ALARM: C24", self.md)

    def test_per_class_numbers_present(self):
        self.assertIn("| breaking | 0.9167 | 0.9167 |", self.md)


if __name__ == "__main__":
    unittest.main()
