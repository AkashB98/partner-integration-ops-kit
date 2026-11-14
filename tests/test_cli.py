import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bundle import bundle_to_json, generate_bundle  # noqa: E402
from cli import EXIT_ERROR, EXIT_OK, main as cli_main  # noqa: E402


def run_cli(argv):
    with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
        code = cli_main(argv)
    return code, out.getvalue()


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="partner-ops-test-")
        self.path = os.path.join(self.tmp, "bundle.json")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(bundle_to_json(generate_bundle()))

    def test_check_passes_on_seeded(self):
        code, out = run_cli(["check", "--input", self.path])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("check PASS", out)

    def test_check_missing_file_is_error(self):
        code, _ = run_cli(["check", "--input", "/tmp/no-such-bundle-xyz.json"])
        self.assertEqual(code, EXIT_ERROR)

    def test_verify_output_metrics(self):
        code, out = run_cli(["verify", "--input", self.path])
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["missed_breaking"], ["C12"])
        self.assertEqual(payload["accuracy"], 0.9167)

    def test_classify_output_count(self):
        code, out = run_cli(["classify", "--input", self.path])
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(len(payload["predictions"]), 24)

    def test_expiry_output_counts(self):
        code, out = run_cli(["expiry", "--input", self.path])
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["counts"]["expired"], 1)

    def test_report_output(self):
        code, out = run_cli(["report", "--input", self.path])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("MISSED BREAKING: C12", out)

    def test_generate_round_trip(self):
        out_path = os.path.join(self.tmp, "gen.json")
        code, _ = run_cli(["generate", "--out", out_path])
        self.assertEqual(code, EXIT_OK)
        code, _ = run_cli(["check", "--input", out_path])
        self.assertEqual(code, EXIT_OK)

    def test_invalid_bundle_is_error(self):
        bad_path = os.path.join(self.tmp, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as fh:
            fh.write('{"as_of": "nope"}')
        code, _ = run_cli(["verify", "--input", bad_path])
        self.assertEqual(code, EXIT_ERROR)


class TestServe(unittest.TestCase):
    def test_serve_round_trip(self):
        import threading
        import urllib.request
        from cli import make_server, reset_state
        reset_state(generate_bundle())
        server = make_server(0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=10) as resp:
                self.assertEqual(json.loads(resp.read()), {"status": "ok"})
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/verify", data=b"{}",
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                served = json.loads(resp.read())
            self.assertEqual(served["missed_breaking"], ["C12"])
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/report", timeout=10) as resp:
                self.assertIn("MISSED BREAKING: C12",
                              resp.read().decode())
        finally:
            server.shutdown()
            server.server_close()
            reset_state()


if __name__ == "__main__":
    unittest.main()
