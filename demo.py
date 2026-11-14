"""End-to-end demo: bundle -> validate -> classify -> verify (with the
missed breaking change called out) -> expiry tiers -> report -> check
-> serve.

SYNTHETIC DATA ONLY (fictional partners). Runs fully offline; the serve
round-trip is loopback-only on an ephemeral port. Every stage asserts.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bundle import bundle_to_json, generate_bundle  # noqa: E402
from classifier import classify_changelog  # noqa: E402
from cli import EXIT_OK, main as cli_main, make_server, reset_state  # noqa: E402
from expiry import expiry_report  # noqa: E402
from report import build_markdown_report  # noqa: E402
from validation import validate_bundle  # noqa: E402
from verify import verify  # noqa: E402


def _request(port: int, path: str, payload=None, method: str = "GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read()


def main() -> None:
    print("== 1. synthetic bundle (4 fictional partners, pinned as_of) ==")
    bundle = generate_bundle()
    assert bundle == generate_bundle(), "bundle must be deterministic"
    assert validate_bundle(bundle) == [], validate_bundle(bundle)[:3]
    print(f"   {len(bundle['partners'])} partners, "
          f"{len(bundle['changelog'])} changelog entries, "
          f"{len(bundle['credentials'])} credentials, "
          f"as_of={bundle['as_of']}")

    print("\n== 2. rule-based classification (no AI — explicit rules) ==")
    preds = classify_changelog(bundle)
    breaking = [p for p in preds if p["prediction"] == "breaking"]
    print(f"   {len(breaking)} predicted breaking, "
          f"{len(preds) - len(breaking)} predicted non-breaking")

    print("\n== 3. verification pass against ground truth ==")
    result = verify(bundle, preds)
    for cls in ("breaking", "non-breaking"):
        s = result["per_class"][cls]
        print(f"   {cls}: precision {s['precision']}, recall {s['recall']}")
    print(f"   accuracy {result['accuracy']} "
          f"({result['correct']}/{result['total']})")
    assert result["missed_breaking"] == ["C12"]
    print(f"   MISSED BREAKING: {result['missed_breaking']} — the "
          "description change that redefined amount_cents from cents "
          "to dollars. This is the costly error: it ships silently.")
    print(f"   false alarms: {result['false_alarms']} — the integer -> "
          "number widening, over-flagged by the any-type-change rule.")

    print("\n== 4. credential / certificate expiry tiers ==")
    exp = expiry_report(bundle)
    print(f"   counts: {exp['counts']}")
    print(f"   actionable (expired/critical/warning): {exp['actionable']}")
    assert exp["counts"] == {"expired": 1, "critical": 2, "warning": 2,
                             "watch": 2, "ok": 2}

    print("\n== 5. markdown verification report ==")
    md = build_markdown_report(bundle)
    assert md == build_markdown_report(generate_bundle())
    assert "MISSED BREAKING: C12" in md
    print("   " + md.splitlines()[0])

    print("\n== 6. CLI check gate ==")
    import tempfile
    tmp = tempfile.mkdtemp(prefix="partner-ops-demo-")
    good_path = os.path.join(tmp, "bundle.json")
    with open(good_path, "w", encoding="utf-8") as fh:
        fh.write(bundle_to_json(bundle))
    code_ok = cli_main(["check", "--input", good_path])
    code_err = cli_main(["check", "--input", "/tmp/no-such-bundle-xyz.json"])
    print(f"   seeded={code_ok} missing-file={code_err}")
    assert code_ok == EXIT_OK and code_err == 2

    print("\n== 7. live localhost serve round-trip ==")
    reset_state(bundle)
    server = make_server(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(port, "/health")
        assert status == 200 and json.loads(body) == {"status": "ok"}
        status, body = _request(port, "/verify", payload={}, method="POST")
        served = json.loads(body)
        assert status == 200
        assert served["missed_breaking"] == ["C12"]
        assert served["per_class"] == result["per_class"]
        status, body = _request(port, "/report")
        assert status == 200 and body.decode() == md
        print("   POST /verify matches local verification; GET /report "
              "matches the local report")
    finally:
        server.shutdown()
        server.server_close()
        reset_state()

    print("\nDemo OK: bundle, classify, verify, expiry, report, check "
          "and serve verified.")


if __name__ == "__main__":
    main()
