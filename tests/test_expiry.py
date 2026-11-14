import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bundle import generate_bundle  # noqa: E402
from expiry import (days_remaining, expiry_report, tier_for_days)  # noqa: E402


class TestTierBoundaries(unittest.TestCase):
    def test_expired(self):
        self.assertEqual(tier_for_days(-1), "expired")
        self.assertEqual(tier_for_days(-400), "expired")

    def test_critical_bounds(self):
        self.assertEqual(tier_for_days(0), "critical")
        self.assertEqual(tier_for_days(7), "critical")

    def test_warning_bounds(self):
        self.assertEqual(tier_for_days(8), "warning")
        self.assertEqual(tier_for_days(30), "warning")

    def test_watch_bounds(self):
        self.assertEqual(tier_for_days(31), "watch")
        self.assertEqual(tier_for_days(90), "watch")

    def test_ok(self):
        self.assertEqual(tier_for_days(91), "ok")
        self.assertEqual(tier_for_days(365), "ok")


class TestExpiryMath(unittest.TestCase):
    def test_days_remaining_sign(self):
        self.assertEqual(days_remaining("2026-11-10", "2026-11-14"), -4)
        self.assertEqual(days_remaining("2026-11-14", "2026-11-14"), 0)
        self.assertEqual(days_remaining("2026-11-18", "2026-11-14"), 4)

    def test_seeded_counts(self):
        report = expiry_report(generate_bundle())
        self.assertEqual(report["counts"], {"expired": 1, "critical": 2,
                                            "warning": 2, "watch": 2,
                                            "ok": 2})

    def test_seeded_actionable(self):
        report = expiry_report(generate_bundle())
        self.assertEqual(report["actionable"],
                         ["K01", "K02", "K03", "K04", "K05"])

    def test_sorted_by_severity_then_date(self):
        report = expiry_report(generate_bundle())
        ids = [r["id"] for r in report["credentials"]]
        self.assertEqual(ids[0], "K01")  # the only expired credential
        tiers = [r["tier"] for r in report["credentials"]]
        self.assertEqual(tiers, ["expired", "critical", "critical",
                                 "warning", "warning", "watch", "watch",
                                 "ok", "ok"])

    def test_deterministic(self):
        self.assertEqual(expiry_report(generate_bundle()),
                         expiry_report(generate_bundle()))


if __name__ == "__main__":
    unittest.main()
