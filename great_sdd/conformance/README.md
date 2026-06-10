# Conformance Layer — the SDD as a deterministic oracle

The first three layers of this kit (`specs/`, `modules/`, `pipeline/`) define the
GREAT business rules and verify them with `tests/`. This **fourth layer** lets *any
consumer* — a Python backend, a TypeScript frontend — prove its own code obeys the
same rules, hermetically and in CI.

The SDD acts as an **oracle**: a deterministic reference implementation. We execute
representative cases against the pure functions and emit **golden fixtures** as
language-neutral JSON. Those committed fixtures **are the contract**. The live
oracle is *not* a runtime dependency of the consumer — it only regenerates the
fixtures.

> **Hard rule: everything here is deterministic.** Fixtures are generated with a
> Tripwire LM injected — if a covered rule's code path calls an LLM, generation
> aborts loudly. Nothing touches the network, an LLM, timestamps, or randomness.

---

## Fixture schema

One file per view in [`fixtures/`](fixtures/), plus `_inventory.json` (the reconciled
rule census). Each view file is a JSON array of entries:

```json
{
  "expected_output": {
    "error_message": "Cannot transition from 'approved' to 'draft'",
    "is_valid": false
  },
  "input": {
    "current_status": "approved",
    "has_saved_draft_in_session": true,
    "target_status": "draft"
  },
  "rule_ids": ["BR-02", "BR-04", "BR-15", "BR-16", "BR-17", "ERev-BR-03"],
  "sdd_version": "1.1.0"
}
```

- `rule_ids` — the business rules this case exercises (feeds coverage).
- `input` — the rule's input, as neutral JSON.
- `expected_output` — the oracle's output. **`*_json` fields are already parsed
  into real JSON values** (not "a Python string of JSON"), so any language can
  deep-equal them directly.
- `sdd_version` — the oracle version that produced the fixture (skew detection).

Files are byte-stable: sorted keys, 2-space indent, trailing newline, no
timestamps. Same oracle + same code → identical bytes.

---

## Python consumer

```python
from great_sdd.conformance.runner import run_against_fixtures

def my_consumer(req):
    # req = {"rule_ids": [...], "input": {...}} — dispatch on rule_ids,
    # re-implement the rule, return the output dict.
    ...

report = run_against_fixtures(my_consumer)
assert report["passed"], report["failures"][:3]
```

The bundled `oracle_consumer_fn` is the reference implementation (it re-runs the
oracle; 85/85 fixtures pass). A real backend substitutes its own logic.

The consumer receives `{"rule_ids", "input"}` — **never `expected_output`** — so it
cannot cheat, and it can dispatch on `rule_ids` (the same `input` legitimately
appears under different rules).

---

## TypeScript consumer (the frontend cannot import Python)

The FE loads the **same JSON**, re-implements the rule, and asserts deep-equality.
No Python, no network.

```ts
import fixtures from "great-sdd-kit/great_sdd/conformance/fixtures/pre_estimation.json";
import { validateStatusTransition } from "../src/rules/statusTransition";

const exercised = new Set<string>();

for (const fx of fixtures) {
  // Dispatch on rule_ids — you know which rule each fixture checks.
  if (fx.rule_ids.includes("BR-04")) {
    const actual = validateStatusTransition(fx.input);   // your TS impl
    expect(actual).toEqual(fx.expected_output);           // deep equal
    fx.rule_ids.forEach((r) => exercised.add(r));
  }
}

// Emit a consumer report for the coverage gate:
// { "sdd_version": "<pinned>", "exercised_rule_ids": [...exercised] }
```

Then run the coverage gate against that report:

```bash
python -m great_sdd.conformance.coverage --report fe-report.json --threshold 0.70
```

**Never serialize language-specific objects into fixtures** — only JSON-neutral
values. The generator guarantees this via canonical JSON + `*_json` normalization;
consumers must compare against neutral JSON, not reconstructed class instances.

---

## Version skew

A consumer pins fixtures at some `sdd_version`. `coverage.py` compares the report's
`sdd_version` against the live oracle and **fails on mismatch** — your fixtures are
stale, regenerate and re-verify.

---

## Coverage & exclusions

`coverage.py` reports BR coverage over the *coverable* surface — business rules
minus two **documented** exclusion buckets (see [`exclusions.py`](exclusions.py)):

- **`NON_DETERMINISTIC_RULES`** — LM-only capabilities (summary prose, the
  incompatibility *explanation*, free-text inductor *ranking*). The deterministic
  decisions behind them (e.g. `is_compatible`) *are* covered.
- **`NO_FUNCTION_SURFACE_RULES`** — deterministic but policy/UI/persistence rules
  with no pure function to execute (e.g. `BR-01` no-deletion).

Nothing is silently dropped — every excluded rule is listed with a reason in the
report and the committed `_inventory.json`.

---

## Regenerating fixtures

```bash
python -m great_sdd.conformance.generate          # rewrite fixtures
python -m great_sdd.conformance.generate --check    # CI: exit 1 on drift
```

CI ([`.github/workflows/conformance.yml`](../../.github/workflows/conformance.yml))
regenerates and fails on any diff vs the committed fixtures, then runs `pytest` and
the coverage gate.

## Endpoint conformance (mirroring an external API contract)

Beyond per-rule fixtures, the layer can mirror a full **HTTP endpoint contract** as
golden fixtures. Unlike rule fixtures (where the SDD is the oracle), an endpoint
fixture MIRRORS an external contract (OpenAPI + backend DTO + frontend types) — the
external API is the source of truth; the SDD reflects it for a cross-language test.
Endpoint fixtures do NOT enter the business-rule census.

- Oracle: `great_sdd/conformance/endpoints/<name>.py` — a deterministic reference
  (fixed seed, no network/LLM/time) that re-implements the documented behavior.
- Fixture: `fixtures/endpoints/<name>.json` — `{endpoint, sdd_version, seed, cases:[{request, expected:{status, body}}]}`, byte-stable.
- Runner: `run_endpoints_against_fixtures(consumer_fn)` passes `{endpoint, request, seed}`
  (never `expected`) and exact-matches `{status, body}`.

Implemented: `GET /project-lines` (mirrors `cap_horse_great` pev-openapi + `list_lines`).
The frontend loads the same JSON as its mock + contract test; the backend can seed
`fixture.seed` and run its handler against each `request`.
