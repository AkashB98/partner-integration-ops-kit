import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bundle import bundle_to_json, generate_bundle  # noqa: E402


class TestBundle(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(generate_bundle(), generate_bundle())
        self.assertEqual(bundle_to_json(generate_bundle()),
                         bundle_to_json(generate_bundle()))

    def test_headline_counts(self):
        bundle = generate_bundle()
        self.assertEqual(len(bundle["partners"]), 4)
        self.assertEqual(len(bundle["changelog"]), 24)
        self.assertEqual(len(bundle["credentials"]), 9)
        self.assertEqual(bundle["as_of"], "2026-11-14")

    def test_truth_split_is_balanced(self):
        truths = [c["truth"] for c in generate_bundle()["changelog"]]
        self.assertEqual(truths.count("breaking"), 12)
        self.assertEqual(truths.count("non-breaking"), 12)

    def test_every_partner_has_a_contract(self):
        bundle = generate_bundle()
        for partner in bundle["partners"]:
            self.assertIn(partner["partner_id"], bundle["contracts"])

    def test_deep_copy_isolation(self):
        a = generate_bundle()
        a["changelog"][0]["field"] = "mutated"
        self.assertNotEqual(generate_bundle()["changelog"][0]["field"],
                            "mutated")


if __name__ == "__main__":
    unittest.main()
