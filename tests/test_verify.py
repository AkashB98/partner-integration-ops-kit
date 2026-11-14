import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bundle import generate_bundle  # noqa: E402
from tests.helpers import change, mini_bundle  # noqa: E402
from verify import verify  # noqa: E402


class TestVerifySeeded(unittest.TestCase):
    def setUp(self):
        self.result = verify(generate_bundle())

    def test_totals(self):
        self.assertEqual(self.result["total"], 24)
        self.assertEqual(self.result["correct"], 22)
        self.assertEqual(self.result["accuracy"], 0.9167)

    def test_breaking_precision_recall(self):
        b = self.result["per_class"]["breaking"]
        self.assertEqual((b["tp"], b["fp"], b["fn"]), (11, 1, 1))
        self.assertEqual(b["precision"], 0.9167)
        self.assertEqual(b["recall"], 0.9167)

    def test_non_breaking_precision_recall(self):
        n = self.result["per_class"]["non-breaking"]
        self.assertEqual((n["tp"], n["fp"], n["fn"]), (11, 1, 1))
        self.assertEqual(n["precision"], 0.9167)
        self.assertEqual(n["recall"], 0.9167)

    def test_missed_breaking_called_out_separately(self):
        self.assertEqual(self.result["missed_breaking"], ["C12"])
        self.assertEqual(self.result["missed_breaking_count"], 1)

    def test_false_alarm_is_the_widening(self):
        self.assertEqual(self.result["false_alarms"], ["C24"])


class TestVerifyHandScored(unittest.TestCase):
    def test_perfect_classifier(self):
        bundle = mini_bundle(changelog=[
            change(cid="A", change_type="field_removed", truth="breaking"),
            change(cid="B", change_type="field_added", truth="non-breaking",
                   new_required=False),
        ])
        result = verify(bundle)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["missed_breaking"], [])
        self.assertEqual(result["per_class"]["breaking"]["recall"], 1.0)

    def test_missed_breaking_is_fn_for_breaking(self):
        bundle = mini_bundle(changelog=[
            change(cid="A", change_type="description_changed",
                   truth="breaking"),
        ])
        result = verify(bundle)
        self.assertEqual(result["missed_breaking"], ["A"])
        self.assertEqual(result["per_class"]["breaking"]["fn"], 1)
        self.assertEqual(result["per_class"]["breaking"]["recall"], 0.0)

    def test_empty_bundle_scores_zero_without_crashing(self):
        result = verify(mini_bundle())
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
