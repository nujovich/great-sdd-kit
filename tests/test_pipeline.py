"""
GREAT Pre-Estimation — Tests (Signature-Driven).

Tests at multiple levels:
  1. Unit: Spec data structures (compatibility, state machine, formulas)
  2. Module: Individual SignatureModules (contract validation + logic)
  3. Integration: Full pipeline with Signature contract enforcement

NOTE: Modules now accept JSON strings in forward() to match their Signature
contracts. This is the contract: inputs are serialized, outputs are serialized.
The pipeline handles the serialization/deserialization.
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from great_sdd.specs.pre_estimation_specs import (
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
from great_sdd.modules.pre_estimation import (
    SelectionValidator,
    PermissionChecker,
    StatusTransitionValidator,
    EstimationCalculator,
    SaveValidator,
    MonthDistributor,
)
from great_sdd.modules.signature_module import SignatureModule, SignatureContractError
from great_sdd.signatures.pre_estimation import (
    VALIDATE_LINE_SELECTION,
    CHECK_ROLE_PERMISSION,
    VALIDATE_STATUS_TRANSITION,
    GENERATE_ESTIMATE,
    VALIDATE_BEFORE_SAVE,
)


# ═══════════════════════════════════════════════════════════
# 1. Spec Data Structure Tests (unchanged)
# ═══════════════════════════════════════════════════════════

class TestStateMachine:
    """Spec §3: Project Line Status Model"""

    def test_all_statuses_have_transitions(self):
        for status, targets in STATUS_TRANSITIONS.items():
            if status in TERMINAL_STATUSES:
                assert targets == [], f"{status.value} should have no transitions"
            else:
                assert len(targets) > 0, f"{status.value} should have at least one transition"

    def test_todo_can_only_go_to_draft(self):
        assert STATUS_TRANSITIONS[LineStatus.TODO] == [LineStatus.DRAFT]

    def test_draft_can_go_to_draft_or_estimated(self):
        assert LineStatus.DRAFT in STATUS_TRANSITIONS[LineStatus.DRAFT]
        assert LineStatus.ESTIMATED in STATUS_TRANSITIONS[LineStatus.DRAFT]

    def test_estimated_can_go_to_sent_or_modification_requested(self):
        assert LineStatus.SENT in STATUS_TRANSITIONS[LineStatus.ESTIMATED]
        assert LineStatus.MODIFICATION_REQUESTED in STATUS_TRANSITIONS[LineStatus.ESTIMATED]

    def test_sent_can_go_to_approved_or_modification_requested(self):
        assert LineStatus.APPROVED in STATUS_TRANSITIONS[LineStatus.SENT]
        assert LineStatus.MODIFICATION_REQUESTED in STATUS_TRANSITIONS[LineStatus.SENT]

    def test_modification_requested_can_go_back_to_draft_or_estimated(self):
        assert LineStatus.DRAFT in STATUS_TRANSITIONS[LineStatus.MODIFICATION_REQUESTED]
        assert LineStatus.ESTIMATED in STATUS_TRANSITIONS[LineStatus.MODIFICATION_REQUESTED]

    def test_approved_is_terminal(self):
        assert LineStatus.APPROVED in TERMINAL_STATUSES
        assert STATUS_TRANSITIONS[LineStatus.APPROVED] == []

    def test_locked_statuses_includes_estimated_sent_approved(self):
        assert LineStatus.ESTIMATED in LOCKED_STATUSES
        assert LineStatus.SENT in LOCKED_STATUSES
        assert LineStatus.APPROVED in LOCKED_STATUSES

    def test_editable_statuses_includes_todo_draft_modification_requested(self):
        assert LineStatus.TODO in EDITABLE_STATUSES
        assert LineStatus.DRAFT in EDITABLE_STATUSES
        assert LineStatus.MODIFICATION_REQUESTED in EDITABLE_STATUSES


class TestRolePermissions:
    """Spec §2: Role Permissions"""

    def test_engineer_can_edit_assigned_only(self):
        p = ROLE_PERMISSIONS[Role.ENGINEER]
        assert p.can_view is True
        assert p.can_edit is True
        assert p.scope == "assigned_only"

    def test_admin_can_edit_all(self):
        p = ROLE_PERMISSIONS[Role.ADMIN]
        assert p.can_view is True
        assert p.can_edit is True
        assert p.scope == "all"

    def test_pmo_read_only(self):
        p = ROLE_PERMISSIONS[Role.PMO]
        assert p.can_view is True
        assert p.can_edit is False
        assert p.scope == "all"

    def test_rcrc_read_only(self):
        p = ROLE_PERMISSIONS[Role.RCRC]
        assert p.can_view is True
        assert p.can_edit is False
        assert p.scope == "all"

    def test_cpo_no_access(self):
        p = ROLE_PERMISSIONS[Role.CPO]
        assert p.can_view is False
        assert p.scope == "none"


class TestCompatibilityRules:
    """Spec §5: Multi-line Selection Compatibility"""

    def test_compatible_lines_same_fields(self):
        lines = [
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
        ]
        assert are_lines_compatible(lines) is True

    def test_incompatible_different_organ_type(self):
        lines = [
            {"organ_type": "Thermal", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
            {"organ_type": "Electric", "energy_fuel_type": "Gasoline",
             "project_ranking": "Mother", "injection_system": "Direct"},
        ]
        assert are_lines_compatible(lines) is False

    def test_null_vs_null_compatible(self):
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
        assert are_lines_compatible([{"organ_type": "X"}]) is True

    def test_three_compatible_lines(self):
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
    def test_all_20_rules_defined(self):
        """There should be exactly 20 business rules (19 original + BR-20 Custom JU permissions)."""
        assert len(BUSINESS_RULES) == 20

    def test_each_rule_has_unique_id(self):
        ids = [r["id"] for r in BUSINESS_RULES]

    def test_no_deletion_rule_exists(self):
        assert any("No deletion" in r["rule"] for r in BUSINESS_RULES)

    def test_draft_gate_rule_exists(self):
        assert any("Draft gate" in r["rule"] for r in BUSINESS_RULES)

    def test_sp_date_mandatory_rule(self):
        assert any("SP date mandatory" in r["rule"] for r in BUSINESS_RULES)


class TestWorkloadStandards:
    """Spec §6-8: Workload Standards"""

    def test_all_metiers_have_standards(self):
        for metier in ["H-DESIGN", "H-SOFTWARE", "H-TUNING", "H-PROJECT", "H-TESTING", "H-CUSTOMER"]:
            assert metier in WORKLOAD_STANDARDS
            assert len(WORKLOAD_STANDARDS[metier]) > 0

    def test_backend_has_api_endpoints(self):
        names = [ind.name for ind in WORKLOAD_STANDARDS["H-DESIGN"]]
        assert "API endpoints" in names

    def test_each_inductor_has_at_least_one_cran(self):
        for metier, inductors in WORKLOAD_STANDARDS.items():
            for ind in inductors:
                assert len(ind.crans) > 0, f"{metier}/{ind.name} has no crans"

    def test_each_inductor_has_job_units(self):
        for metier, inductors in WORKLOAD_STANDARDS.items():
            for ind in inductors:
                assert len(ind.job_units) > 0, f"{metier}/{ind.name} has no JUs"

    def test_cran_coefficients_are_positive(self):
        for metier, inductors in WORKLOAD_STANDARDS.items():
            for ind in inductors:
                for cran in ind.crans:
                    assert cran.variable_coeff > 0
                    assert cran.fixed_coeff >= 0


class TestEstimationFormulas:
    """Spec §9: Estimation Calculation"""

    def test_ju_total_formula(self):
        assert calculate_ju_total(2.0, 5, 0.5) == 10.5

    def test_zero_occurrence(self):
        assert calculate_ju_total(2.0, 0, 0.5) == 0.5

    def test_fte_calculation(self):
        assert calculate_fte(209.0) == 1.0
        assert calculate_fte(418.0) == 2.0
        assert calculate_fte(104.5) == 0.5

    def test_monthly_distribution(self):
        dist = distribute_monthly(120.0, "2026-01-01", 12)
        assert len(dist) == 12
        assert sum(dist) == pytest.approx(120.0)
        assert all(d == 10.0 for d in dist)


# ═══════════════════════════════════════════════════════════
# 2. Signature Contract Tests (NEW)
# ═══════════════════════════════════════════════════════════

class TestSignatureContracts:
    """Verify that modules honor their Signature contracts."""

    def test_selection_validator_has_signature(self):
        v = SelectionValidator()
        assert v.signature is VALIDATE_LINE_SELECTION
        assert v.signature.name == "ValidateLineSelection"

    def test_permission_checker_has_signature(self):
        c = PermissionChecker()
        assert c.signature is CHECK_ROLE_PERMISSION

    def test_status_validator_has_signature(self):
        s = StatusTransitionValidator()
        assert s.signature is VALIDATE_STATUS_TRANSITION

    def test_estimation_calculator_has_signature(self):
        e = EstimationCalculator()
        assert e.signature is GENERATE_ESTIMATE

    def test_save_validator_has_signature(self):
        s = SaveValidator()
        assert s.signature is VALIDATE_BEFORE_SAVE

    def test_module_describe(self):
        v = SelectionValidator()
        desc = v.describe()
        assert "SelectionValidator" in desc
        assert "ValidateLineSelection" in desc
        assert "lines_json" in desc
        assert "is_compatible" in desc

    def test_contract_error_on_missing_input(self):
        """SignatureModule raises SignatureContractError on missing required input."""
        v = SelectionValidator()
        with pytest.raises(SignatureContractError, match="missing required inputs"):
            v.forward()  # no lines_json

    def test_contract_error_on_missing_input(self):
        """SignatureModule raises SignatureContractError when required input is missing."""
        v = SelectionValidator()
        with pytest.raises(SignatureContractError, match="missing required inputs"):
            v.forward()  # no lines_json at all

    def test_contract_error_on_missing_output(self):
        """SignatureModule raises SignatureContractError if forward_impl returns wrong outputs."""

        class BadModule(SignatureModule):
            signature = VALIDATE_LINE_SELECTION
            def forward_impl(self, lines_json: str) -> dict:
                return {}  # missing is_compatible and incompatibility_reason

        with pytest.raises(SignatureContractError, match="missing output"):
            BadModule().forward(lines_json="[]")


class TestSelectionValidatorSignature:
    """Test SelectionValidator through its Signature contract."""

    def test_compatible_selection(self):
        validator = SelectionValidator()
        result = validator.forward(
            lines_json=json.dumps([
                {"organ_type": "A", "energy_fuel_type": "B",
                 "project_ranking": "C", "injection_system": "D"},
                {"organ_type": "A", "energy_fuel_type": "B",
                 "project_ranking": "C", "injection_system": "D"},
            ])
        )
        assert result["is_compatible"] is True
        assert result["incompatibility_reason"] == ""

    def test_incompatible_selection(self):
        validator = SelectionValidator()
        result = validator.forward(
            lines_json=json.dumps([
                {"organ_type": "A", "energy_fuel_type": "B",
                 "project_ranking": "C", "injection_system": "D"},
                {"organ_type": "X", "energy_fuel_type": "B",
                 "project_ranking": "C", "injection_system": "D"},
            ])
        )
        assert result["is_compatible"] is False
        assert len(result["incompatibility_reason"]) > 0

    def test_output_is_boolean_compatible(self):
        """Output is_coerce is always boolean (signature field_type=boolean)."""
        validator = SelectionValidator()
        result = validator.forward(lines_json=json.dumps([{"a": 1}]))
        assert isinstance(result["is_compatible"], bool)


class TestPermissionCheckerSignature:
    """Test PermissionChecker through its Signature contract."""

    def setup_method(self):
        self.checker = PermissionChecker()

    def test_engineer_can_edit_own_line(self):
        result = self.checker.forward(
            role="Engineer", line_assignee="Ana Martinez",
            current_user="Ana Martinez", action="edit"
        )
        assert result["allowed"] is True

    def test_engineer_cannot_edit_others_line(self):
        result = self.checker.forward(
            role="Engineer", line_assignee="Ana Martinez",
            current_user="Carlos Ruiz", action="edit"
        )
        assert result["allowed"] is False
        assert "assigned" in result["reason"].lower()

    def test_admin_can_edit_any_line(self):
        result = self.checker.forward(
            role="Admin", line_assignee="Ana Martinez",
            current_user="Admin", action="edit"
        )
        assert result["allowed"] is True

    def test_pmo_cannot_edit(self):
        result = self.checker.forward(
            role="PMO", line_assignee="Ana Martinez",
            current_user="Laura Gomez", action="edit"
        )
        assert result["allowed"] is False
        assert "read-only" in result["reason"].lower()

    def test_pmo_can_view(self):
        result = self.checker.forward(
            role="PMO", line_assignee="Ana Martinez",
            current_user="Laura Gomez", action="view"
        )
        assert result["allowed"] is True

    def test_cpo_no_access(self):
        result = self.checker.forward(
            role="CPO", line_assignee="Ana Martinez",
            current_user="CPO User", action="view"
        )
        assert result["allowed"] is False
        assert "no access" in result["reason"].lower()

    def test_invalid_role(self):
        result = self.checker.forward(
            role="InvalidRole", line_assignee="", current_user="", action="view"
        )
        assert result["allowed"] is False

    def test_output_is_boolean_allowed(self):
        result = self.checker.forward(
            role="Admin", line_assignee="X", current_user="Y", action="view"
        )
        assert isinstance(result["allowed"], bool)


class TestStatusTransitionValidatorSignature:
    """Test StatusTransitionValidator through its Signature contract."""

    def setup_method(self):
        self.validator = StatusTransitionValidator()

    def test_todo_to_draft_valid(self):
        result = self.validator.forward(
            current_status="to_do", target_status="draft",
            has_saved_draft_in_session=False
        )
        assert result["is_valid"] is True

    def test_todo_to_estimated_invalid(self):
        result = self.validator.forward(
            current_status="to_do", target_status="estimated",
            has_saved_draft_in_session=False
        )
        assert result["is_valid"] is False

    def test_draft_to_estimated_with_draft_gate(self):
        result = self.validator.forward(
            current_status="draft", target_status="estimated",
            has_saved_draft_in_session=True
        )
        assert result["is_valid"] is True

    def test_draft_to_estimated_without_draft_gate(self):
        result = self.validator.forward(
            current_status="draft", target_status="estimated",
            has_saved_draft_in_session=False
        )
        assert result["is_valid"] is False

    def test_estimated_to_sent(self):
        result = self.validator.forward(
            current_status="estimated", target_status="sent",
            has_saved_draft_in_session=False
        )
        assert result["is_valid"] is True

    def test_approved_no_transitions(self):
        for status in ["draft", "estimated", "sent", "modification_requested"]:
            result = self.validator.forward(
                current_status="approved", target_status=status,
                has_saved_draft_in_session=False
            )
            assert result["is_valid"] is False

    def test_invalid_status_values(self):
        result = self.validator.forward(
            current_status="invalid", target_status="draft",
            has_saved_draft_in_session=False
        )
        assert result["is_valid"] is False

    def test_modification_requested_to_draft(self):
        result = self.validator.forward(
            current_status="modification_requested", target_status="draft",
            has_saved_draft_in_session=False
        )
        assert result["is_valid"] is True

    def test_output_is_boolean_is_valid(self):
        result = self.validator.forward(
            current_status="to_do", target_status="draft",
            has_saved_draft_in_session=False
        )
        assert isinstance(result["is_valid"], bool)


class TestEstimationCalculatorSignature:
    """Test EstimationCalculator through its Signature contract."""

    def setup_method(self):
        self.calculator = EstimationCalculator()

    def test_simple_calculation(self):
        job_units = json.dumps([
            {"short_name": "TEST", "variable": 2.0, "occurrence": 5,
             "fixed": 0.5, "unit_type": "man_day", "description": "Test"},
        ])
        result = self.calculator.forward(job_units_json=job_units)
        expected_md = (2.0 * 5) + 0.5  # = 10.5
        assert float(result["total_fte"]) == round(expected_md / 209, 2)

    def test_multiple_job_units(self):
        job_units = json.dumps([
            {"short_name": "JU1", "variable": 2.0, "occurrence": 5,
             "fixed": 0.5, "unit_type": "man_day", "description": "A"},
            {"short_name": "JU2", "variable": 1.0, "occurrence": 3,
             "fixed": 0.0, "unit_type": "man_day", "description": "B"},
        ])
        result = self.calculator.forward(job_units_json=job_units)

    def test_bench_hours_unit_type(self):
        job_units = json.dumps([
            {"short_name": "BH1", "variable": 10.0, "occurrence": 8,
             "fixed": 2.0, "unit_type": "bench_hours", "description": "BH Test"},
        ])
        result = self.calculator.forward(job_units_json=job_units)
        assert float(result["total_bh"]) == (10.0 * 8) + 2.0

    def test_empty_job_units(self):
        result = self.calculator.forward(job_units_json="[]")
        assert float(result["total_fte"]) == 0.0
        assert float(result["total_bh"]) == 0.0
        assert float(result["total_km"]) == 0.0

    def test_breakdown_is_json_string(self):
        """Output breakdown_json is a JSON string (signature field_type=json coerced to string)."""
        job_units = json.dumps([
            {"short_name": "T", "variable": 1.0, "occurrence": 1,
             "fixed": 0.0, "unit_type": "man_day", "description": "T"},
        ])
        result = self.calculator.forward(job_units_json=job_units)
        assert isinstance(result["breakdown_json"], str)
        parsed = json.loads(result["breakdown_json"])
        assert isinstance(parsed, list)


class TestSaveValidatorSignature:
    """Test SaveValidator through its Signature contract."""

    def setup_method(self):
        self.validator = SaveValidator()

    def test_valid_draft_save(self):
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": "Simple", "job_units": []}],
        }
        result = self.validator.forward(line_json=json.dumps(line), save_type="draft")
        assert result["can_save"] is True

    def test_missing_sp_date_blocks_save(self):
        """BR-08: SP date mandatory"""
        line = {
            "status": "to_do",
            "sp_date": None,
            "inductors": [{"name": "API", "selected_cran": "Simple"}],
        }
        result = self.validator.forward(line_json=json.dumps(line), save_type="draft")
        assert result["can_save"] is False
        errors = json.loads(result["validation_errors_json"])
        assert any("SP date" in e for e in errors)

    def test_no_inductors_with_cran_no_custom(self):
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": None}],
        }
        result = self.validator.forward(line_json=json.dumps(line), save_type="draft")
        assert result["can_save"] is False

    def test_custom_jus_unblocked(self):
        """BR-11: Custom JUs allow saving without standard inductors"""
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "Custom", "is_custom": True, "selected_cran": None}],
        }
        result = self.validator.forward(line_json=json.dumps(line), save_type="draft")
        assert result["can_save"] is True

    def test_todo_to_draft_valid_transition(self):
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": "Simple"}],
        }
        result = self.validator.forward(line_json=json.dumps(line), save_type="draft")
        assert result["can_save"] is True

    def test_todo_to_definitive_blocked_by_draft_gate(self):
        """BR-02: Draft gate blocks definitive without draft first"""
        line = {
            "status": "to_do",
            "sp_date": "2026-01-01",
            "inductors": [{"name": "API", "selected_cran": "Simple"}],
        }
        result = self.validator.forward(
            line_json=json.dumps(line), save_type="definitive",
            has_saved_draft_in_session=False
        )
        assert result["can_save"] is False

    def test_output_can_save_is_boolean(self):
        result = self.validator.forward(
            line_json=json.dumps({"status": "to_do", "sp_date": "2026-01-01",
                                   "inductors": [{"selected_cran": "X"}]}),
            save_type="draft"
        )
        assert isinstance(result["can_save"], bool)

    def test_validation_errors_is_json(self):
        result = self.validator.forward(
            line_json=json.dumps({"status": "to_do", "sp_date": None, "inductors": []}),
            save_type="draft"
        )
        assert isinstance(result["validation_errors_json"], str)


class TestMonthDistributorSignature:
    """Test MonthDistributor through its Signature contract."""

    def setup_method(self):
        self.distributor = MonthDistributor()

    def test_distribution_output_is_json(self):
        result = self.distributor.forward(
            total_fte="120.0", total_bh="0.0", total_km="0.0",
            sp_date="2026-01-01", project_duration_months="12"
        )
        # monthly_distribution_json should be a string containing JSON
        assert isinstance(result["monthly_distribution_json"], str)
        monthly = json.loads(result["monthly_distribution_json"])
        assert len(monthly) == 12

    def test_yearly_aggregation_is_json(self):
        result = self.distributor.forward(
            total_fte="120.0", total_bh="0.0", total_km="0.0",
            sp_date="2026-01-01", project_duration_months="12"
        )
        assert isinstance(result["yearly_aggregation_json"], str)
        yearly = json.loads(result["yearly_aggregation_json"])
        assert isinstance(yearly, dict)


# ═══════════════════════════════════════════════════════════
# Prototype Estimation Tests
# ═══════════════════════════════════════════════════════════

from great_sdd.specs.pre_estimation_specs import (
    PrototypeCategory,
    PrototypeEstimation,
    LineRelationship,
    get_related_line_ids,
    check_hvt_attribute_changed,
    DEFAULT_PROTOTYPE_CATEGORIES,
)


class TestPrototypeCategories:
    """Test PrototypeCategory data structure."""

    def test_default_categories_exist(self):
        """There should be 4 default prototype categories (PRE-01 pending)."""
        assert len(DEFAULT_PROTOTYPE_CATEGORIES) == 4

    def test_categories_have_ids(self):
        """Each category has a unique id."""
        ids = [c.id for c in DEFAULT_PROTOTYPE_CATEGORIES]
        assert len(ids) == len(set(ids))

    def test_categories_have_names(self):
        """Each category has a non-empty name."""
        for cat in DEFAULT_PROTOTYPE_CATEGORIES:
            assert len(cat.name) > 0

    def test_category_names(self):
        """Expected category names per AdminPage fixture."""
        names = [c.name for c in DEFAULT_PROTOTYPE_CATEGORIES]
        assert "Greenfield" in names
        assert "Refactor" in names
        assert "Integration" in names
        assert "Maintenance" in names


class TestPrototypeEstimation:
    """Test PrototypeEstimation data structure."""

    def test_create_empty(self):
        pe = PrototypeEstimation(line_id="PL-001")
        assert pe.line_id == "PL-001"
        assert pe.is_empty() is True
        assert pe.total_units() == 0

    def test_add_quantities(self):
        pe = PrototypeEstimation(
            line_id="PL-001",
            categories={"proto-cat-1": 3.0, "proto-cat-2": 1.0},
        )
        assert pe.total_units() == 4.0
        assert pe.is_empty() is False

    def test_comment_field(self):
        pe = PrototypeEstimation(
            line_id="PL-001",
            categories={"proto-cat-1": 2.0},
            comment="Urgent prototype needed",
        )
        assert pe.comment == "Urgent prototype needed"

    def test_saved_state(self):
        pe = PrototypeEstimation(line_id="PL-001")
        assert pe.saved is False
        pe.saved = True
        assert pe.saved is True

    def test_does_not_affect_fte(self):
        """BR-18: Prototype data is separate from engineering estimation."""
        pe = PrototypeEstimation(
            line_id="PL-001",
            categories={"proto-cat-1": 5.0},
        )
        # Prototype has no FTE/BH/KM fields
        assert not hasattr(pe, "fte")
        assert not hasattr(pe, "bh")
        assert not hasattr(pe, "km")


class TestParentChildRelationships:
    """Test LineRelationship and related functions."""

    def test_relationship_creation(self):
        rel = LineRelationship(parent_line_id="PL-001", child_line_id="PL-002")
        assert rel.parent_line_id == "PL-001"
        assert rel.child_line_id == "PL-002"
        assert rel.relationship_type == "parent_child"

    def test_get_related_ids_parent(self):
        rels = [
            LineRelationship("PL-001", "PL-002"),
            LineRelationship("PL-001", "PL-003"),
        ]
        related = get_related_line_ids("PL-001", rels)
        assert "PL-002" in related
        assert "PL-003" in related

    def test_get_related_ids_child(self):
        """Relationships are bidirectional."""
        rels = [LineRelationship("PL-001", "PL-002")]
        related = get_related_line_ids("PL-002", rels)
        assert "PL-001" in related

    def test_no_related_lines(self):
        rels = [LineRelationship("PL-001", "PL-002")]
        related = get_related_line_ids("PL-999", rels)
        assert len(related) == 0


class TestHVTAttributeChangeDetection:
    """Test check_hvt_attribute_changed function."""

    def test_no_change(self):
        line = {"id": "PL-001", "organ_type": "Thermal", "sp_date": "2026-01-01"}
        original = {"organ_type": "Thermal", "sp_date": "2026-01-01"}
        result = check_hvt_attribute_changed(line, original)
        assert result is None

    def test_organ_type_changed(self):
        line = {"id": "PL-001", "organ_type": "Electric", "sp_date": "2026-01-01"}
        original = {"organ_type": "Thermal", "sp_date": "2026-01-01"}
        result = check_hvt_attribute_changed(line, original)
        assert result is not None
        assert result["changed"] is True
        assert "organ_type" in result["fields"]
        assert result["fields"]["organ_type"]["old"] == "Thermal"
        assert result["fields"]["organ_type"]["new"] == "Electric"

    def test_multiple_fields_changed(self):
        line = {"id": "PL-001", "organ_type": "Electric", "sp_date": "2026-06-01"}
        original = {"organ_type": "Thermal", "sp_date": "2026-01-01"}
        result = check_hvt_attribute_changed(line, original)
        assert result is not None
        assert len(result["fields"]) == 2

    def test_warning_message_includes_line_id(self):
        line = {"id": "PL-001", "organ_type": "Electric"}
        original = {"organ_type": "Thermal"}
        result = check_hvt_attribute_changed(line, original)
        assert "PL-001" in result["message"]

    def test_monitored_fields(self):
        """All 10 HVT monitored fields are checked."""
        line = {"id": "PL-001", "client": "Renault", "market": "EU"}
        original = {"client": "Renault", "market": "EU"}
        result = check_hvt_attribute_changed(line, original)
        assert result is None  # No changes

    def test_client_changed(self):
        line = {"id": "PL-001", "client": "Nissan"}
        original = {"client": "Renault"}
        result = check_hvt_attribute_changed(line, original)
        assert result is not None
        assert "client" in result["fields"]


# ──────────────────────────────────────────────────────
# Custom JU Permissions (BR-20)
# ──────────────────────────────────────────────────────

def test_custom_ju_roles_spec():
    """BR-20: CUSTOM_JU_ROLES mapping is correct."""
    from great_sdd.specs.pre_estimation_specs import CUSTOM_JU_ROLES
    assert CUSTOM_JU_ROLES["Admin"] is True
    assert CUSTOM_JU_ROLES["Engineer"] is True
    assert CUSTOM_JU_ROLES["PMO"] is False
    assert CUSTOM_JU_ROLES["RCRC"] is False
    assert CUSTOM_JU_ROLES["CPO"] is False


def test_can_create_custom_ju_allowed():
    """BR-20: Engineer and Admin can create Custom JUs."""
    from great_sdd.specs.pre_estimation_specs import can_create_custom_ju
    assert can_create_custom_ju("Admin") is True
    assert can_create_custom_ju("Engineer") is True


def test_can_create_custom_ju_denied():
    """BR-20: PMO, RCRC and CPO cannot create Custom JUs."""
    from great_sdd.specs.pre_estimation_specs import can_create_custom_ju
    assert can_create_custom_ju("PMO") is False
    assert can_create_custom_ju("RCRC") is False
    assert can_create_custom_ju("CPO") is False


def test_can_create_custom_ju_unknown():
    """BR-20: Unknown role defaults to False."""
    from great_sdd.specs.pre_estimation_specs import can_create_custom_ju
    assert can_create_custom_ju("UnknownRole") is False


def test_custom_ju_permission_checker():
    """BR-20: CustomJUPermissionChecker module returns correct permissions."""
    from great_sdd.modules.pre_estimation import CustomJUPermissionChecker
    checker = CustomJUPermissionChecker()

    result = checker.forward("Engineer")
    assert result["can_create_custom_ju"] is True
    assert "can" in result["reason"]

    result = checker.forward("Admin")
    assert result["can_create_custom_ju"] is True

    result = checker.forward("PMO")
    assert result["can_create_custom_ju"] is False
    assert "cannot" in result["reason"]

    result = checker.forward("RCRC")
    assert result["can_create_custom_ju"] is False
    assert "cannot" in result["reason"]

    result = checker.forward("CPO")
    assert result["can_create_custom_ju"] is False


def test_business_rules_count_20():
    """BR-20 added: BUSINESS_RULES should now have 20 rules."""
    from great_sdd.specs.pre_estimation_specs import BUSINESS_RULES
    assert len(BUSINESS_RULES) == 20
    assert BUSINESS_RULES[-1]["id"] == "BR-20"


def test_legacy_copy_rules():
    from great_sdd.specs.pre_estimation_specs import merge_legacy_estimation
    current = {
        "j1": {"variable": 4.0, "fixed": 1.0, "inductor_id": "I1"},
        "j2": {"variable": 2.0, "fixed": 0.0, "inductor_id": "I1"},
        "j4": {"variable": 1.0, "fixed": 0.0, "inductor_id": "I1"},
        "j5": {"variable": 3.0, "fixed": 0.0, "inductor_id": "I2"},
    }
    historical = [
        {"ju_id": "j1", "variable": 2.0, "fixed": 0.0, "occurrence": 5.0},  # changed coeffs, total 10
        {"ju_id": "j2", "variable": 2.0, "fixed": 0.0, "occurrence": 3.0},  # unchanged
        {"ju_id": "j3", "variable": 1.0, "fixed": 0.0, "occurrence": 4.0},  # orphan
    ]
    out = merge_legacy_estimation(historical, current)
    occ = {o["ju_id"]: o["occurrence"] for o in out["job_units"]}
    assert occ["j2"] == 3.0                       # rule 1
    assert abs(occ["j1"] - 2.25) < 1e-9           # rule 2: (10-1)/4
    assert occ["j4"] == 0.0                        # rule 4
    assert "j5" not in occ                         # rule 5: new inductor not added
    assert any(c["ju_id"] == "j3" for c in out["custom_jus"])  # rule 3


def test_legacy_copy_rule2_zero_variable_guard():
    from great_sdd.specs.pre_estimation_specs import merge_legacy_estimation
    current = {"jz": {"variable": 0.0, "fixed": 0.0, "inductor_id": "I9"}}
    historical = [{"ju_id": "jz", "variable": 2.0, "fixed": 0.0, "occurrence": 5.0}]
    out = merge_legacy_estimation(historical, current)
    occ = {o["ju_id"]: o["occurrence"] for o in out["job_units"]}
    assert occ["jz"] == 0.0  # current variable 0 -> occurrence 0, no divide-by-zero
