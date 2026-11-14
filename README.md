# partner-integration-ops-kit

**The Alloy Technical Partner Operations Analyst JD (surfaced 2026-11-14) described the unglamorous work that keeps partner integrations alive — tracking credential and certificate expiries, watching partner changelogs, automating the backlog — and then asked the sharp question: the hire must explain how they checked the automation worked. This repo is that answer, made runnable: a rule-based classifier judges partner changelog diffs against a pinned field contract, and then a verification pass re-checks every single classification against ground truth and calls out the missed breaking changes by name.**

> **Honesty line: this project is synthetic and NOT production integration tooling. The classifier is rule-based — no AI or ML does the classification, and the README never claims otherwise. No real partner, credential, or changelog data is used anywhere in it.**

A partner **changelog diff** — one recorded change to a partner's API fields — is either **breaking** (existing integrations that rely on the old contract will fail) or **non-breaking** (existing integrations keep working). The expensive mistake is asymmetric: a **false alarm** (flagging a safe change as breaking) costs a review conversation, but a **missed breaking change** ships silently and breaks partner integrations in production. So this kit does not just classify — it **verifies**: every automated classification is scored against planted ground-truth labels, precision and recall are reported per class, and missed breaking changes get their own section in every report.

Stdlib-only Python. Zero network, zero API keys, zero external dependencies.

## Quickstart

```bash
# 1. Emit the synthetic bundle (4 fictional partners, pinned as_of 2026-11-14)
python3 cli.py generate --out bundle.json

# 2. Classify every changelog diff against the pinned contracts
python3 cli.py classify --input bundle.json

# 3. THE point of the repo: verify every classification against ground truth
python3 cli.py verify --input bundle.json

# 4. Credential / certificate expiry tiers (date math, deliberately small)
python3 cli.py expiry --input bundle.json

# 5. Markdown verification report (missed breaking changes first-class)
python3 cli.py report --input bundle.json

# 6. CI gate: exit 0 = pass, 1 = quality breach (breaking precision or
#    recall below 0.9, or more than 1 missed breaking change),
#    2 = data-quality / IO error. Seeded data exits 0.
python3 cli.py check --input bundle.json

# 7. One-command end-to-end demo (incl. a live serve round-trip)
python3 demo.py

# 8. Tiny localhost API: POST /verify, /classify, /expiry, /report,
#    GET /report, GET /health
python3 cli.py serve --port 8765
```

## The seeded bundle at a glance

**4 fictional partners** (Northwind Pay, Helio Health, Cobalt Logistics, Fern Retail), each with a **pinned field contract** — the agreed set of fields, types, and required flags the integration was built against. **24 changelog entries** with planted ground-truth labels, balanced 12 breaking / 12 non-breaking, covering every rule class: field removed, field renamed, type changed, required field added, field becoming required, enum value removed (breaking); optional field added, field becoming optional, enum value added, description change (non-breaking). Plus a **credential registry** of 9 fictional API keys, certificates, and OAuth secrets expiring relative to the pinned `as_of` date of 2026-11-14, so expiry tests never depend on the wall clock.

Two entries are planted to make the classifier fail honestly:

| Entry | What it is | Truth | Classifier says | Why |
|---|---|---|---|---|
| C12 | `amount_cents` description changes from "in cents" to "in dollars" | breaking | non-breaking | The rule "description changes are cosmetic" cannot see a semantic redefinition written as prose |
| C24 | `weight_grams` type changes integer → number | non-breaking | breaking | The rule "any type change is breaking" cannot see a safe widening |

## The classification rules

Explicit, arguable-in-a-review rules — no model, no embeddings, no AI claim:

- **Breaking:** a field is removed or renamed; a field's type changes; a new field is added as required; an existing field becomes required; an enum value is removed.
- **Non-breaking:** a new optional field is added; a field becomes optional; an enum value is added; a description changes.

## Verification results (seeded bundle, all 24 entries re-checked)

| Class | Precision | Recall | TP | FP | FN |
|---|---|---|---|---|---|
| breaking | 0.9167 | 0.9167 | 11 | 1 | 1 |
| non-breaking | 0.9167 | 0.9167 | 11 | 1 | 1 |

- **Accuracy 0.9167 (22/24).** The two errors are exactly the two planted hard cases above — the evals pin their IDs so the failure modes can never quietly change shape.
- **Missed breaking: exactly 1 — C12**, the cents→dollars units redefinition. It is reported by name in the CLI, the report, the demo, and the API, because that is the error class that pages someone at 2 a.m.
- **False alarms: exactly 1 — C24**, the integer→number widening. Reported too, but framed honestly: it costs a conversation, not an outage.
- **Precision** — of the entries flagged breaking, the share that really are. **Recall** — of the entries that really are breaking, the share that got flagged. For the breaking class, recall is the number that matters most, and the `check` gate floors both at 0.9.
- Eval E9 pins a property demos usually skip: the classifier is **truth-blind** — flipping every ground-truth label changes no prediction, only the scores. The classifier never peeks at the answer key; the verifier is the only component allowed to read it.

## Expiry tiers (the small module, on purpose)

