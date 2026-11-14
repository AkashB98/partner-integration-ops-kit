"""Verification pass: re-check EVERY automated classification against
the ground-truth labels and report precision / recall per class.

This is the headline of the kit — the Alloy JD asked the hire to explain
how they checked the automation worked. The answer here: never trust the
classifier's own output; score all of it against planted truth, and call
out MISSED BREAKING changes (truth=breaking, predicted=non-breaking)
separately, because a missed breaking change ships silently and breaks
partner integrations in production, while a false alarm only costs a
review conversation.
"""

from __future__ import annotations

from classifier import BREAKING, NON_BREAKING, classify_changelog

CLASSES = (BREAKING, NON_BREAKING)


def _pr(tp: int, fp: int, fn: int) -> dict:
    precision = round(tp / (tp + fp), 4) if (tp + fp) else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall}


def verify(bundle: dict, predictions: list | None = None) -> dict:
    """Score predictions (default: run the classifier) against truth."""
    if predictions is None:
        predictions = classify_changelog(bundle)
    truth_by_id = {c["id"]: c["truth"] for c in bundle.get("changelog", [])}
    counts = {cls: {"tp": 0, "fp": 0, "fn": 0} for cls in CLASSES}
    missed_breaking, false_alarms = [], []
    correct = 0
    for pred in predictions:
        truth = truth_by_id.get(pred["id"])
        guessed = pred["prediction"]
        if truth is None:
            continue
        if guessed == truth:
            correct += 1
            counts[truth]["tp"] += 1
        else:
            counts[guessed]["fp"] += 1
            counts[truth]["fn"] += 1
            if truth == BREAKING:
                missed_breaking.append(pred["id"])
            else:
                false_alarms.append(pred["id"])
    per_class = {cls: _pr(**counts[cls]) for cls in CLASSES}
    total = sum(1 for p in predictions if p["id"] in truth_by_id)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "per_class": per_class,
        "missed_breaking": sorted(missed_breaking),
        "missed_breaking_count": len(missed_breaking),
        "false_alarms": sorted(false_alarms),
        "predictions": predictions,
    }
