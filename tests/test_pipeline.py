"""
GREAT Pre-Estimation — Tests.

Tests the pipeline at multiple levels:
  1. Unit: Spec data structures (compatibility, state machine, formulas)
  2. Module: Individual DSPy modules (pure Python parts)
  3. Integration: Full pipeline with LM
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from great_dspy.specs.pre_estimation_specs import (
    LineStatus,
    Role,
    ROLE_PERMISSIONS,
    STATUS_TRANSITIONS,
    LOCKED_STATUSES,
    EDITABLE_STATUSES,
    TERMINAL_STATUSES,
    are_lines_compatible,
    COMPATIBILITY_FIELDS,
    BUSINESS_RULES,
    WORKLOAD_STANDARDS,
    calculate_ju_total,
    calculate_fte,
    distribute_monthly,
    aggregate_yearly,
    MAN_DAY_FTE_DIVISOR,
)
from great_dspy.modules.pre_estimation import (
    SelectionValidator,
    PermissionChecker,
    StatusTransitionValidator,
    EstimationCalculator,
    SaveValidator,
    MonthDistributor,
)


# ═══════════════════════════════════════════════════════════
# 1. Spec Data Structure Tests
# ═══════════════════════════════════════════════════════════

class TestStateMachine:
    """Spec §3: Project Line Status Model"""

    def test_all_statuses_have_transitions(self):
        """Every status except terminal should have at least one valid transition."""
        for status, targets in STATUS_TRANSITIONS.items():
            if status in TERMINAL_STATUSES:
                assert targets == [], f"{status.value} should have no transitions"
            else:
                assert len(targets) > 0, f"{status.value} should have at least one transition"

    def test_todo_can_only_go_to_draft(self):
        """To do -> Draft only"""
        assert STATUS_TRANSITIONS[LineStatus.TODO] == [LineStatus.DRAFT]

    def test_draft_can_go_to_draft_or_estimated(self):
        """Draft -> Draft | Estimated"""
        assert LineStatus.DRAFT in STATUS_TRANSITIONS[LineStatus.DRAFT]
        assert LineStatus.ESTIMATED in STATUS_TRANSITIONS[LineStatus.DRAFT]

    def test_estimated_can_go_to_sent_or_rejected(self):
        """Estimated -> Sent | Rejected"""
        assert LineStatus.SENT in STATUS_TRANSITIONS[LineStatus.ESTIMATED]
        assert LineStatus.REJECTED in STATUS_TRANSITIONS[LineStatus.ESTIMATED]

    def test_sent_can_go_to_approved_or_rejected(self):
        """Sent -> Approved | Rejected"""
        assert LineStatus.APPROVED in STATUS_TRANSITIONS[LineStatus.SENT]
        assert LineStatus.REJECTED in STATUS_TRANSITIONS[LineStatus.SENT]

    def test_rejected_can_go_back_to_draft_or_estimated(self):
        """Rejected -> Draft | Estimated"""
        assert LineStatus.DRAFT in STATUS_TRANSITIONS[LineStatus.REJECTED]
        assert LineStatus.ESTIMATED in STATUS_TRANSITIONS[LineStatus.REJECTED]

    def test_approved_is_terminal(self):
        """Approved: no transitions"""
        assert LineStatus.APPROVED in TERMINAL_STATUSES
        assert STATUS_TRANSITIONS[LineStatus.APPROVED] == []

    def test_locked_statuses_includes_estimated_sent_approved(self):
        """§17 Rule BR-03, BR-04, BR-16"""
        assert LineStatus.ESTIMATED in LOCKED_STATUSES
        assert LineStatus.SENT in LOCKED_STATUSES
        assert LineStatus.APPROVED in LOCKED_STATUSES

    def test_editable_statuses_includes_todo_draft_rejected(self):
        """To do, Draft, and Rejected are editable"""
        assert LineStatus.TODO in EDITABLE_STATUSES
        assert LineStatus.DRAFT in EDITABLE_STATUSES
        assert LineStatus.REJECTED in EDITABLE_STATUSES


class TestRolePermissions:
    """Spec §2: Role Permissions"""

    def test_engineer_can_edit_assigned_only(self):
        """Engineer: full edit, assigned lines only"""
        p = ROLE_PERMISSIONS[Role.ENGINEER]
        assert p.can_view is True
        assert p.can_edit is True
        assert p.scope == "assigned_only"

    def test_admin_can_edit_all(self):
        """Admin: full edit, any line"""
        p = ROLE_PERMISSIONS[Role.ADMIN]
        assert p.can_view is True
        assert p.can_edit is True
        assert p.scope == "all"

    def test_pmo_read_only(self):
        """PMO: read-only"""
        p = ROLE_PERMISSIONS[Role.PMO]
        assert p.can_view is True
        assert p.can_edit is False
        assert p.scope == "all"

    def test_rcrc_read_only(self):
        """RCRC: read-only"""
        p = ROLE_PERMISSIONS[Role.RCRC]
        assert p.can_view is True
        assert p.can_edit is False
        assert p.scope == "all"

    def test_cpo_no_access(self):
        """CPO: no access to Pre-Estimation"""
        p = ROLE_PERMISSIONS[Role.CPO]
        assert p.can_view is False
        assert p.scope == "none"


class TestCompatibilityRules:
    """Spec §5: Multi-line Selection Compatibility"""

    def test_compatible_lines_same_fields(self):
        """Two lines with identical compatibility fields are compatible"""
        lines = [
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
        ]
        assert are_lines_compatible(lines) is True

    def test_incompatible_different_organ_type(self):
        """Different organ types are incompatible"""
        lines = [
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
            {"organ_type": "Electric", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
        ]
        assert are_lines_compatible(lines) is False

    def test_null_vs_null_compatible(self):
        """Both lines with null injection system = compatible"""
        lines = [
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": None},
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": None},
        ]
        assert are_lines_compatible(lines) is True

    def test_null_vs_value_incompatible(self):
        """§5.2: null vs value = incompatible"""
        lines = [
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": None},
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
        ]
        assert are_lines_compatible(lines) is False

    def test_single_line_always_compatible(self):
        """Single line is always compatible"""
        assert are_lines_compatible([{"organ_type": "X"}]) is True

    def test_three_compatible_lines(self):
        """Three lines all matching = compatible"""
        lines = [
            {"organ_type": "A", "energy_fuel_type": "B",
             "project_ranking": "C", "injection_system": "D"},
            {"organ_type": "A", "energy_fuel_type": "B",
             "project_ranking": "C", "injection_system": "D"},
            {"organ_type": "A", "energy_fuel_type": "B",
             "project_ranking": "C", "injection_system": "D"},
        ]
        assert are_lines_compatible(lines) is True


class TestBusinessRules:
    """Spec §17: Business Rules"""

    def test_all_17_rules_defined(self):
        """There should be exactly 17 business rules"""
        assert len(BUSINESS_RULES) == 17

    def test_each_rule_has_unique_id(self):
        """Each rule has a unique BR-XX id"""
        ids = [r["id"] for r in BUSINESS_RULES]
        assert len(ids) == len(set(ids))

    def test_no_deletion_rule_exists(self):
        """BR-01: No deletion rule is present"""
        assert any("No deletion" in r["rule"] for r in BUSINESS_RULES)

    def test_draft_gate_rule_exists(self):
        """BR-02: Draft gate rule is present"""
        assert any("Draft gate" in r["rule"] for r in BUSINESS_RULES)

    def test_sp_date_mandatory_rule(self):
        """BR-08: SP date mandatory"""
        assert any("SP date mandatory" in r["rule"] for r in BUSINESS_RULES)


class TestWorkloadStandards:
    """Spec §6-8: Workload Standards"""

    def test_all_metiers_have_standards(self):
        """Every métier has at least one inductor defined"""
        for metier in ["Backend", "Frontend", "Data", "DevOps", "QA", "Mobile"]:
            assert metier in WORKLOAD_STANDARDS
            assert len(WORKLOAD_STANDARDS[metier]) > 0

    def test_backend_has_api_endpoints(self):
        """Backend has 'API endpoints' inductor"""
        names = [ind.name for ind in WORKLOAD_STANDARDS["Backend"]]
        assert "API endpoints" in names

    def test_each_inductor_has_at_least_one_cran(self):
        """Every inductor has at least one cran variant"""
        for metier, inductors in WORKLOAD_STANDARDS.items():
            for ind in inductors:
                assert len(ind.crans) > 0, f"{metier}/{ind.name} has no crans"

    def test_each_inductor_has_job_units(self):
        """Every inductor has at least one job unit"""
        for metier, inductors in WORKLOAD_STANDARDS.items():
            for ind in inductors:
                assert len(ind.job_units) > 0, f"{metier}/{ind.name} has no JUs"

    def test_cran_coefficients_are_positive(self):
        """All cran coefficients are positive"""
        for metier, inductors in WORKLOAD_STANDARDS.items():
            for ind in inductors:
                for cran in ind.crans:
                    assert cran.variable_coeff > 0, f"{metier}/{ind.name}/{cran.name} variable <= 0"
                    assert cran.fixed_coeff >= 0, f"{metier}/{ind.name}/{cran.name} fixed < 0"


class TestEstimationFormulas:
    """Spec §9: Estimation Calculation"""

    def test_ju_total_formula(self):
        """Total = (Variable × Occurrence) + Fixed"""
        # (2.0 × 5) + 0.5 = 10.5
        assert calculate_ju_total(2.0, 5, 0.5) == 10.5

    def test_zero_occurrence(self):
        """§17 BR-13: Zero occurrence is allowed and produces zero"""
        assert calculate_ju_total(2.0, 0, 0.5) == 0.5  # Only fixed

    def test_fte_calculation(self):
        """FTE = Total MD / 209"""
        assert calculate_fte(209.0) == 1.0
        assert calculate_fte(418.0) == 2.0
        assert calculate_fte(104.5) == 0.5

    def test_monthly_distribution(self):
        """Total distributed evenly across months"""
        dist = distribute_monthly(120.0, "2026-01-01", 12)
        assert len(dist) == 12
        assert sum(dist) == pytest.approx(120.0)
        assert all(d == 10.0 for d in dist)


# ═══════════════════════════════════════════════════════════
# 2. Module Unit Tests (Pure Python parts)
# ═══════════════════════════════════════════════════════════

class TestSelectionValidatorModule:
    """Tests for the SelectionValidator module (Python path)"""

    def test_compatible_selection(self):
        validator = SelectionValidator()
        result = validator.forward([
            {"organ_type": "A", "energy_fuel_type": "B",
             "project_ranking": "C", "injection_system": "D"},
            {"organ_type": "A", "energy_fuel_type": "B",
             "project_ranking": "C", "injection_system": "D"},
        ])
        assert result["is_compatible"] is True

    def test_incompatible_selection(self):
        validator = SelectionValidator()
        result = validator.forward([
            {"organ_type": "A", "energy_fuel_type": "B",
             "project_ranking": "C", "injection_system": "D"},
            {"organ_type": "X", "energy_fuel_type": "B",
             "project_ranking": "C", "injection_system": "D"},
        ])
        assert result["is_compatible"] is False
        assert len(result["incompatibility_reason"]) > 0


class TestPermissionCheckerModule:
    """Tests for the PermissionChecker module (Python path)"""

    def setup_method(self):
        self.checker = PermissionChecker()

    def test_engineer_can_edit_own_line(self):
        result = self.checker.forward("Engineer", "Ana Martinez", "Ana Martinez", "edit")
        assert result["allowed"] is True

    def test_engineer_cannot_edit_others_line(self):
        result = self.checker.forward("Engineer", "Ana Martinez", "Carlos Ruiz", "edit")
        assert result["allowed"] is False
        assert "assigned" in result["reason"].lower()

    def test_admin_can_edit_any_line(self):
        result = self.checker.forward("Admin", "Ana Martinez", "Admin", "edit")
        assert result["allowed"] is True

    def test_pmo_cannot_edit(self):
        result = self.checker.forward("PMO", "Ana Martinez", "Laura Gomez", "edit")
        assert result["allowed"] is False
        assert "read-only" in result["reason"].lower()

    def test_pmo_can_view(self):
        result = self.checker.forward("PMO", "Ana Martinez", "Laura Gomez", "view")
        assert result["allowed"] is True

    def test_cpo_no_access(self):
        result = self.checker.forward("CPO", "Ana Martinez", "CPO User", "view")
        assert result["allowed"] is False
        assert "no access" in result["reason"].lower()

    def test_invalid_role(self):
        result = self.checker.forward("InvalidRole", "", "", "view")
        assert result["allowed"] is False


class TestStatusTransitionValidatorModule:
    """Tests for the StatusTransitionValidator module (Python path)"""

    def setup_method(self):
        self.validator = StatusTransitionValidator()

    def test_todo_to_draft_valid(self):
        result = self.validator.forward("to_do", "draft")
        assert result["is_valid"] is True

    def test_todo_to_estimated_invalid_no_draft_gate(self):
        """Cannot skip Draft gate — To do can only go to Draft (state machine)"""
        result = self.validator.forward("to_do", "estimated", has_saved_draft_in_session=False)
        assert result["is_valid"] is False
        # to_do can only transition to draft — this hits STATUS_TRANSITIONS first
        assert "Cannot transition" in result["error_message"]

    def test_draft_to_estimated_with_draft_gate(self):
        result = self.validator.forward("draft", "estimated", has_saved_draft_in_session=True)
        assert result["is_valid"] is True

    def test_draft_to_estimated_without_draft_gate(self):
        """Even if in Draft status, need to save Draft again this session"""
        result = self.validator.forward("draft", "estimated", has_saved_draft_in_session=False)
        assert result["is_valid"] is False

    def test_estimated_to_sent(self):
        result = self.validator.forward("estimated", "sent")
        assert result["is_valid"] is True

    def test_approved_no_transitions(self):
        for status in ["draft", "estimated", "sent", "rejected"]:
            result = self.validator.forward("approved", status)
            assert result["is_valid"] is False

    def test_invalid_status_values(self):
        result = self.validator.forward("invalid", "draft")
        assert result["is_valid"] is False

    def test_rejected_to_draft(self):
        result = self.validator.forward("rejected", "draft")
        assert result["is_valid"] is True


class TestEstimationCalculatorModule:
    """Tests for the EstimationCalculator module (Python path)"""

    def setup_method(self):
        self.calculator = EstimationCalculator()

    def test_simple_calculation(self):
        job_units = [
            {"short_name": "TEST", "variable": 2.0, "occurrence": 5,
             "fixed": 0.5, "unit_type": "man_day", "description": "Test"},
        ]
        result = self.calculator.forward(job_units)
        expected_md = (2.0 * 5) + 0.5  # = 10.5
        assert result["total_man_days"] == expected_md
        # FTE rounded to 2 decimal places
        assert result["total_fte"] == round(expected_md / 209, 2)

    def test_multiple_job_units(self):
        job_units = [
            {"short_name": "JU1", "variable": 2.0, "occurrence": 5, "fixed": 0.5, "unit_type": "man_day", "description": "A"},
            {"short_name": "JU2", "variable": 1.0, "occurrence": 3, "fixed": 0.0, "unit_type": "man_day", "description": "B"},
        ]
        result = self.calculator.forward(job_units)
        expected = ((2.0 * 5) + 0.5) + ((1.0 * 3) + 0.0)  # 10.5 + 3.0 = 13.5
        assert result["total_man_days"] == expected

    def test_bench_hours_unit_type(self):
        job_units = [
            {"short_name": "BH1", "variable": 10.0, "occurrence": 8, "fixed": 2.0, "unit_type": "bench_hours", "description": "BH Test"},
        ]
        result = self.calculator.forward(job_units)
        assert result["total_bh"] == (10.0 * 8) + 2.0
        assert result["total_man_days"] == 0.0  # BH doesn't add to man_days

    def test_empty_job_units(self):
        result = self.calculator.forward([])
        assert result["total_fte"] == 0.0
        assert result["total_bh"] == 0.0
        assert result["total_km"] == 0.0


class TestSaveValidatorModule:
    """Tests for the SaveValidator module (Python path)"""

    def setup_method(self):
        self.validator = SaveValidator()

    def test_valid_draft_save(self):
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": "Simple", "job_units": []}],
        }
        result = self.validator.forward(line, "draft")
        assert result["can_save"] is True
        assert len(result["validation_errors"]) == 0

    def test_missing_sp_date_blocks_save(self):
        """BR-08: SP date mandatory"""
        line = {
            "status": "to_do",
            "sp_date": None,
            "inductors": [{"name": "API", "selected_cran": "Simple"}],
        }
        result = self.validator.forward(line, "draft")
        assert result["can_save"] is False
        assert any("SP date" in e for e in result["validation_errors"])

    def test_no_inductors_with_cran_no_custom(self):
        """At least one inductor with cran or Custom JUs"""
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": None}],
        }
        result = self.validator.forward(line, "draft")
        assert result["can_save"] is False

    def test_custom_jus_unblocked(self):
        """BR-11: Custom JUs allow saving without standard inductors"""
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "Custom", "is_custom": True, "selected_cran": None}],
        }
        result = self.validator.forward(line, "draft")
        assert result["can_save"] is True

    def test_todo_to_draft_valid_transition(self):
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": "Simple"}],
        }
        result = self.validator.forward(line, "draft")
        assert result["can_save"] is True

    def test_todo_to_definitive_blocked_by_draft_gate(self):
        """BR-02: Draft gate blocks definitive without draft first"""
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": "Simple"}],
        }
        result = self.validator.forward(line, "definitive", has_saved_draft_in_session=False)
        assert result["can_save"] is False


# ═══════════════════════════════════════════════════════════
# 3. Full Pipeline Tests (require LM)
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """Integration tests. Skipped if no LM is configured."""

    def test_pipeline_imports(self):
        """Pipeline can be imported without errors"""
        from great_dspy.pipeline.pre_estimation_pipeline import PreEstimationPipeline
        assert PreEstimationPipeline is not None

    def test_pipeline_can_be_instantiated(self):
        """Pipeline can be instantiated"""
        from great_dspy.pipeline.pre_estimation_pipeline import PreEstimationPipeline
        pipeline = PreEstimationPipeline()
        assert pipeline is not None


# ═══════════════════════════════════════════════════════════
# 4. Integration: Specs Consistency
# ═══════════════════════════════════════════════════════════

class TestSpecsConsistency:
    """Cross-cutting consistency checks on the spec data"""

    def test_all_roles_in_permissions(self):
        """Every defined Role has a permission entry"""
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"{role} missing from ROLE_PERMISSIONS"

    def test_valid_statuses_are_enum_members(self):
        """All statuses in STATUS_TRANSITIONS are valid enum members"""
        for status in STATUS_TRANSITIONS:
            assert isinstance(status, LineStatus)
        for targets in STATUS_TRANSITIONS.values():
            for t in targets:
                assert isinstance(t, LineStatus)

    def test_compatibility_fields_are_valid(self):
        """COMPATIBILITY_FIELDS should have exactly 4 fields"""
        assert len(COMPATIBILITY_FIELDS) == 4

    def test_locked_and_editable_disjoint(self):
        """A status cannot be both locked and editable"""
        assert LOCKED_STATUSES.isdisjoint(EDITABLE_STATUSES)

    def test_man_day_divisor_is_reasonable(self):
        """209 working days per year is ~52 weeks × 5 days - holidays"""
        assert MAN_DAY_FTE_DIVISOR == 209