Credential/cert expiry is date math, so it gets one small module (`expiry.py`) and one test file — not headline billing. Against the pinned `as_of` date: **expired** < 0 days, **critical** 0–7, **warning** 8–30, **watch** 31–90, **ok** > 90. Seeded registry: 1 expired, 2 critical, 2 warning, 2 watch, 2 ok; the actionable list (expired + critical + warning) is K01–K05, sorted severity-first.

## Architecture

| Module | Job |
|---|---|
| `bundle.py` | Deterministic synthetic bundle: 4 fictional partners, pinned contracts, 24 labelled changelog entries, 9-credential expiry registry, pinned `as_of` |
| `classifier.py` | The rule-based breaking / non-breaking classifier (truth-blind by construction) |
| `verify.py` | The verification pass: per-class precision/recall, missed-breaking and false-alarm lists |
| `expiry.py` | Credential/cert expiry tiers — one small date-math module |
| `validation.py` | Data-quality gate (partners, contracts, change types, labels, dates, duplicates); reports issues, never raises on bad data |
| `report.py` | The markdown verification report, copied from the computed numbers |
| `cli.py` | `generate` / `classify` / `verify` / `expiry` / `report` / `check` (CI exit 0/1/2) / `demo` / `serve` (stdlib `http.server` on 127.0.0.1) |
| `demo.py` | End-to-end narrative with asserts: determinism, verification, expiry, check exit codes, live localhost serve round-trip |
| `fixtures/` | The canonical bundle (`sample_bundle.json`), pinned equal to `bundle.py` output by eval E12 |

## Evals

`python3 evals/run_evals.py` → **13/13 golden evals**, report committed at `evals/eval_report.json` (md5 `6d302c33d8d20bd7e5973e80b8d50eaf`, byte-identical across 3 verified runs):

- **E1** bundle determinism — canonical bundle bytes pinned
- **E2** headline counts (4 partners, 24 entries split 12/12, 9 credentials, validates clean)
- **E3** predicted split pinned (12 breaking / 12 non-breaking)
- **E4** per-class precision/recall pinned (0.9167 everywhere; breaking TP/FP/FN = 11/1/1)
- **E5** missed breaking pinned to exactly C12, the planted units change
- **E6** false alarm pinned to exactly C24, the planted safe widening
- **E7** all 6 breaking change types caught at least once — rule-table coverage, not just aggregates
- **E8** expiry tiers pinned (1/2/2/2/2, actionable K01–K05)
- **E9** classifier truth-blindness — label flip changes no prediction
- **E10** CLI `check` exit codes 0 / 2
- **E11** serve round-trip matches local verify + report exactly
- **E12** bundled fixture pinned to the canonical bundle
- **E13** report determinism + the honesty line + the C12 callout

Unit tests: `python3 -m unittest discover -s tests` → **61 hermetic tests**, including a no-network enforcement test (sockets stubbed), one test per classifier rule plus its edges, hand-scored verification cases (perfect classifier, single missed breaking, empty bundle), every expiry tier boundary (days −1/0/7/8/30/31/90/91), validation defects, CLI exit codes, and serve round-trips. The expiry module has exactly one test file, per its deliberately small scope.

## Development loop — what the checks actually found

No fabricated war stories. The build itself was green on its first full run (61 tests, 13 evals, demo — no code bug surfaced and none is claimed here). What the verification pass genuinely surfaces is in the seeded numbers, and it is the reason the repo exists:

1. **The classifier's two errors are not random — they are the two rules' known blind spots.** "Any type change is breaking" cannot express widening; "description changes are cosmetic" cannot express a semantic redefinition. A verification pass that only reported accuracy (0.9167) would hide both; reporting missed breaking by ID makes the blind spot a named, tracked defect instead of a vibe.
2. **The costly error and the cheap error score identically in aggregate metrics.** C12 (missed breaking) and C24 (false alarm) each cost exactly one precision/recall point — but only one of them breaks partner integrations in production. That asymmetry is why missed breaking is a separate list, a separate eval (E5), and a separate term in the `check` gate, rather than a footnote inside accuracy.

## Scope and honest limits

- **Rule-based, deliberately.** Real changelog monitoring also parses OpenAPI/JSON-Schema diffs mechanically; this kit works on already-extracted diff records so the classification + verification logic is the subject, not a parser.
- **The two blind spots are real limits, not staged humility.** Type-widening awareness (integer → number, optional-isation of return types) and semantic description review (units, currency, timezone redefinitions) are exactly what a v2 would add — most likely as a "needs human review" third verdict rather than a forced binary.
- **Planted labels are a teaching device.** Real ground truth comes from incident history and partner confirmations, which are noisier and slower; precision/recall here are cleaner than any real backlog's.
- **No pipeline reporting.** Per the JD-scoped design, the general reporting/dashboard layer was cut — the verification report is the only output surface, because it is the part the JD actually interrogates.
- **The API is a demo surface.** It binds 127.0.0.1 only, holds its bundle in memory, and resets on restart.

## Why this project

The Partner Operations gap the Alloy JD named is not "can you watch a changelog" — it is "when the automation says a partner change is safe, how do you know it is right, and what does it cost when it is wrong?" This project practises exactly that reasoning end-to-end: pin the contract, classify with rules you can defend line by line, re-check every classification against ground truth, and put the missed breaking change — the one that ships silently — at the top of the report, with every number reproducible from the committed bundle and pinned by an eval.
