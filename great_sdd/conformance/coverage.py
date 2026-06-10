"""Coverage + version-skew gate for GREAT conformance.

Inputs (one of):
  --report PATH     consumer report: {"sdd_version": "...", "exercised_rule_ids": [...]}
  --from-fixtures   use the union of rule_ids in the committed fixtures (oracle self-check)

Exit code != 0 if coverage < threshold OR version skew detected.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdd.base_conformance import compute_coverage, compute_version_skew, read_version
from great_sdd.conformance.rule_inventory import business_rule_ids
from great_sdd.conformance.exclusions import (
    NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES)
from great_sdd.conformance.generate import REPO_ROOT, FIXTURES_DIR


def _denominator() -> list[str]:
    """Business rules minus deterministic-but-unprobeable ones (documented)."""
    excluded = set(NO_FUNCTION_SURFACE_RULES)
    return [r for r in business_rule_ids() if r not in excluded]


def _fixture_exercised_ids() -> list[str]:
    ids: set[str] = set()
    for fp in sorted(FIXTURES_DIR.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        for entry in json.loads(fp.read_text()):
            ids.update(entry["rule_ids"])
    return sorted(ids)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GREAT conformance coverage gate.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--report", help="Path to consumer report JSON.")
    src.add_argument("--from-fixtures", action="store_true", help="Use committed fixtures.")
    ap.add_argument("--threshold", type=float, default=0.70)
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = ap.parse_args(argv)

    oracle_version = read_version(REPO_ROOT)
    if args.from_fixtures:
        exercised = _fixture_exercised_ids()
        consumer_version = oracle_version
    else:
        data = json.loads(Path(args.report).read_text())
        exercised = data.get("exercised_rule_ids", [])
        consumer_version = data.get("sdd_version", "")

    cov = compute_coverage(_denominator(), exercised, args.threshold)
    skew = compute_version_skew(consumer_version, oracle_version)
    report = {
        "coverage": cov,
        "version_skew": skew,
        "excluded": {
            "non_deterministic": NON_DETERMINISTIC_RULES,
            "no_function_surface": NO_FUNCTION_SURFACE_RULES,
        },
    }
    if args.json:
        print(json.dumps(report, sort_keys=True, indent=2))
    else:
        print(f"Coverage: {cov['covered_count']}/{cov['total']} "
              f"({cov['coverage'] * 100:.1f}%) threshold={cov['threshold'] * 100:.0f}% "
              f"-> {'PASS' if cov['passed'] else 'FAIL'}")
        if cov["missing"]:
            print(f"  Uncovered (no probe yet): {', '.join(cov['missing'])}")
        print(f"  Excluded — LM-only ({len(NON_DETERMINISTIC_RULES)}): "
              f"{', '.join(sorted(NON_DETERMINISTIC_RULES))}")
        print(f"  Excluded — no function surface ({len(NO_FUNCTION_SURFACE_RULES)}): "
              f"{', '.join(sorted(NO_FUNCTION_SURFACE_RULES))}")
        print(f"Version: consumer={skew['consumer_version']} oracle={skew['oracle_version']} "
              f"-> {'SKEW' if skew['skew'] else 'OK'}")
    return 0 if (cov["passed"] and not skew["skew"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
