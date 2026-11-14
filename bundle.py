"""Deterministic synthetic bundle: fictional partners, pinned field
contracts, labelled changelog entries, and a credential expiry registry.

SYNTHETIC DATA ONLY — every partner, field, and date here is fictional.
The ``as_of`` date is pinned (2026-11-14) so expiry math is deterministic
in tests and evals; nothing reads the wall clock.

Ground-truth labels (``truth``) are planted deliberately:
- 12 breaking / 12 non-breaking changelog entries.
- One planted MISSED BREAKING case: a description change that silently
  redefines a field's units (cents -> dollars). A rule-based classifier
  that treats every description change as cosmetic will miss it — that
  is the costly error the verification pass exists to surface.
- One planted false alarm: an integer -> number type widening, which is
  backward compatible (truth: non-breaking) but a naive "any type change
  is breaking" rule flags as breaking.
"""

from __future__ import annotations

import copy
import json

AS_OF = "2026-11-14"

_PARTNERS = [
    {"partner_id": "northwind-pay", "name": "Northwind Pay"},
    {"partner_id": "helio-health", "name": "Helio Health"},
    {"partner_id": "cobalt-logistics", "name": "Cobalt Logistics"},
    {"partner_id": "fern-retail", "name": "Fern Retail"},
]

_CONTRACTS = {
    "northwind-pay": {"fields": {
        "amount_cents": {"type": "integer", "required": True,
                         "description": "Charge amount in cents."},
        "currency": {"type": "string", "required": True,
                     "description": "ISO 4217 currency code."},
        "customer_email": {"type": "string", "required": False,
                           "description": "Receipt email."},
        "status": {"type": "enum", "required": True,
                   "description": "One of: pending, settled, failed."},
        "metadata_note": {"type": "string", "required": False,
                          "description": "Free-text note."},
    }},
    "helio-health": {"fields": {
        "patient_ref": {"type": "string", "required": True,
                        "description": "Opaque patient reference."},
        "appointment_at": {"type": "string", "required": True,
                           "description": "ISO 8601 appointment time."},
        "consent_flag": {"type": "boolean", "required": True,
                         "description": "Consent recorded."},
        "clinic_code": {"type": "string", "required": False,
                        "description": "Clinic identifier."},
    }},
    "cobalt-logistics": {"fields": {
        "shipment_id": {"type": "string", "required": True,
                        "description": "Shipment identifier."},
        "weight_grams": {"type": "integer", "required": True,
                         "description": "Weight in grams."},
        "priority": {"type": "enum", "required": False,
                     "description": "One of: standard, express."},
        "carrier_note": {"type": "string", "required": False,
                         "description": "Carrier note."},
    }},
    "fern-retail": {"fields": {
        "order_id": {"type": "string", "required": True,
                     "description": "Order identifier."},
        "total_price": {"type": "number", "required": True,
                        "description": "Order total."},
        "discount_code": {"type": "string", "required": False,
                          "description": "Optional discount code."},
        "channel": {"type": "enum", "required": True,
                    "description": "One of: web, store."},
    }},
}


def _chg(cid, partner, change_type, field, truth, **kw):
    row = {"id": cid, "partner_id": partner, "change_type": change_type,
           "field": field, "truth": truth}
    row.update(kw)
    return row


