"""Golden evals for partner-integration-ops-kit.

SYNTHETIC DATA ONLY (fictional partners). Every eval is deterministic:
run_evals.py writes eval_report.json and the file must be
byte-identical across runs. No timestamps, ports, or temp paths enter
the report — only names, booleans, pinned counts and values.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import threading
import urllib.request
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bundle import bundle_to_json, generate_bundle  # noqa: E402
from classifier import classify_changelog  # noqa: E402
from cli import (EXIT_ERROR, EXIT_OK, load_bundle,  # noqa: E402
                 main as cli_main, make_server, reset_state)
from expiry import expiry_report  # noqa: E402
from report import build_markdown_report  # noqa: E402
from validation import validate_bundle  # noqa: E402
from verify import verify  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE = os.path.join(ROOT, "fixtures", "sample_bundle.json")
RESULTS = []


def check(name, passed, detail=""):
    RESULTS.append({"name": name, "passed": bool(passed), "detail": detail})
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return passed


def _run_cli(argv):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return cli_main(argv)


def main():
    print("== golden evals: partner-integration-ops-kit ==")
    bundle = generate_bundle()
    result = verify(bundle)
    exp = expiry_report(bundle)

    # E1: bundle determinism (bytes pinned).
    text1 = bundle_to_json(generate_bundle())
    text2 = bundle_to_json(generate_bundle())
    md5 = hashlib.md5(text1.encode()).hexdigest()
    check("E1 bundle determinism (seeded, pinned as_of 2026-11-14)",
          text1 == text2, f"bundle_md5={md5}")

    # E2: headline counts pinned.
    truths = [c["truth"] for c in bundle["changelog"]]
    check("E2 headline counts (4 partners, 24 entries 12/12, 9 credentials)",
          len(bundle["partners"]) == 4 and len(bundle["changelog"]) == 24
          and truths.count("breaking") == 12
          and truths.count("non-breaking") == 12
          and len(bundle["credentials"]) == 9
          and validate_bundle(bundle) == [],
          f"entries={len(bundle['changelog'])}")

    # E3: predicted split pinned (12 breaking / 12 non-breaking).
    preds = classify_changelog(bundle)
    predicted = [p["prediction"] for p in preds]
    check("E3 predicted split pinned (12 breaking / 12 non-breaking)",
          predicted.count("breaking") == 12
          and predicted.count("non-breaking") == 12,
          f"breaking={predicted.count('breaking')}")

    # E4: per-class precision / recall pinned — the headline numbers.
    b = result["per_class"]["breaking"]
    n = result["per_class"]["non-breaking"]
    check("E4 per-class precision/recall pinned (0.9167 everywhere)",
          (b["precision"], b["recall"]) == (0.9167, 0.9167)
          and (n["precision"], n["recall"]) == (0.9167, 0.9167)
          and result["accuracy"] == 0.9167
          and (b["tp"], b["fp"], b["fn"]) == (11, 1, 1),
          f"breaking={b['precision']}/{b['recall']} "
          f"accuracy={result['accuracy']}")

    # E5: the missed breaking change is exactly the planted units change.
    check("E5 missed breaking pinned (exactly C12, the cents->dollars "
          "description change)",
          result["missed_breaking"] == ["C12"]
          and result["missed_breaking_count"] == 1,
          f"missed={result['missed_breaking']}")

    # E6: the only false alarm is the planted safe widening.
    check("E6 false alarm pinned (exactly C24, integer->number widening)",
          result["false_alarms"] == ["C24"],
          f"false_alarms={result['false_alarms']}")

    # E7: every breaking rule class is caught at least once (coverage of
    # the rule table by the seeded bundle, not just aggregate metrics).
    caught_types = set()
    truth_by_id = {c["id"]: c for c in bundle["changelog"]}
    for pred in preds:
        row = truth_by_id[pred["id"]]
        if row["truth"] == "breaking" and pred["prediction"] == "breaking":
            caught_types.add(row["change_type"])
    check("E7 all breaking change types caught (6 rule classes)",
          caught_types == {"field_removed", "field_renamed",
                           "type_changed", "requirement_changed",
                           "enum_value_removed", "field_added"},
          f"caught_types={sorted(caught_types)}")

    # E8: expiry tiers pinned on the seeded registry.
    check("E8 expiry tiers pinned (1 expired, 2/2/2/2, actionable K01-K05)",
          exp["counts"] == {"expired": 1, "critical": 2, "warning": 2,
                            "watch": 2, "ok": 2}
          and exp["actionable"] == ["K01", "K02", "K03", "K04", "K05"],
          f"counts={exp['counts']}")

    # E9: classifier never peeks at truth — flipping every label changes
    # no prediction, only the scores.
    flipped = generate_bundle()
    for row in flipped["changelog"]:
        row["truth"] = ("non-breaking" if row["truth"] == "breaking"
                        else "breaking")
    flipped_preds = classify_changelog(flipped)
    check("E9 classifier is truth-blind (label flip changes no prediction)",
          [p["prediction"] for p in flipped_preds] == predicted
          and verify(flipped)["accuracy"] != result["accuracy"])

    # E10: CLI check exit codes 0 / 2.
    import tempfile
    tmp = tempfile.mkdtemp(prefix="partner-ops-evals-")
    good_path = os.path.join(tmp, "bundle.json")
    with open(good_path, "w", encoding="utf-8") as fh:
        fh.write(bundle_to_json(bundle))
    codes = (_run_cli(["check", "--input", good_path]),
             _run_cli(["check", "--input", "/tmp/no-such-bundle-xyz.json"]))
    check("E10 CLI check exit codes 0/2 (seeded passes)",
          codes == (EXIT_OK, EXIT_ERROR), f"codes={codes}")

    # E11: serve round-trip matches local verification + report.
    reset_state(bundle)
    server = make_server(0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                    timeout=10) as resp:
            health = json.loads(resp.read())
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/verify", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            served = json.loads(resp.read())
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/report",
                                    timeout=10) as resp:
            served_report = resp.read().decode()
        serve_ok = health == {"status": "ok"} \
            and served["per_class"] == result["per_class"] \
            and served["missed_breaking"] == ["C12"] \
            and served_report == build_markdown_report(bundle)
    finally:
        server.shutdown()
        server.server_close()
        reset_state()
    check("E11 serve round-trip matches local verify + report", serve_ok)

    # E12: bundled fixture pinned to the canonical bundle.
    fixture = load_bundle(FIXTURE)
    check("E12 fixture pinned (equals canonical bundle, validates clean)",
          fixture == generate_bundle() and validate_bundle(fixture) == [])

    # E13: report determinism + honesty line + missed-breaking callout.
    md1 = build_markdown_report(bundle)
    md2 = build_markdown_report(generate_bundle())
    check("E13 report determinism + honesty line + C12 callout",
          md1 == md2 and "no AI or ML" in md1
          and "MISSED BREAKING: C12" in md1,
          f"report_md5={hashlib.md5(md1.encode()).hexdigest()}")

    passed = sum(1 for r in RESULTS if r["passed"])
    total_count = len(RESULTS)
    summary_doc = {"passed": passed, "total": total_count,
                   "all_passed": passed == total_count, "evals": RESULTS}
    with open(os.path.join(HERE, "eval_report.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary_doc, sort_keys=True) + "\n")
    print(f"\n{passed}/{total_count} evals passed -> evals/eval_report.json")
    return 0 if passed == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
