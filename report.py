"""Markdown verification report, copied from the computed numbers."""

from __future__ import annotations

from expiry import expiry_report
from verify import verify


def build_markdown_report(bundle: dict) -> str:
    result = verify(bundle)
    exp = expiry_report(bundle)
    b = result["per_class"]["breaking"]
    n = result["per_class"]["non-breaking"]
    lines = [
        "# Partner integration verification report",
        "",
        "> Honesty line: synthetic data only. The classifier is "
        "rule-based — no AI or ML is doing the classification — and "
        "every classification is re-checked against planted ground "
        "truth below.",
        "",
        f"As of {bundle['as_of']} · {result['total']} changelog entries "
        f"checked · accuracy {result['accuracy']}",
        "",
        "## Classification vs ground truth",
        "",
        "| Class | Precision | Recall | TP | FP | FN |",
        "|---|---|---|---|---|---|",
        f"| breaking | {b['precision']} | {b['recall']} | {b['tp']} "
        f"| {b['fp']} | {b['fn']} |",
        f"| non-breaking | {n['precision']} | {n['recall']} | {n['tp']} "
        f"| {n['fp']} | {n['fn']} |",
        "",
        "## Missed breaking changes (the costly error)",
        "",
    ]
    if result["missed_breaking"]:
        for cid in result["missed_breaking"]:
            lines.append(f"- MISSED BREAKING: {cid} — truth is breaking, "
                         "classifier said non-breaking. A missed breaking "
                         "change ships silently and breaks partner "
                         "integrations in production.")
    else:
        lines.append("- None. Every breaking change was caught.")
    lines += ["", "## False alarms", ""]
    if result["false_alarms"]:
        for cid in result["false_alarms"]:
            lines.append(f"- FALSE ALARM: {cid} — classifier said "
                         "breaking, truth is non-breaking. Costs a "
                         "review conversation, not an outage.")
    else:
        lines.append("- None.")
    lines += ["", "## Credential / certificate expiry", "",
              f"Counts by tier: {exp['counts']}", ""]
    for row in exp["credentials"]:
        lines.append(f"- {row['id']} [{row['tier']}] "
                     f"{row['label']} — expires {row['expires_on']} "
                     f"({row['days_remaining']} days)")
    lines.append("")
    return "\n".join(lines)
