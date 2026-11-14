"""No-network enforcement: with sockets blocked, bundling, validating,
classifying, verifying, expiry and reporting must all still work.
(``serve`` is the only intentional exception — it binds loopback on
demand, and is not used here.)"""

import os
import socket
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Blocker:
    def __init__(self, *a, **k):
        raise RuntimeError("network access blocked in hermetic test")


class TestNoNetwork(unittest.TestCase):
    def setUp(self):
        self._real_socket = socket.socket
        socket.socket = _Blocker
        import urllib.request as urlreq
        self._real_urlopen = urlreq.urlopen
        urlreq.urlopen = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("network access blocked in hermetic test"))

    def tearDown(self):
        socket.socket = self._real_socket
        import urllib.request as urlreq
        urlreq.urlopen = self._real_urlopen

    def test_full_pipeline_offline(self):
        from bundle import generate_bundle
        from expiry import expiry_report
        from report import build_markdown_report
        from validation import validate_bundle
        from verify import verify
        bundle = generate_bundle()
        self.assertEqual(validate_bundle(bundle), [])
        self.assertEqual(verify(bundle)["missed_breaking"], ["C12"])
        self.assertEqual(expiry_report(bundle)["counts"]["expired"], 1)
        self.assertIn("MISSED BREAKING: C12", build_markdown_report(bundle))

    def test_no_module_opens_sockets_at_import(self):
        for mod in ("bundle", "validation", "classifier", "verify",
                    "expiry", "report", "cli", "demo"):
            sys.modules.pop(mod, None)
        import bundle, classifier, cli, demo, expiry, report, validation, verify  # noqa: F401
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
