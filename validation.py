"""Data-quality gate for a bundle. Reports issues, never raises."""

from __future__ import annotations

from datetime import date

CHANGE_TYPES = {
    "field_added", "field_removed", "field_renamed", "type_changed",
    "requirement_changed", "description_changed",
    "enum_value_added", "enum_value_removed",
}
TRUTHS = {"breaking", "non-breaking"}
KINDS = {"api_key", "certificate", "oauth_secret"}


def _is_date(text) -> bool:
    try:
        date.fromisoformat(text)
        return True
    except (TypeError, ValueError):
        return False


def validate_bundle(bundle) -> list:
    issues = []
    if not isinstance(bundle, dict):
        return ["bundle must be a JSON object"]
    if not _is_date(bundle.get("as_of")):
        issues.append("as_of must be an ISO date (YYYY-MM-DD)")
    partners = bundle.get("partners")
    if not isinstance(partners, list) or not partners:
        issues.append("partners must be a non-empty list")
        partners = []
    partner_ids = set()
    for p in partners:
        pid = p.get("partner_id") if isinstance(p, dict) else None
        if not pid:
            issues.append("partner missing partner_id")
        elif pid in partner_ids:
            issues.append(f"duplicate partner_id: {pid}")
        partner_ids.add(pid)
    contracts = bundle.get("contracts", {})
    if not isinstance(contracts, dict):
        issues.append("contracts must be an object")
        contracts = {}
    for pid in contracts:
        if pid not in partner_ids:
            issues.append(f"contract for unknown partner: {pid}")
    seen = set()
    for row in bundle.get("changelog", []):
        cid = row.get("id")
        if not cid:
            issues.append("changelog entry missing id")
            continue
        if cid in seen:
            issues.append(f"duplicate changelog id: {cid}")
        seen.add(cid)
        if row.get("partner_id") not in partner_ids:
            issues.append(f"{cid}: unknown partner {row.get('partner_id')!r}")
        if row.get("change_type") not in CHANGE_TYPES:
            issues.append(f"{cid}: unknown change_type {row.get('change_type')!r}")
        if row.get("truth") not in TRUTHS:
            issues.append(f"{cid}: truth must be breaking or non-breaking")
        if not row.get("field"):
            issues.append(f"{cid}: missing field")
    seen = set()
    for cred in bundle.get("credentials", []):
        kid = cred.get("id")
        if not kid:
            issues.append("credential missing id")
            continue
        if kid in seen:
            issues.append(f"duplicate credential id: {kid}")
        seen.add(kid)
        if cred.get("partner_id") not in partner_ids:
            issues.append(f"{kid}: unknown partner {cred.get('partner_id')!r}")
        if cred.get("kind") not in KINDS:
            issues.append(f"{kid}: unknown kind {cred.get('kind')!r}")
        if not _is_date(cred.get("expires_on")):
            issues.append(f"{kid}: expires_on must be an ISO date")
    return issues
