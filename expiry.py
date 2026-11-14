"""Credential / certificate expiry alert tiers — deliberately small.

This is date math, not a feature: given a pinned ``as_of`` date, each
credential lands in exactly one tier by days remaining:

  expired   days < 0
  critical  0 <= days <= 7
  warning   8 <= days <= 30
  watch     31 <= days <= 90
  ok        days > 90
"""

from __future__ import annotations

from datetime import date

TIERS = ("expired", "critical", "warning", "watch", "ok")
_SEVERITY = {tier: i for i, tier in enumerate(TIERS)}


def _parse(text: str) -> date:
    return date.fromisoformat(text)


def days_remaining(expires_on: str, as_of: str) -> int:
    return (_parse(expires_on) - _parse(as_of)).days


def tier_for_days(days: int) -> str:
    if days < 0:
        return "expired"
    if days <= 7:
        return "critical"
    if days <= 30:
        return "warning"
    if days <= 90:
        return "watch"
    return "ok"


def classify_credential(cred: dict, as_of: str) -> dict:
    days = days_remaining(cred["expires_on"], as_of)
    return {"id": cred["id"], "partner_id": cred["partner_id"],
            "kind": cred["kind"], "label": cred["label"],
            "expires_on": cred["expires_on"], "days_remaining": days,
            "tier": tier_for_days(days)}


def expiry_report(bundle: dict) -> dict:
    """All credentials tiered, sorted by severity then expiry date."""
    as_of = bundle["as_of"]
    rows = [classify_credential(c, as_of) for c in bundle.get("credentials", [])]
    rows.sort(key=lambda r: (_SEVERITY[r["tier"]], r["expires_on"], r["id"]))
    counts = {tier: 0 for tier in TIERS}
    for row in rows:
        counts[row["tier"]] += 1
    return {"as_of": as_of, "counts": counts, "credentials": rows,
            "actionable": [r["id"] for r in rows
                           if r["tier"] in ("expired", "critical", "warning")]}
