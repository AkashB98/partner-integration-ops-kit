"""Shared builders for the test suite (not a test module)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def change(cid="T1", change_type="field_added", truth="non-breaking", **kw):
    row = {"id": cid, "partner_id": "p1", "change_type": change_type,
           "field": "f1", "truth": truth}
    row.update(kw)
    return row


def mini_bundle(changelog=None, credentials=None, as_of="2026-11-14"):
    return {
        "as_of": as_of,
        "partners": [{"partner_id": "p1", "name": "Partner One"}],
        "contracts": {"p1": {"fields": {
            "f1": {"type": "string", "required": False,
                   "description": "A field."}}}},
        "changelog": changelog if changelog is not None else [],
        "credentials": credentials if credentials is not None else [],
    }
