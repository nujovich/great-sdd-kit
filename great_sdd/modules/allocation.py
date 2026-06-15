"""
GREAT Allocation — Signature-Driven Pipeline Modules.

Financial layer: assigns JUs to societes, calculates K€, handles
split allocation, bulk assignment, and TC cost type popup.

Each module inherits from SignatureModule and honors a Signature contract
from signatures/allocation.py. The forward() method is handled by
SignatureModule (input/output validation), while forward_impl() contains
the actual business logic.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from great_sdd.modules.base import LMClient
from great_sdd.modules.signature_module import SignatureModule
from great_sdd.specs.pre_estimation_specs import LineStatus, Role
from great_sdd.specs.allocation_specs import (
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
    resolve_ju_metier,
    validate_ju_metier_routing,
    TESTING_UNIT_TYPES,
    TESTING_METIER,
)
from great_sdd.signatures.allocation import (
    CHECK_ALLOCATION_PERMISSION,
    FILTER_APPROVED_JUS,
    MATCH_ALLOCATION_RULES,
    ROUTE_HPROJECT_HNP,
    CALCULATE_KE,
    HANDLE_TC_POPUP,
    HANDLE_SPLIT,
    BULK_ASSIGN,
    VALIDATE_ALLOCATION_SAVE,
    CHECK_DROPDOWN_DIVERSITY,
)

logger = logging.getLogger(__name__)


class AllocationPermissionChecker(SignatureModule):
    """Check if role can view/edit/save in Allocation (§2).
    Signature: CHECK_ALLOCATION_PERMISSION
    """

    signature = CHECK_ALLOCATION_PERMISSION

    def forward_impl(self, role: str) -> dict:
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


class AllocationEligibilityFilter(SignatureModule):
    """Filter job units to only Approved (PL, Métier) pairs (§3).
    Signature: FILTER_APPROVED_JUS
    """

    signature = FILTER_APPROVED_JUS

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        approved = [ju for ju in job_units if ju.get("status") == "approved"]
        excluded = len(job_units) - len(approved)

        return {
            "approved_jus_json": json.dumps(approved),
            "excluded_count": str(excluded),
        }


class AllocationRuleMatcher(SignatureModule):
    """Match job units to societes using allocation rules (§4).
    Signature: MATCH_ALLOCATION_RULES

    Pure Python: case-insensitive CONTAINS matching.
    Empty field = wildcard. Most specific wins.
    Exception rules take unconditional priority.
    Skips JUs that already have a societe (ALLOC-BR-02).
    """

    signature = MATCH_ALLOCATION_RULES

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
                return 0  # Field doesn't match -> rule doesn't apply
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

    def forward_impl(self, job_units_json: str, rules_json: str = "[]") -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        try:
            rules = json.loads(rules_json) if isinstance(rules_json, str) else rules_json
        except (json.JSONDecodeError, TypeError):
            rules = []

        self.rules = rules
        results = []
        unassigned = 0

        for ju in job_units:
            if ju.get("societe"):
                # ALLOC-BR-02: Skip JUs that already have a societe
                results.append(ju)
                continue

            rule = self._find_best_rule(ju)
            if rule:
                ju["societe"] = rule.get("societe", "")
                ju["cost_type"] = rule.get("cost_type", "FTE")
                ju["_rule_matched"] = rule.get("id", "unknown")
            else:
                unassigned += 1

            results.append(ju)

        return {
            "assigned_jus_json": json.dumps(results),
            "unassigned_count": str(unassigned),
        }


class HProjectRouter(SignatureModule):
    """Apply H-PROJECT/H-NP extra routing after Excel rules (§4.5).
    Signature: ROUTE_HPROJECT_HNP
    """

    signature = ROUTE_HPROJECT_HNP

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        results = []
        routed = 0

        for ju in job_units:
            metier = ju.get("metier", "")
            if metier not in ("H-PROJECT", "H-NP"):
                results.append(ju)
                continue

            routed_societe = route_hproject_hnp(
                standard_emissions=ju.get("standard_emissions", ""),
                organ_type=ju.get("organ_type", ""),
                alliance_code=ju.get("alliance_code", ""),
            )

            if routed_societe:
                ju["societe"] = routed_societe
                ju["_routed_by"] = "hproject_extra"
                routed += 1

            results.append(ju)

        return {
            "routed_jus_json": json.dumps(results),
            "routed_count": str(routed),
        }


class KECalculator(SignatureModule):
    """Calculate K€ from FTE per year using rate tables (§11).
    Signature: CALCULATE_KE
    """

    signature = CALCULATE_KE

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

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        results = []
        for ju in job_units:
            if ju.get("cost_type") == "TC":
                ke_yearly = ju.get("ke_yearly", {})
            else:
                ke_yearly = self.calculate_for_ju(ju)

            ju["ke_yearly"] = ke_yearly
            ju["total_ke"] = sum(ke_yearly.values())
            results.append(ju)

        return {"calculated_jus_json": json.dumps(results)}


class TCPopupHandler(SignatureModule):
    """Handle TC cost type K€ input popup (§8).
    Signature: HANDLE_TC_POPUP
    """

    signature = HANDLE_TC_POPUP

    def distribute_ke(self, total_ke: float, fte_yearly: dict[str, float],
                      overrides: Optional[dict[str, float]] = None) -> dict:
        """Distribute total K€ proportionally to FTE share, with per-year overrides."""
        distributed = distribute_tc_ke(total_ke, fte_yearly)
        if overrides:
            for year, val in overrides.items():
                distributed[year] = val
        return distributed

    def forward_impl(self, job_unit_json: str, total_ke: float,
                     overrides_json: str = "{}") -> dict:
        try:
            job_unit = json.loads(job_unit_json) if isinstance(job_unit_json, str) else job_unit_json
        except (json.JSONDecodeError, TypeError):
            job_unit = {}

        try:
            overrides = json.loads(overrides_json) if isinstance(overrides_json, str) else overrides_json
        except (json.JSONDecodeError, TypeError):
            overrides = {}

        ke_yearly = self.distribute_ke(
            total_ke,
            job_unit.get("fte_yearly", {}),
            overrides if overrides else None,
        )
        return {
            "ke_yearly_json": json.dumps(ke_yearly),
            "total_ke": round(sum(ke_yearly.values()), 2),
            "cost_type": "TC",
        }


class SplitAllocationHandler(SignatureModule):
    """Handle split allocation across N societes (§10).
    Signature: HANDLE_SPLIT
    """

    signature = HANDLE_SPLIT

    def forward_impl(self, ju_json: str, splits_json: str) -> dict:
        try:
            ju = json.loads(ju_json) if isinstance(ju_json, str) else ju_json
        except (json.JSONDecodeError, TypeError):
            ju = {}

        try:
            splits = json.loads(splits_json) if isinstance(splits_json, str) else splits_json
        except (json.JSONDecodeError, TypeError):
            splits = []

        fte_yearly = ju.get("fte_yearly", {})

        try:
            split_results = apply_split(fte_yearly, splits)
        except ValueError as e:
            return {"child_jus_json": "[]", "error": str(e)}

        child_rows = []
        for split in split_results:
            child = dict(ju)
            child["societe"] = split["societe"]
            child["fte_yearly"] = split["fte_yearly"]
            child["split_pct"] = split["percentage"]
            child["_parent_ju_id"] = ju.get("ju_id", "")
            child["_is_split_child"] = True
            child_rows.append(child)

        return {"child_jus_json": json.dumps(child_rows), "error": ""}


class BulkAssigner(SignatureModule):
    """Bulk societe assignment (§9).
    Signature: BULK_ASSIGN
    """

    signature = BULK_ASSIGN

    def forward_impl(self, rows_json: str, societe: str) -> dict:
        try:
            rows = json.loads(rows_json) if isinstance(rows_json, str) else rows_json
        except (json.JSONDecodeError, TypeError):
            rows = []

        results = []
        for row in rows:
            row["societe"] = societe
            row["_bulk_assigned"] = True
            row["_dirty"] = True
            results.append(row)

        return {
            "updated_rows_json": json.dumps(results),
            "assigned_count": str(len(results)),
        }


class AllocationSaveValidator(SignatureModule):
    """Validate pre-save conditions (§5.5, §13).
    Signature: VALIDATE_ALLOCATION_SAVE
    """

    signature = VALIDATE_ALLOCATION_SAVE

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

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
            "errors_json": json.dumps(errors),
            "warnings_json": json.dumps(warnings),
        }


# DEPRECATED: HIW-176 — diversity dropdown removed from Allocation view
class DiversityDropdownHandler(SignatureModule):
    """Handle diversity dropdown for H-DESIGN, H-TESTING, H-CUSTOMER (§7).
    Signature: CHECK_DROPDOWN_DIVERSITY
    """

    signature = CHECK_DROPDOWN_DIVERSITY

    def has_diversity(self, ju: dict) -> bool:
        """Check if a JU requires diversity selection."""
        ju_code = ju.get("ju_code", "")
        rule_ju_list = ju.get("_rule_ju_list", [])
        return ju_code in rule_ju_list

    def forward_impl(self, job_units_json: str) -> dict:
        try:
            job_units = json.loads(job_units_json) if isinstance(job_units_json, str) else job_units_json
        except (json.JSONDecodeError, TypeError):
            job_units = []

        results = []
        unresolved = 0
        for ju in job_units:
            metier = ju.get("metier", "")
            config = METIER_ALLOCATION_CONFIG.get(metier, {})

            if config.get("has_diversity_dropdown") and self.has_diversity(ju):
                if not ju.get("diversity_resolved"):
                    ju["_needs_diversity"] = True
                    ju["diversity_resolved"] = False
                    unresolved += 1

            results.append(ju)

        return {
            "flagged_jus_json": json.dumps(results),
            "unresolved_count": str(unresolved),
        }


class JUMetierRouter:
    """
    Resolve and validate JU metier routing (ALLOC-BR-17).

    BH/Kilometres -> H-TESTING
    Man Day/Kiloeuros -> same as project_line.metier

    NOTE: This is a helper class (not a SignatureModule) because it's
    used internally by other modules, not as a pipeline stage.
    """

    def resolve(self, unit_type: str, project_line_metier: str) -> str:
        """Resolve the correct metier for a job unit."""
        return resolve_ju_metier(unit_type, project_line_metier)

    def forward(self, job_units: list[dict], project_lines: dict[str, dict]) -> dict:
        """Validate metier routing for a batch of job units."""
        validation = validate_ju_metier_routing(job_units, project_lines)

        resolved = []
        for ju in job_units:
            pl_id = ju.get("project_line_id", "")
            pl_metier = project_lines.get(pl_id, {}).get("metier", "")
            expected = resolve_ju_metier(ju.get("unit_type", ""), pl_metier)
            ju["_expected_metier"] = expected
            resolved.append(ju)

        return {
            "valid": validation["valid"],
            "errors": validation["errors"],
            "resolved": resolved,
        }
