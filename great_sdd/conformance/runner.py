"""Run a consumer against the committed GREAT fixtures (no network).

A consumer_fn(input: dict) -> dict re-implements the rule; the runner exact-matches
its output against expected_output and reports which rule_ids were exercised
(feed that to coverage.py).

The bundled `oracle_consumer_fn` is the reference Python consumer: it re-runs the
same deterministic oracle the fixtures were generated from, demonstrating a 100%
match for an importing Python backend. A real backend would substitute its own
implementation here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdd.base_conformance import run_conformance, normalize_output, read_version, run_endpoint_conformance
from great_sdd.conformance.generate import FIXTURES_DIR, REPO_ROOT, build_probes, ENDPOINTS_DIR
from great_sdd.conformance.endpoints import project_lines as _project_lines_ep


def load_fixtures(fixtures_dir: Path = FIXTURES_DIR) -> list[dict]:
    entries: list[dict] = []
    for fp in sorted(Path(fixtures_dir).glob("*.json")):
        if fp.name.startswith("_"):
            continue
        entries.extend(json.loads(fp.read_text()))
    return entries


def _dispatch_key(rule_ids, inp) -> str:
    return json.dumps({"rule_ids": sorted(rule_ids), "input": inp}, sort_keys=True)


def _oracle_dispatch() -> dict:
    """Map (rule_ids, input) -> the probe fn that produced it.

    Keyed on rule_ids+input (not input alone) because the same input legitimately
    appears under different rules with different expected outputs.
    """
    table = {}
    for probes in build_probes().values():
        for p in probes:
            for case in p.cases:
                table[_dispatch_key(p.rule_ids, case)] = p.fn
    return table


def oracle_consumer_fn(req: dict) -> dict:
    """Reference consumer: an importing Python backend re-running the oracle.

    req = {"rule_ids": [...], "input": {...}} — dispatches on rule_ids+input.
    """
    fn = _oracle_dispatch()[_dispatch_key(req["rule_ids"], req["input"])]
    return normalize_output(fn(req["input"]))


def run_against_fixtures(consumer_fn, fixtures_dir: Path = FIXTURES_DIR) -> dict:
    return run_conformance(load_fixtures(fixtures_dir), consumer_fn)


# ── Endpoint conformance ──

_ENDPOINT_ORACLES = {
    "GET /project-lines": _project_lines_ep.list_project_lines,
}


def oracle_endpoint_consumer_fn(req: dict) -> dict:
    """Reference endpoint consumer: re-run the oracle.

    req = {"endpoint", "request", "seed"} — dispatches on endpoint. A real backend
    would instead seed its store from req["seed"] and call its own handler.
    """
    return _ENDPOINT_ORACLES[req["endpoint"]](req["request"])


def load_endpoint_fixtures(endpoints_dir: Path = ENDPOINTS_DIR) -> list:
    return [json.loads(fp.read_text())
            for fp in sorted(Path(endpoints_dir).glob("*.json"))]


def run_endpoints_against_fixtures(consumer_fn, endpoints_dir: Path = ENDPOINTS_DIR) -> list:
    return [run_endpoint_conformance(fx, consumer_fn)
            for fx in load_endpoint_fixtures(endpoints_dir)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Run the reference consumer against committed fixtures.")
    ap.add_argument("--emit-report", help="Write a consumer report for coverage.py.")
    args = ap.parse_args(argv)

    rep = run_against_fixtures(oracle_consumer_fn)
    print(f"Conformance: {rep['total'] - rep['failed_count']}/{rep['total']} passed; "
          f"{len(rep['exercised_rule_ids'])} rules exercised.")
    for f in rep["failures"][:5]:
        print(f"  FAIL {f['rule_ids']} input={f['input']}")
    if args.emit_report:
        Path(args.emit_report).write_text(json.dumps({
            "sdd_version": read_version(REPO_ROOT),
            "exercised_rule_ids": rep["exercised_rule_ids"],
        }, sort_keys=True, indent=2))
        print(f"  wrote consumer report -> {args.emit_report}")
    ep_reports = run_endpoints_against_fixtures(oracle_endpoint_consumer_fn)
    for er in ep_reports:
        print(f"Endpoint {er['endpoint']}: {er['total'] - er['failed_count']}/{er['total']} cases passed.")
    ep_ok = all(er["passed"] for er in ep_reports)
    return 0 if (rep["passed"] and ep_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
