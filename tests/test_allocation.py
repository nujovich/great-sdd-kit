"""
GREAT Allocation — Tests.

Tests cover:
- Spec-level: permissions, eligibility, societes, rates, formulas, rules count
- Module-level: each SignatureModule's forward() with proper kwargs
- Pipeline-level: end-to-end AllocationPipeline.run_allocation()
- Business rules: ALLOC-BR-01 through ALLOC-BR-17
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import json
import pytest

from great_sdd.specs.pre_estimation_specs import LineStatus, Role
from great_sdd.specs.allocation_specs import (
    ALLOCATION_PERMISSIONS, ALLOCATION_ELIGIBLE_STATUSES,
    AVAILABLE_SOCIETES, FTE_RATES, TSA_RATES,
    calculate_fte_ke, calculate_tsa_ke, distribute_tc_ke,
    apply_split, route_hproject_hnp,
    ALLOCATION_RULES_LIST,
    resolve_ju_metier, validate_ju_metier_routing,
)
from great_sdd.modules.allocation import (
    AllocationPermissionChecker, AllocationEligibilityFilter,
    AllocationRuleMatcher, HProjectRouter, KECalculator,
    TCPopupHandler, SplitAllocationHandler, BulkAssigner,
    AllocationSaveValidator, DiversityDropdownHandler,
    JUMetierRouter,
)
from great_sdd.pipeline.allocation_pipeline import run_allocation

# ──────────────────────────────────────────────
# Spec-level tests
# ──────────────────────────────────────────────

def test_permissions():
    p = ALLOCATION_PERMISSIONS
    assert p[Role.ADMIN].can_edit is True
    assert p[Role.PMO].can_edit is True
    assert p[Role.RCRC].can_edit is True
    assert p[Role.ENGINEER].can_view is False
    assert p[Role.CPO].can_view is False

def test_eligibility():
    assert LineStatus.APPROVED in ALLOCATION_ELIGIBLE_STATUSES
    assert len(ALLOCATION_ELIGIBLE_STATUSES) == 1

def test_societes():
    assert len(AVAILABLE_SOCIETES) == 7
    names = [s.name for s in AVAILABLE_SOCIETES]
    assert "Horse Spain S.L." in names

def test_fte_rates():
    assert FTE_RATES["Horse Spain S.L.-Valladolid"]["2024"] == 107

def test_tsa_rates():
    assert TSA_RATES["Ampere/RG"]["2025"] == 155

def test_calculate_fte_ke():
    assert calculate_fte_ke(1.0, "Horse Spain S.L.-Valladolid", "2024") == 107.0
    assert calculate_fte_ke(2.0, "Horse Romania S.A.-Bucarest", "2025") == 158.0  # 2 × 79

def test_calculate_tsa_ke():
    assert calculate_tsa_ke(1.0, "CHENNAI GESC H", "2025") == 54.0

def test_tc_distribution():
    result = distribute_tc_ke(100, {"2024": 1.0, "2025": 1.0})
    assert result["2024"] == 50.0
    assert result["2025"] == 50.0

def test_tc_distribution_uneven():
    result = distribute_tc_ke(150, {"2024": 2.0, "2025": 1.0})
    assert result["2024"] == 100.0
    assert result["2025"] == 50.0

def test_tc_distribution_zero_fte():
    result = distribute_tc_ke(100, {"2024": 0.0, "2025": 0.0})
    assert result["2024"] == 0.0

def test_split_valid():
    result = apply_split({"2024": 1.0}, [
        {"societe": "A", "percentage": 60},
        {"societe": "B", "percentage": 40},
    ])
    assert len(result) == 2
    assert result[0]["societe"] == "A"
    assert result[0]["fte_yearly"]["2024"] == 0.6

def test_split_invalid_total():
    with pytest.raises(ValueError):
        apply_split({"2024": 1.0}, [
            {"societe": "A", "percentage": 50},
            {"societe": "B", "percentage": 30},
        ])

def test_hproject_routing_brasil():
    result = route_hproject_hnp("L83L", "Engine", "XYZ")
    assert result == "Horse Brasil S.A.-CURITIBA"

def test_hproject_routing_valladolid():
    result = route_hproject_hnp("X99", "Boite de vitesse", "DB001")
    assert result == "Horse Spain S.L.-VALLADOLID"

def test_hproject_routing_bucarest():
    result = route_hproject_hnp("X99", "Boite de vitesse", "AC001")
    assert result == "Horse Romania S.A.-BUCAREST"

def test_hproject_no_routing():
    assert route_hproject_hnp("X99", "Engine", "XYZ") == ""

def test_16_rules():
    assert len(ALLOCATION_RULES_LIST) == 17


# ──────────────────────────────────────────────
# Module-level tests (Signature-driven)
# ──────────────────────────────────────────────

def test_permission_checker():
    """CHECK_ALLOCATION_PERMISSION signature"""
    c = AllocationPermissionChecker()
    assert c.forward(role="Admin")["can_view"] is True
    assert c.forward(role="Engineer")["can_view"] is False
    assert c.forward(role="RCRC")["can_edit"] is True
    assert c.forward(role="CPO")["can_view"] is False

def test_eligibility_filter():
    """FILTER_APPROVED_JUS signature — ALLOC-BR-01"""
    f = AllocationEligibilityFilter()
    jus = [
        {"ju_code": "J1", "status": "approved"},
        {"ju_code": "J2", "status": "estimated"},
        {"ju_code": "J3", "status": "approved"},
    ]
    result = f.forward(job_units_json=json.dumps(jus))
    approved = json.loads(result["approved_jus_json"])
    assert len(approved) == 2
    assert all(j["status"] == "approved" for j in approved)
    assert result["excluded_count"] == "1"

def test_rule_matcher_with_empty_rules():
    """MATCH_ALLOCATION_RULES signature — no rules = no assignments"""
    m = AllocationRuleMatcher([])
    jus = [{"ju_code": "J1", "metier": "Backend"}]
    result = m.forward(job_units_json=json.dumps(jus), rules_json="[]")
    assigned = json.loads(result["assigned_jus_json"])
    assert len(assigned) == 1
    assert assigned[0].get("societe") is None

def test_rule_matcher_skips_assigned():
    """MATCH_ALLOCATION_RULES — ALLOC-BR-02: skips JUs with existing societe"""
    m = AllocationRuleMatcher([
        {"fields": {"metier": "Backend"}, "societe": "Horse Spain", "exception": False},
    ])
    jus = [
        {"ju_code": "J1", "metier": "Backend", "societe": "Already Set"},
        {"ju_code": "J2", "metier": "Backend"},
    ]
    result = m.forward(
        job_units_json=json.dumps(jus),
        rules_json=json.dumps([{"fields": {"metier": "Backend"}, "societe": "Horse Spain", "exception": False}]),
    )
    assigned = json.loads(result["assigned_jus_json"])
    assert assigned[0]["societe"] == "Already Set"  # Skipped (ALLOC-BR-02)
    assert assigned[1]["societe"] == "Horse Spain"

def test_ke_calculator():
    """CALCULATE_KE signature — ALLOC-BR-03/04"""
    c = KECalculator()
    jus = [{
        "ju_code": "J1",
        "cost_type": "FTE",
        "societe": "Horse Spain S.L.-Valladolid",
        "fte_yearly": {"2024": 1.0, "2025": 0.5},
    }]
    result = c.forward(job_units_json=json.dumps(jus))
    calculated = json.loads(result["calculated_jus_json"])
    assert calculated[0]["ke_yearly"]["2024"] == 107.0
    assert calculated[0]["ke_yearly"]["2025"] == 53.0  # 0.5 × 106

def test_tc_handler():
    """HANDLE_TC_POPUP signature — ALLOC-BR-13"""
    h = TCPopupHandler()
    result = h.forward(
        job_unit_json=json.dumps({"fte_yearly": {"2024": 2.0, "2025": 1.0}}),
        total_ke=150.0,
    )
    assert result["total_ke"] == "150.0"
    assert result["cost_type"] == "TC"
    ke_yearly = json.loads(result["ke_yearly_json"])
    assert ke_yearly["2024"] == 100.0

def test_save_validator():
    """VALIDATE_ALLOCATION_SAVE — ALLOC-BR-06/07: TSA/TC blocks, FTE warns"""
    v = AllocationSaveValidator()
    jus = [
        {"ju_code": "J1", "cost_type": "FTE", "societe": ""},
        {"ju_code": "J2", "cost_type": "TC", "societe": ""},
    ]
    result = v.forward(job_units_json=json.dumps(jus))
    assert result["can_save"] is False  # TC without societe blocks
    errors = json.loads(result["errors_json"])
    warnings = json.loads(result["warnings_json"])
    assert len(errors) == 1
    assert len(warnings) == 1

def test_save_validator_ok():
    """VALIDATE_ALLOCATION_SAVE — all good"""
    v = AllocationSaveValidator()
    jus = [
        {"ju_code": "J1", "cost_type": "FTE", "societe": "Horse Spain"},
        {"ju_code": "J2", "cost_type": "TC", "societe": "Horse Romania"},
    ]
    result = v.forward(job_units_json=json.dumps(jus))
    assert result["can_save"] is True
    errors = json.loads(result["errors_json"])
    warnings = json.loads(result["warnings_json"])
    assert len(errors) == 0

def test_bulk_assigner():
    """BULK_ASSIGN signature — ALLOC-BR-09/10: overwrite, societe only"""
    b = BulkAssigner()
    rows = [
        {"ju_code": "J1", "societe": ""},
        {"ju_code": "J2", "societe": "Old"},
    ]
    result = b.forward(rows_json=json.dumps(rows), societe="New Societe")
    updated = json.loads(result["updated_rows_json"])
    assert all(r["societe"] == "New Societe" for r in updated)
    assert all(r["_bulk_assigned"] for r in updated)
    assert result["assigned_count"] == "2"

def test_split_handler():
    """HANDLE_SPLIT signature — ALLOC-BR-11: 100% required"""
    s = SplitAllocationHandler()
    ju = {"ju_code": "J1", "fte_yearly": {"2024": 1.0, "2025": 0.5}}
    result = s.forward(
        ju_json=json.dumps(ju),
        splits_json=json.dumps([{"societe": "A", "percentage": 60}, {"societe": "B", "percentage": 40}]),
    )
    assert result["error"] == ""
    children = json.loads(result["child_jus_json"])
    assert len(children) == 2
    assert children[0]["_is_split_child"] is True
    assert children[0]["fte_yearly"]["2024"] == 0.6

def test_split_handler_invalid():
    """HANDLE_SPLIT — percentages must sum to 100%"""
    s = SplitAllocationHandler()
    ju = {"ju_code": "J1", "fte_yearly": {"2024": 1.0}}
    result = s.forward(
        ju_json=json.dumps(ju),
        splits_json=json.dumps([{"societe": "A", "percentage": 50}, {"societe": "B", "percentage": 30}]),
    )
    assert "100%" in result["error"]

def test_diversity_dropdown():
    """CHECK_DROPDOWN_DIVERSITY — ALLOC-BR-08: non-blocking"""
    d = DiversityDropdownHandler()
    jus = [
        {"ju_code": "J1", "metier": "H-DESIGN", "_rule_ju_list": ["J1"], "diversity_resolved": False},
        {"ju_code": "J2", "metier": "H-SOFTWARE", "_rule_ju_list": [], "diversity_resolved": True},
    ]
    result = d.forward(job_units_json=json.dumps(jus))
    flagged = json.loads(result["flagged_jus_json"])
    assert flagged[0]["_needs_diversity"] is True
    assert flagged[0]["diversity_resolved"] is False
    assert result["unresolved_count"] == "1"


# ──────────────────────────────────────────────
# ALLOC-BR-17: JU Metier Routing
# ──────────────────────────────────────────────

def test_resolve_ju_metier_bh_km():
    """Bench Hours and Kilometres → H-TESTING"""
    assert resolve_ju_metier("Bench Hours", "H-DESIGN") == "H-TESTING"
    assert resolve_ju_metier("Kilometres", "H-SOFTWARE") == "H-TESTING"
    assert resolve_ju_metier("Bench Hours", "H-PROJECT") == "H-TESTING"

def test_resolve_ju_metier_non_testing():
    """Man Day and Kiloeuros → same as project_line.metier"""
    assert resolve_ju_metier("Man Day", "H-DESIGN") == "H-DESIGN"
    assert resolve_ju_metier("Man Day", "H-SOFTWARE") == "H-SOFTWARE"
    assert resolve_ju_metier("Kiloeuros", "H-PROJECT") == "H-PROJECT"
    assert resolve_ju_metier("Man Day", "H-CUSTOMER") == "H-CUSTOMER"

def test_validate_ju_metier_routing_valid():
    """All JUs with correct metier pass validation"""
    jus = [
        {"id": "ju1", "unit_type": "Bench Hours", "metier": "H-TESTING", "project_line_id": "pl1"},
        {"id": "ju2", "unit_type": "Kilometres", "metier": "H-TESTING", "project_line_id": "pl2"},
        {"id": "ju3", "unit_type": "Man Day", "metier": "H-DESIGN", "project_line_id": "pl1"},
    ]
    pls = {
        "pl1": {"metier": "H-DESIGN"},
        "pl2": {"metier": "H-SOFTWARE"},
    }
    result = validate_ju_metier_routing(jus, pls)
    assert result["valid"] is True
    assert len(result["errors"]) == 0

def test_validate_ju_metier_routing_invalid():
    """JUs with wrong metier fail validation"""
    jus = [
        {"id": "ju1", "unit_type": "Bench Hours", "metier": "H-DESIGN", "project_line_id": "pl1"},
        {"id": "ju2", "unit_type": "Man Day", "metier": "H-SOFTWARE", "project_line_id": "pl1"},
    ]
    pls = {
        "pl1": {"metier": "H-DESIGN"},
    }
    result = validate_ju_metier_routing(jus, pls)
    assert result["valid"] is False
    assert len(result["errors"]) == 2

def test_ju_metier_router_module():
    """JUMetierRouter module resolves and validates"""
    router = JUMetierRouter()
    assert router.resolve("Bench Hours", "H-DESIGN") == "H-TESTING"
    assert router.resolve("Man Day", "H-DESIGN") == "H-DESIGN"

    jus = [
        {"id": "ju1", "unit_type": "Bench Hours", "metier": "H-TESTING", "project_line_id": "pl1"},
        {"id": "ju2", "unit_type": "Man Day", "metier": "H-DESIGN", "project_line_id": "pl1"},
    ]
    pls = {"pl1": {"metier": "H-DESIGN"}}
    result = router.forward(jus, pls)
    assert result["valid"] is True
    assert result["resolved"][0]["_expected_metier"] == "H-TESTING"
    assert result["resolved"][1]["_expected_metier"] == "H-DESIGN"

def test_ju_metier_router_invalid():
    """JUMetierRouter reports errors for misrouted JUs"""
    router = JUMetierRouter()
    jus = [
        {"id": "ju1", "unit_type": "Kilometres", "metier": "H-DESIGN", "project_line_id": "pl1"},
    ]
    pls = {"pl1": {"metier": "H-DESIGN"}}
    result = router.forward(jus, pls)
    assert result["valid"] is False
    assert len(result["errors"]) == 1
    assert "H-TESTING" in result["errors"][0]


# ──────────────────────────────────────────────
# Pipeline-level tests
# ──────────────────────────────────────────────

def test_pipeline_full():
    """End-to-end AllocationPipeline with approved JUs"""
    jus = [
        {"ju_code": "J1", "status": "approved", "metier": "H-DESIGN",
         "cost_type": "FTE", "societe": "Horse Spain S.L.-Valladolid",
         "fte_yearly": {"2024": 1.0, "2025": 0.5}},
        {"ju_code": "J2", "status": "estimated", "metier": "H-SOFTWARE",
         "cost_type": "FTE", "societe": "", "fte_yearly": {"2024": 2.0}},
    ]
    ctx = run_allocation("Admin", jus)
    assert ctx.permission_allowed is True
    assert len(ctx.eligible_jus) == 1  # Only approved
    assert ctx.can_save is True

def test_pipeline_denied_role():
    """Engineer cannot access Allocation"""
    ctx = run_allocation("Engineer", [])
    assert ctx.permission_allowed is False
    assert len(ctx.errors) > 0

def test_pipeline_no_approved():
    """No approved JUs = empty allocation"""
    jus = [
        {"ju_code": "J1", "status": "estimated", "metier": "H-DESIGN"},
    ]
    ctx = run_allocation("Admin", jus)
    assert ctx.permission_allowed is True
    assert len(ctx.eligible_jus) == 0


# ──────────────────────────────────────────────
# Business rule coverage tests
# ──────────────────────────────────────────────

def test_alloc_br_01_approved_only():
    """ALLOC-BR-01: Only Approved (PL, Metier) pairs appear"""
    f = AllocationEligibilityFilter()
    jus = [
        {"status": "approved"}, {"status": "estimated"},
        {"status": "draft"}, {"status": "sent"},
    ]
    result = f.forward(job_units_json=json.dumps(jus))
    approved = json.loads(result["approved_jus_json"])
    assert len(approved) == 1
    assert approved[0]["status"] == "approved"

def test_alloc_br_02_skip_assigned():
    """ALLOC-BR-02: Auto-rules skip JUs with existing societe"""
    m = AllocationRuleMatcher([])
    jus = [
        {"ju_code": "J1", "metier": "H-DESIGN", "societe": "Already Set"},
    ]
    result = m.forward(
        job_units_json=json.dumps(jus),
        rules_json=json.dumps([{"fields": {}, "societe": "New Societe"}]),
    )
    assigned = json.loads(result["assigned_jus_json"])
    assert assigned[0]["societe"] == "Already Set"  # Not overwritten

def test_alloc_br_06_tsa_blocks():
    """ALLOC-BR-06: TSA without societe blocks save"""
    v = AllocationSaveValidator()
    jus = [{"ju_code": "J1", "cost_type": "TSA", "societe": ""}]
    result = v.forward(job_units_json=json.dumps(jus))
    assert result["can_save"] is False

def test_alloc_br_07_fte_warns():
    """ALLOC-BR-07: FTE without societe = warning, not error"""
    v = AllocationSaveValidator()
    jus = [{"ju_code": "J1", "cost_type": "FTE", "societe": ""}]
    result = v.forward(job_units_json=json.dumps(jus))
    assert result["can_save"] is True  # Not blocked
    warnings = json.loads(result["warnings_json"])
    assert len(warnings) == 1

def test_alloc_br_08_diversity_non_blocking():
    """ALLOC-BR-08: Unresolved diversity does not block save"""
    v = AllocationSaveValidator()
    jus = [{"ju_code": "J1", "cost_type": "FTE", "societe": "Horse Spain"}]
    result = v.forward(job_units_json=json.dumps(jus))
    assert result["can_save"] is True

def test_alloc_br_09_bulk_overwrites():
    """ALLOC-BR-09: Bulk assign always overwrites existing societes"""
    b = BulkAssigner()
    rows = [{"ju_code": "J1", "societe": "Old"}]
    result = b.forward(rows_json=json.dumps(rows), societe="New")
    updated = json.loads(result["updated_rows_json"])
    assert updated[0]["societe"] == "New"

def test_alloc_br_11_split_100():
    """ALLOC-BR-11: Split percentages must sum to 100%"""
    s = SplitAllocationHandler()
    ju = {"fte_yearly": {"2024": 1.0}}
    result = s.forward(
        ju_json=json.dumps(ju),
        splits_json=json.dumps([{"societe": "A", "percentage": 60}, {"societe": "B", "percentage": 50}]),
    )
    assert "100%" in result["error"]

def test_alloc_br_13_tc_requires_societe():
    """ALLOC-BR-13: TC requires societe"""
    v = AllocationSaveValidator()
    jus = [{"ju_code": "J1", "cost_type": "TC", "societe": ""}]
    result = v.forward(job_units_json=json.dumps(jus))
    assert result["can_save"] is False
    errors = json.loads(result["errors_json"])
    assert "TC" in errors[0]
