"""Rule-based changelog classifier.

This is deliberately NOT an AI/ML classifier. Each changelog diff is
judged by explicit rules against the partner's pinned field contract —
the same rules an integration engineer would apply in a review:

  breaking:
    - a field is removed or renamed (consumers referencing it break)
    - a field's type changes (any change; see honest limit below)
    - a new field is added as required (old payloads no longer validate)
    - an existing field becomes required
    - an enum value is removed (consumers may receive/handle it no more)

  non-breaking:
    - a new optional field is added
    - a field becomes optional
    - an enum value is added
    - a description changes (treated as cosmetic)

Honest limits, pinned by the golden evals rather than hidden:
  - "any type change is breaking" over-flags safe widenings such as
    integer -> number (planted entry C24 is a false alarm).
  - "description changes are cosmetic" misses semantic redefinitions
    written as prose, e.g. a units change cents -> dollars (planted
    entry C12 is a missed breaking change — the costly error class).
The verification pass in verify.py measures exactly these failures.
"""

from __future__ import annotations

BREAKING = "breaking"
NON_BREAKING = "non-breaking"

_REASONS = {
    "field_removed": "field removed from the contract",
    "field_renamed": "field renamed; old name no longer resolves",
    "type_changed": "field type changed",
    "enum_value_removed": "enum value removed",
}


def classify_change(change: dict, contract: dict | None = None) -> dict:
    """Classify one changelog entry. Never reads ``truth``.

    Returns {"id", "partner_id", "field", "prediction", "reason"}.
    ``contract`` is accepted so callers can pass the pinned contract;
    the current rules are fully determined by the diff itself, and the
    parameter documents that the judgement is contract-relative.
    """
    ctype = change.get("change_type")
    if ctype in _REASONS:
        prediction, reason = BREAKING, _REASONS[ctype]
    elif ctype == "field_added":
        if change.get("new_required"):
            prediction = BREAKING
            reason = "new field added as required; old payloads fail validation"
        else:
            prediction = NON_BREAKING
            reason = "new optional field added; old payloads still validate"
    elif ctype == "requirement_changed":
        if change.get("old_required") is False and change.get("new_required") is True:
            prediction = BREAKING
            reason = "field became required; old payloads may omit it"
        else:
            prediction = NON_BREAKING
            reason = "field became optional; strictly more permissive"
    elif ctype == "enum_value_added":
        prediction, reason = NON_BREAKING, "enum value added; existing values unchanged"
    elif ctype == "description_changed":
        prediction, reason = NON_BREAKING, "description-only change; treated as cosmetic"
    else:
        prediction, reason = NON_BREAKING, f"unrecognised change type {ctype!r}; defaulted to non-breaking"
    return {"id": change.get("id"), "partner_id": change.get("partner_id"),
            "field": change.get("field"), "prediction": prediction,
            "reason": reason}


def classify_changelog(bundle: dict) -> list:
    """Classify every changelog entry in bundle order (deterministic)."""
    contracts = bundle.get("contracts", {})
    out = []
    for change in bundle.get("changelog", []):
        contract = contracts.get(change.get("partner_id"))
        out.append(classify_change(change, contract))
    return out
