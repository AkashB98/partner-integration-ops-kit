"""CLI: generate | classify | verify | expiry | report | check | demo | serve.

SYNTHETIC DATA ONLY — every partner is fictional. NOT production
integration tooling.

Exit codes:
  check : 0 = pass, 1 = quality breach (breaking precision or recall
          below 0.9, or more than 1 missed breaking change),
          2 = usage / IO / data-quality error
  others: 0 = success, 2 = usage / IO error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bundle import bundle_to_json, generate_bundle  # noqa: E402
from classifier import classify_changelog  # noqa: E402
from expiry import expiry_report  # noqa: E402
from report import build_markdown_report  # noqa: E402
from validation import validate_bundle  # noqa: E402
from verify import verify  # noqa: E402

EXIT_OK, EXIT_FAIL, EXIT_ERROR = 0, 1, 2
MIN_BREAKING_PRECISION = 0.9
MIN_BREAKING_RECALL = 0.9
MAX_MISSED_BREAKING = 1


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True)


def load_bundle(path: str) -> Dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("bundle file must contain a JSON object")
    return data


def _load_or_error(path: str) -> Optional[Dict]:
    try:
        return load_bundle(path)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
    except (ValueError, OSError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
    return None


def _validated(args):
    data = _load_or_error(args.input)
    if data is None:
        return None, EXIT_ERROR
    issues = validate_bundle(data)
    if issues:
        for issue in issues[:20]:
            print(f"data-quality: {issue}", file=sys.stderr)
        return None, EXIT_ERROR
    return data, EXIT_OK


def _write_out(args, text: str, summary: str) -> int:
    if getattr(args, "out", None):
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(summary)
    else:
        print(text, end="")
    return EXIT_OK


def cmd_generate(args) -> int:
    return _write_out(args, bundle_to_json(generate_bundle()),
                      f"generated synthetic bundle -> {args.out}")


def cmd_classify(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    payload = {"as_of": data["as_of"],
               "predictions": classify_changelog(data)}
    return _write_out(args, canonical(payload) + "\n",
                      f"classify -> {args.out}")


def cmd_verify(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    return _write_out(args, canonical(verify(data)) + "\n",
                      f"verify -> {args.out}")


def cmd_expiry(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    return _write_out(args, canonical(expiry_report(data)) + "\n",
                      f"expiry -> {args.out}")


def cmd_report(args) -> int:
    data, code = _validated(args)
    if data is None:
        return code
    return _write_out(args, build_markdown_report(data),
                      f"report -> {args.out}")


def cmd_check(args) -> int:
    data = _load_or_error(args.input)
    if data is None:
        return EXIT_ERROR
    issues = validate_bundle(data)
    if issues:
        for issue in issues[:20]:
            print(f"data-quality: {issue}")
        print(f"check FAIL (data quality): {len(issues)} issue(s)")
        return EXIT_ERROR
    result = verify(data)
    b = result["per_class"]["breaking"]
    print(f"entries={result['total']} accuracy={result['accuracy']} "
          f"breaking_precision={b['precision']} "
          f"breaking_recall={b['recall']} "
          f"missed_breaking={result['missed_breaking']}")
    breaches = []
    if b["precision"] < MIN_BREAKING_PRECISION:
        breaches.append(f"breaking precision {b['precision']} "
                        f"< {MIN_BREAKING_PRECISION}")
    if b["recall"] < MIN_BREAKING_RECALL:
        breaches.append(f"breaking recall {b['recall']} "
                        f"< {MIN_BREAKING_RECALL}")
    if result["missed_breaking_count"] > MAX_MISSED_BREAKING:
        breaches.append(f"missed breaking {result['missed_breaking_count']} "
                        f"> {MAX_MISSED_BREAKING}")
    if breaches:
        for item in breaches:
            print(f"check FAIL: {item}")
        return EXIT_FAIL
    print("check PASS")
    return EXIT_OK


def cmd_demo(args) -> int:
    import demo as demo_mod
    try:
        demo_mod.main()
    except AssertionError as exc:
        print(f"demo FAILED: {exc}", file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


# ------------------------------------------------------------------- serve

class _State:
    def __init__(self):
        self.data: Dict = generate_bundle()


_STATE = _State()


def get_state() -> _State:
    return _STATE


def reset_state(data: Optional[Dict] = None) -> None:
    _STATE.data = data if data is not None else generate_bundle()


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: Any) -> None:
        self._send(code, (canonical(payload) + "\n").encode(),
                   "application/json")

    def _bundle_from(self, body: Dict) -> Optional[Dict]:
        if "bundle" not in body:
            return _STATE.data
        candidate = body["bundle"]
        if validate_bundle(candidate):
            return None
        _STATE.data = candidate
        return candidate

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            return self._send_json(200, {"status": "ok"})
        if self.path == "/report":
            return self._send(200, build_markdown_report(
                _STATE.data).encode(), "text/markdown; charset=utf-8")
        return self._send_json(404, {"error": "unknown endpoint"})

    def do_POST(self):  # noqa: N802
        if self.path not in ("/verify", "/classify", "/expiry", "/report"):
            return self._send_json(404, {"error": "unknown endpoint"})
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw) if raw.strip() else {}
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
            data = self._bundle_from(body)
            if data is None:
                return self._send_json(400, {"error": "data quality"})
            if self.path == "/verify":
                return self._send_json(200, verify(data))
            if self.path == "/classify":
                return self._send_json(
                    200, {"predictions": classify_changelog(data)})
            if self.path == "/expiry":
                return self._send_json(200, expiry_report(data))
            return self._send_json(
                200, {"report": build_markdown_report(data)})
        except (ValueError, TypeError, KeyError) as exc:
            return self._send_json(400, {"error": f"bad request: {exc}"})

    def log_message(self, *a: Any) -> None:
        pass


def make_server(port: int) -> HTTPServer:
    return HTTPServer(("127.0.0.1", port), _Handler)


def cmd_serve(args) -> int:
    if args.input:
        data = _load_or_error(args.input)
        if data is None:
            return EXIT_ERROR
        reset_state(data)
    server = make_server(args.port)
    print(f"serving on http://127.0.0.1:{args.port}  "
          f"(POST /verify, /classify, /expiry, /report; "
          f"GET /report, /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="partner-integration-ops-kit",
        description="Partner changelog breaking-change classifier with "
                    "a full verification pass against ground truth.")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="emit the synthetic bundle")
    g.add_argument("--out", default=None)
    g.set_defaults(func=cmd_generate)

    for name, func, helptext in [
            ("classify", cmd_classify, "classify changelog diffs"),
            ("verify", cmd_verify, "verify classifications vs truth"),
            ("expiry", cmd_expiry, "credential expiry tiers"),
            ("report", cmd_report, "markdown verification report")]:
        s = sub.add_parser(name, help=helptext)
        s.add_argument("--input", required=True)
        s.add_argument("--out", default=None)
        s.set_defaults(func=func)

    c = sub.add_parser("check", help="CI gate: exit 0 pass / 1 breach / 2 error")
    c.add_argument("--input", required=True)
    c.set_defaults(func=cmd_check)

    sub.add_parser("demo", help="run the end-to-end demo").set_defaults(func=cmd_demo)

    s = sub.add_parser("serve", help="localhost JSON/markdown API")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--input", default=None)
    s.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
