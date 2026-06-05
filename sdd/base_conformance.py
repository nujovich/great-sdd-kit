"""SDD Kit — Conformance Engine (domain-agnostic).

Turns a deterministic spec surface into language-neutral golden fixtures and
verifies consumers against them. NO domain imports. NO network. NO LLM.

The engine has four responsibilities:
  1. Determinism guard  — TripwireLM aborts generation if a covered path hits the LM.
  2. Fixture generation  — Probe + generate_fixtures emit byte-stable golden JSON.
  3. Coverage / skew     — compute_coverage, compute_version_skew.
  4. Consumer runner     — run_conformance exact-matches a consumer against fixtures.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class NonDeterministicError(Exception):
    """Raised when fixture generation hits a non-deterministic path (e.g. the LM)."""


class TripwireLM:
    """Stand-in LM client. Any completion attempt aborts generation loudly."""

    def complete(self, system: str, prompt: str, **kwargs) -> str:
        raise NonDeterministicError(
            "LM call attempted during deterministic fixture generation. "
            "The covered rule depends on a non-deterministic module path. "
            "Refactor it to be deterministic or add it to NON_DETERMINISTIC_RULES."
        )


def canonical_json(obj: Any) -> str:
    """Deterministic, byte-stable JSON: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def normalize_output(result: dict) -> dict:
    """Parse any `*_json` string value into a real JSON value (language-neutral)."""
    out = {}
    for k, v in result.items():
        if k.endswith("_json") and isinstance(v, str):
            try:
                out[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                out[k] = v
        else:
            out[k] = v
    return out


def read_version(repo_root: Path) -> str:
    """Read project version: pyproject.toml first, then package.json. Stdlib-only."""
    repo_root = Path(repo_root)
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', pyproject.read_text(), re.M)
        if m:
            return m.group(1)
    pkg = repo_root / "package.json"
    if pkg.exists():
        data = json.loads(pkg.read_text())
        if "version" in data:
            return str(data["version"])
    raise RuntimeError(f"No version found under {repo_root}")


# ── Fixture generation ──

@dataclass
class Probe:
    """Binds rule_ids to a deterministic fn over representative input cases."""
    rule_ids: list[str]
    name: str
    fn: Callable[[dict], dict]
    cases: list[dict] = field(default_factory=list)


def generate_fixtures(probes: list[Probe], sdd_version: str) -> list[dict]:
    """Run every probe case and emit sorted, normalized fixture entries.

    Raises NonDeterministicError (via TripwireLM inside fn) if a covered path
    is non-deterministic — callers MUST construct domain modules with TripwireLM.
    """
    entries: list[dict] = []
    for probe in probes:
        rule_ids = sorted(probe.rule_ids)
        for case in probe.cases:
            output = normalize_output(probe.fn(case))
            entries.append({
                "rule_ids": rule_ids,
                "input": case,
                "expected_output": output,
                "sdd_version": sdd_version,
            })
    entries.sort(key=lambda e: (e["rule_ids"], canonical_json(e["input"])))
    return entries


def write_fixture_file(path: Path, entries) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(entries))


# ── Coverage / version skew ──

def compute_coverage(all_rule_ids: list[str], covered_rule_ids: list[str],
                     threshold: float) -> dict:
    all_set = set(all_rule_ids)
    covered = all_set & set(covered_rule_ids)
    total = len(all_set)
    coverage = (len(covered) / total) if total else 1.0
    return {
        "total": total,
        "covered_count": len(covered),
        "coverage": coverage,
        "threshold": threshold,
        "passed": coverage >= threshold,
        "missing": sorted(all_set - covered),
        "covered": sorted(covered),
    }


def compute_version_skew(consumer_version: str, oracle_version: str) -> dict:
    return {
        "consumer_version": consumer_version,
        "oracle_version": oracle_version,
        "skew": consumer_version != oracle_version,
    }


# ── Consumer runner ──

def run_conformance(fixtures: list[dict], consumer_fn: Callable[[dict], dict]) -> dict:
    """Run consumer_fn against each fixture; exact-match expected_output."""
    failures = []
    exercised: set[str] = set()
    for fx in fixtures:
        exercised.update(fx["rule_ids"])
        actual = normalize_output(consumer_fn(fx["input"]))
        if actual != fx["expected_output"]:
            failures.append({
                "rule_ids": fx["rule_ids"],
                "input": fx["input"],
                "expected": fx["expected_output"],
                "actual": actual,
            })
    return {
        "total": len(fixtures),
        "failed_count": len(failures),
        "passed": not failures,
        "failures": failures,
        "exercised_rule_ids": sorted(exercised),
    }
