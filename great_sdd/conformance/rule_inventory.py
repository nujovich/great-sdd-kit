r"""Programmatic census of GREAT business rules — the single source of truth.

Scans every great_sdd/specs/*.py module for module-level lists of dicts carrying
an "id" key, deduping across files (e.g. estimation_review re-exports BR-* into
ALL_BUSINESS_RULES). Business rules match r"BR-\d+$"; everything else
(ALLOC-01, ERev-01, ...) is a pending/open-question marker, not a rule.
"""
from __future__ import annotations

import importlib
import pkgutil
import re

import great_sdd.specs as _specs_pkg

_BR_RE = re.compile(r"BR-\d+$")


def _all_rule_dicts() -> dict[str, dict]:
    """Map rule_id -> rule dict, deduped across all spec modules."""
    found: dict[str, dict] = {}
    for mod_info in pkgutil.iter_modules(_specs_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"great_sdd.specs.{mod_info.name}")
        for value in vars(mod).values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        found.setdefault(item["id"], item)
    return found


def all_rule_ids() -> list[str]:
    return sorted(_all_rule_dicts())


def business_rule_ids() -> list[str]:
    return sorted(rid for rid in _all_rule_dicts() if _BR_RE.search(rid))


def pending_marker_ids() -> list[str]:
    return sorted(rid for rid in _all_rule_dicts() if not _BR_RE.search(rid))


def rule_count() -> int:
    return len(business_rule_ids())


def rule_text(rule_id: str) -> str:
    return _all_rule_dicts().get(rule_id, {}).get("rule", "")
