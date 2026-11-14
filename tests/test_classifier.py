import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier import classify_change, classify_changelog  # noqa: E402
from bundle import generate_bundle  # noqa: E402
from tests.helpers import change  # noqa: E402


class TestClassifierRules(unittest.TestCase):
    def pred(self, **kw):
        return classify_change(change(**kw))["prediction"]

    def test_field_removed_is_breaking(self):
        self.assertEqual(self.pred(change_type="field_removed"), "breaking")

    def test_field_renamed_is_breaking(self):
        self.assertEqual(self.pred(change_type="field_renamed",
                                   new_field="f2"), "breaking")

    def test_type_changed_is_breaking(self):
        self.assertEqual(self.pred(change_type="type_changed",
                                   old_type="string", new_type="integer"),
                         "breaking")

    def test_enum_value_removed_is_breaking(self):
        self.assertEqual(self.pred(change_type="enum_value_removed",
                                   removed_value="x"), "breaking")

    def test_required_field_added_is_breaking(self):
        self.assertEqual(self.pred(change_type="field_added",
                                   new_required=True), "breaking")

    def test_optional_field_added_is_non_breaking(self):
        self.assertEqual(self.pred(change_type="field_added",
                                   new_required=False), "non-breaking")

    def test_becoming_required_is_breaking(self):
        self.assertEqual(self.pred(change_type="requirement_changed",
                                   old_required=False, new_required=True),
                         "breaking")

    def test_becoming_optional_is_non_breaking(self):
        self.assertEqual(self.pred(change_type="requirement_changed",
                                   old_required=True, new_required=False),
                         "non-breaking")

    def test_enum_value_added_is_non_breaking(self):
        self.assertEqual(self.pred(change_type="enum_value_added",
                                   added_value="x"), "non-breaking")

    def test_description_changed_is_non_breaking(self):
        self.assertEqual(self.pred(change_type="description_changed"),
                         "non-breaking")

    def test_unknown_type_defaults_non_breaking_with_reason(self):
        out = classify_change(change(change_type="something_new"))
        self.assertEqual(out["prediction"], "non-breaking")
        self.assertIn("unrecognised", out["reason"])

    def test_classifier_never_reads_truth(self):
        # Same diff, opposite planted labels -> identical predictions.
        a = classify_change(change(change_type="field_removed",
                                   truth="breaking"))
        b = classify_change(change(change_type="field_removed",
                                   truth="non-breaking"))
        self.assertEqual(a["prediction"], b["prediction"])

    def test_reason_is_always_present(self):
        for row in generate_bundle()["changelog"]:
            out = classify_change(row)
            self.assertTrue(out["reason"])
            self.assertEqual(out["id"], row["id"])

    def test_classify_changelog_order_and_count(self):
        bundle = generate_bundle()
        preds = classify_changelog(bundle)
        self.assertEqual(len(preds), 24)
        self.assertEqual([p["id"] for p in preds],
                         [c["id"] for c in bundle["changelog"]])


if __name__ == "__main__":
    unittest.main()
