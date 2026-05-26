"""
GREAT Allocation — Pipeline Modules.

Financial layer: assigns JUs to societes, calculates K€, handles
split allocation, bulk assignment, and TC cost type popup.
"""
from __future__ import annotations

import logging
from typing import Optional

from great_dspy.modules.base import Module
from great_dspy.specs.pre_estimation_specs import LineStatus, Role
from great_dspy.specs.allocation_specs import (
    ALLOCATION_PERMISSIONS,
    ALLOCATION_ELIGIBLE_STATUSES,
    AVAILABLE_SOCIETES,
    FTE_RATES,
    TSA_RATES,
    calculate_fte_ke,
    calculate_tsa_ke,
    distribute_tc_ke,
    apply_split,
    route_hproject_hnp,
    METIER_ALLOCATION_CONFIG,
    SplitAllocation,
)

logger = logging.getLogger(__name__)


class AllocationPermissionChecker(Module):
    """Check if role can view/edit/save in Allocation (§2)."""

    def forward(self, role: str) -> dict:
        try:
            role_enum = Role(role)
        except ValueError:
            return {"can_view": False, "can_edit": False, "can_save": False,
                    "reason": f"Unknown role: {role}"}

        perm = ALLOCATION_PERMISSIONS.get(role_enum)
        if not perm or not perm.can_view:
            return {"can_view": False, "can_edit": False, "can_save": False,
                    "reason": f"{role} has no access to Allocation"}

        return {
            "can_view": True,
            "can_edit": perm.can_edit,
            "can_save": perm.can_save,
            "reason": f"{role} {'can' if perm.can_edit else 'cannot'} edit in Allocation",
        }


class AllocationEligibilityFilter(Module):
    """Filter job units to only Approved (PL, Métier) pairs (§3)."""

    def forward(self, job_units: list[dict]) -> list[dict]:
        return [
            ju for ju in job_units
            if ju.get("status") == "approved"
        ]


class AllocationRuleMatcher(Module):
    """
    Match job units to societes using allocation rules (§4).

    Pure Python: case-insensitive CONTAINS matching.
    Empty field = wildcard. Most specific wins.
    Exception rules take unconditional priority.
    """

    def __init__(self, rules: Optional[list[dict]] = None, lm=None):
        super().__init__(lm)
        self.rules = rules or []

    def set_rules(self, rules: list[dict]):
        self.rules = rules

    def _score_rule(self, rule: dict, ju: dict) -> int:
        """Count non-empty rule fields that match the JU."""
        score = 0
        for field, match_value in rule.get("fields", {}).items():
            if not match_value:  # Empty = wildcard
                continue
            ju_value = str(ju.get(field, "")).lower()
            if match_value.lower() in ju_value:
                score += 1
            else:
                return 0  # Field doesn't match → rule doesn't apply
        return score

    def _find_best_rule(self, ju: dict) -> Optional[dict]:
        """Find the best matching rule for a job unit."""
        # First pass: check exception rules
        for rule in self.rules:
            if rule.get("exception") and self._score_rule(rule, ju) > 0:
                return rule

        # Second pass: score all non-exception rules
        best_rule = None
        best_score = 0

        for rule in self.rules:
            if rule.get("exception"):
                continue
            score = self._score_rule(rule, ju)
            if score > best_score:
                best_score = score
                best_rule = rule
            elif score == best_score and score > 0:
                # Tie: last rule in the file wins (already in order)
                best_rule = rule

        return best_rule

    def forward(self, job_units: list[dict]) -> list[dict]:
        """
        Assign societe and cost type to JUs with no existing assignment.
        Skips JUs that already have a societe (§4.1).
        """
        results = []
        for ju in job_units:
            if ju.get("societe"):
                results.append(ju)
                continue

            rule = self._find_best_rule(ju)
            if rule:
                ju["societe"] = rule.get("societe", "")
                ju["cost_type"] = rule.get("cost_type", "FTE")
                ju["_rule_matched"] = rule.get("id", "unknown")

            results.append(ju)

        return results


class HProjectRouter(Module):
    """Apply H-PROJECT/H-NP extra routing after Excel rules (§4.5)."""

    def forward(self, job_units: list[dict]) -> list[dict]:
        results = []
        for ju in job_units:
            metier = ju.get("metier", "")
            if metier not in ("H-PROJECT", "H-NP"):
                results.append(ju)
                continue

            routed = route_hproject_hnp(
                standard_emissions=ju.get("standard_emissions", ""),
                organ_type=ju.get("organ_type", ""),
                alliance_code=ju.get("alliance_code", ""),
            )

            if routed:
                ju["societe"] = routed
                ju["_routed_by"] = "hproject_extra"

            results.append(ju)

        return results


