import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bundle import generate_bundle  # noqa: E402
from validation import validate_bundle  # noqa: E402


class TestValidation(unittest.TestCase):
    def test_seeded_bundle_is_clean(self):
        self.assertEqual(validate_bundle(generate_bundle()), [])

    def test_non_object_bundle(self):
        self.assertTrue(validate_bundle([1, 2, 3]))

    def test_bad_as_of(self):
        bundle = generate_bundle()
        bundle["as_of"] = "next Tuesday"
        self.assertTrue(any("as_of" in i for i in validate_bundle(bundle)))

    def test_duplicate_changelog_id(self):
        bundle = generate_bundle()
        bundle["changelog"].append(copy.deepcopy(bundle["changelog"][0]))
        self.assertTrue(any("duplicate changelog" in i
                            for i in validate_bundle(bundle)))

    def test_unknown_partner_in_changelog(self):
        bundle = generate_bundle()
        bundle["changelog"][0]["partner_id"] = "ghost"
        self.assertTrue(any("unknown partner" in i
                            for i in validate_bundle(bundle)))

    def test_bad_truth_label(self):
        bundle = generate_bundle()
        bundle["changelog"][0]["truth"] = "maybe"
        self.assertTrue(any("truth" in i for i in validate_bundle(bundle)))

    def test_bad_credential_date(self):
        bundle = generate_bundle()
        bundle["credentials"][0]["expires_on"] = "soon"
        self.assertTrue(any("expires_on" in i
                            for i in validate_bundle(bundle)))

    def test_unknown_change_type(self):
        bundle = generate_bundle()
        bundle["changelog"][0]["change_type"] = "field_exploded"
        self.assertTrue(any("change_type" in i
                            for i in validate_bundle(bundle)))


if __name__ == "__main__":
    unittest.main()