_CHANGELOG = [
    # --- breaking (classifier should catch 11 of 12) ---
    _chg("C01", "northwind-pay", "field_removed", "metadata_note", "breaking"),
    _chg("C02", "northwind-pay", "type_changed", "amount_cents", "breaking",
         old_type="integer", new_type="string"),
    _chg("C03", "helio-health", "field_added", "consent_scope", "breaking",
         new_type="string", new_required=True),
    _chg("C04", "helio-health", "requirement_changed", "clinic_code",
         "breaking", old_required=False, new_required=True),
    _chg("C05", "cobalt-logistics", "enum_value_removed", "priority",
         "breaking", removed_value="express"),
    _chg("C06", "cobalt-logistics", "field_renamed", "weight_grams",
         "breaking", new_field="weight_g"),
    _chg("C07", "fern-retail", "field_removed", "discount_code", "breaking"),
    _chg("C08", "fern-retail", "type_changed", "channel", "breaking",
         old_type="enum", new_type="string"),
    _chg("C09", "northwind-pay", "field_added", "idempotency_key", "breaking",
         new_type="string", new_required=True),
    _chg("C10", "helio-health", "requirement_changed", "patient_ref",
         "breaking", old_required=False, new_required=True),
    _chg("C11", "cobalt-logistics", "type_changed", "shipment_id", "breaking",
         old_type="string", new_type="integer"),
    # Planted miss: description redefines units cents -> dollars.
    _chg("C12", "northwind-pay", "description_changed", "amount_cents",
         "breaking",
         old_description="Charge amount in cents.",
         new_description="Charge amount in dollars."),
    # --- non-breaking (classifier should clear 11 of 12) ---
    _chg("C13", "northwind-pay", "field_added", "receipt_locale",
         "non-breaking", new_type="string", new_required=False),
    _chg("C14", "helio-health", "description_changed", "clinic_code",
         "non-breaking",
         old_description="Clinic identifier.",
         new_description="Clinic identifier (site code)."),
    _chg("C15", "cobalt-logistics", "requirement_changed", "carrier_note",
         "non-breaking", old_required=True, new_required=False),
    _chg("C16", "fern-retail", "enum_value_added", "channel", "non-breaking",
         added_value="kiosk"),
    _chg("C17", "fern-retail", "field_added", "gift_wrap", "non-breaking",
         new_type="boolean", new_required=False),
    _chg("C18", "northwind-pay", "description_changed", "customer_email",
         "non-breaking",
         old_description="Receipt email.",
         new_description="Receipt email address."),
    _chg("C19", "helio-health", "enum_value_added", "priority", "non-breaking",
         added_value="overnight"),
    _chg("C20", "cobalt-logistics", "requirement_changed", "priority",
         "non-breaking", old_required=True, new_required=False),
    _chg("C21", "fern-retail", "field_added", "loyalty_id", "non-breaking",
         new_type="string", new_required=False),
    _chg("C22", "helio-health", "description_changed", "appointment_at",
         "non-breaking",
         old_description="ISO 8601 appointment time.",
         new_description="ISO 8601 appointment start time (UTC)."),
    _chg("C23", "northwind-pay", "enum_value_added", "status", "non-breaking",
         added_value="refunded"),
    # Planted false alarm: integer -> number is a safe widening.
    _chg("C24", "cobalt-logistics", "type_changed", "weight_grams",
         "non-breaking", old_type="integer", new_type="number"),
]

_CREDENTIALS = [
    {"id": "K01", "partner_id": "northwind-pay", "kind": "certificate",
     "label": "Northwind TLS cert", "expires_on": "2026-11-10"},
    {"id": "K02", "partner_id": "northwind-pay", "kind": "api_key",
     "label": "Northwind prod API key", "expires_on": "2026-11-14"},
    {"id": "K03", "partner_id": "helio-health", "kind": "certificate",
     "label": "Helio mTLS cert", "expires_on": "2026-11-18"},
    {"id": "K04", "partner_id": "helio-health", "kind": "oauth_secret",
     "label": "Helio OAuth secret", "expires_on": "2026-11-25"},
    {"id": "K05", "partner_id": "cobalt-logistics", "kind": "api_key",
     "label": "Cobalt webhook signing key", "expires_on": "2026-12-05"},
    {"id": "K06", "partner_id": "cobalt-logistics", "kind": "certificate",
     "label": "Cobalt client cert", "expires_on": "2026-12-30"},
    {"id": "K07", "partner_id": "fern-retail", "kind": "api_key",
     "label": "Fern catalogue API key", "expires_on": "2027-01-15"},
    {"id": "K08", "partner_id": "fern-retail", "kind": "certificate",
     "label": "Fern TLS cert", "expires_on": "2027-03-01"},
    {"id": "K09", "partner_id": "northwind-pay", "kind": "oauth_secret",
     "label": "Northwind OAuth secret", "expires_on": "2027-06-01"},
]


def generate_bundle() -> dict:
    """Return a fresh deep copy of the canonical synthetic bundle."""
    return copy.deepcopy({
        "as_of": AS_OF,
        "partners": _PARTNERS,
        "contracts": _CONTRACTS,
        "changelog": _CHANGELOG,
        "credentials": _CREDENTIALS,
    })


def bundle_to_json(bundle: dict) -> str:
    return json.dumps(bundle, sort_keys=True, indent=2) + "\n"