class KECalculator(Module):
    """Calculate K€ from FTE per year using rate tables (§11)."""

    def calculate_for_ju(self, ju: dict) -> dict:
        """Calculate K€ for a single job unit."""
        cost_type = ju.get("cost_type", "FTE")
        societe = ju.get("societe", "")
        yearly_fte = ju.get("fte_yearly", {})

        ke_yearly = {}

        if cost_type == "FTE":
            for year, fte in yearly_fte.items():
                ke_yearly[year] = calculate_fte_ke(fte, societe, str(year))
        elif cost_type == "TSA":
            for year, fte in yearly_fte.items():
                ke_yearly[year] = calculate_tsa_ke(fte, societe, str(year))
        # TC: handled via popup, not here

        return ke_yearly

    def forward(self, job_units: list[dict]) -> list[dict]:
        results = []
        for ju in job_units:
            if ju.get("cost_type") == "TC":
                ke_yearly = ju.get("ke_yearly", {})
            else:
                ke_yearly = self.calculate_for_ju(ju)

            ju["ke_yearly"] = ke_yearly
            ju["total_ke"] = sum(ke_yearly.values())
            results.append(ju)

        return results


class TCPopupHandler(Module):
    """Handle TC cost type K€ input popup (§8)."""

    def distribute_ke(self, total_ke: float, fte_yearly: dict[str, float],
                      overrides: Optional[dict[str, float]] = None) -> dict:
        """
        Distribute total K€ proportionally to FTE share, with per-year overrides.

        Args:
            total_ke: Total K€ entered by RCRC
            fte_yearly: {"2024": 0.5, "2025": 0.3, ...}
            overrides: Optional per-year overrides {"2024": 30.0}

        Returns:
            {"2024": 33.33, "2025": 20.0, ...}
        """
        distributed = distribute_tc_ke(total_ke, fte_yearly)
        if overrides:
            for year, val in overrides.items():
                distributed[year] = val
        return distributed

    def forward(self, job_unit: dict, total_ke: float,
                overrides: Optional[dict[str, float]] = None) -> dict:
        ke_yearly = self.distribute_ke(
            total_ke,
            job_unit.get("fte_yearly", {}),
            overrides,
        )
        return {
            "ke_yearly": ke_yearly,
            "total_ke": sum(ke_yearly.values()),
            "cost_type": "TC",
        }


class SplitAllocationHandler(Module):
    """Handle split allocation across N societes (§10)."""

    def forward(self, ju: dict, splits: list[dict]) -> list[dict]:
        """
        Split a JU's FTE across N societes.

        Args:
            ju: Original job unit dict
            splits: [{"societe": "X", "percentage": 60}, ...]

        Returns:
            List of child JUs with proportional FTE/K€
        """
        fte_yearly = ju.get("fte_yearly", {})

        try:
            split_results = apply_split(fte_yearly, splits)
        except ValueError as e:
            return [{"error": str(e)}]

        child_rows = []
        for split in split_results:
            child = dict(ju)
            child["societe"] = split["societe"]
            child["fte_yearly"] = split["fte_yearly"]
            child["split_pct"] = split["percentage"]
            child["_parent_ju_id"] = ju.get("ju_id", "")
            child["_is_split_child"] = True
            child_rows.append(child)

        return child_rows


class BulkAssigner(Module):
    """Bulk societe assignment (§9)."""

    def forward(self, rows: list[dict], societe: str) -> list[dict]:
        """
        Apply one societe to multiple rows. Always overwrites existing.

        Args:
            rows: List of rows to update
            societe: Target societe name

        Returns:
            Updated rows with new societe
        """
        results = []
        for row in rows:
            row["societe"] = societe
            row["_bulk_assigned"] = True
            row["_dirty"] = True
            results.append(row)
        return results


class AllocationSaveValidator(Module):
    """Validate pre-save conditions (§5.5, §13)."""

    def forward(self, job_units: list[dict]) -> dict:
        errors = []
        warnings = []

        for ju in job_units:
            cost_type = ju.get("cost_type", "FTE")
            societe = ju.get("societe", "")

            # TSA/TC without societe blocks save (ALLOC-BR-06, ALLOC-BR-13)
            if cost_type in ("TSA", "TC") and not societe:
                ju_code = ju.get("ju_code", "unknown")
                errors.append(f"{cost_type} row {ju_code}: societe is mandatory")

            # FTE without societe = non-blocking warning (ALLOC-BR-07)
            if cost_type == "FTE" and not societe:
                ju_code = ju.get("ju_code", "unknown")
                warnings.append(f"FTE row {ju_code}: no societe assigned (non-blocking)")

        return {
            "can_save": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }


class DiversityDropdownHandler(Module):
    """Handle diversity dropdown for H-DESIGN, H-TESTING, H-CUSTOMER (§7)."""

    def has_diversity(self, ju: dict) -> bool:
        """Check if a JU requires diversity selection."""
        ju_code = ju.get("ju_code", "")
        rule_ju_list = ju.get("_rule_ju_list", [])
        return ju_code in rule_ju_list

    def forward(self, job_units: list[dict]) -> list[dict]:
        results = []
        for ju in job_units:
            metier = ju.get("metier", "")
            config = METIER_ALLOCATION_CONFIG.get(metier, {})

            if config.get("has_diversity_dropdown") and self.has_diversity(ju):
                if not ju.get("diversity_resolved"):
                    ju["_needs_diversity"] = True
                    ju["diversity_resolved"] = False

            results.append(ju)

        return results