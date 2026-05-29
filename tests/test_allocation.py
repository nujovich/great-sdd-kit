"""
GREAT Allocation — Tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from great_sdd.specs.allocation_specs import (
    ALLOCATION_PERMISSIONS, ALLOCATION_ELIGIBLE_STATUSES,
    AVAILABLE_SOCIETES, FTE_RATES, TSA_RATES,
    calculate_fte_ke, calculate_tsa_ke, distribute_tc_ke,
    apply_split, route_hproject_hnp,
    ALLOCATION_RULES_LIST,
)
from great_sdd.modules.allocation import (
    AllocationPermissionChecker, AllocationEligibilityFilter,
    AllocationRuleMatcher, HProjectRouter, KECalculator,
    TCPopupHandler, SplitAllocationHandler, BulkAssigner,
    AllocationSaveValidator, DiversityDropdownHandler,
)

def test_permissions():
    from great_sdd.specs.pre_estimation_specs import Role
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
    assert len(ALLOCATION_RULES_LIST) == 16

# ── Module tests ──

def test_permission_checker():
    c = AllocationPermissionChecker()
    assert c.forward("Admin")["can_view"] is True
    assert c.forward("Engineer")["can_view"] is False
    assert c.forward("RCRC")["can_edit"] is True
    assert c.forward("CPO")["can_view"] is False

def test_eligibility_filter():
    f = AllocationEligibilityFilter()
    jus = [
        {"ju_code": "J1", "status": "approved"},
        {"ju_code": "J2", "status": "estimated"},
        {"ju_code": "J3", "status": "approved"},
    ]
    result = f.forward(jus)
    assert len(result) == 2
    assert all(j["status"] == "approved" for j in result)

def test_rule_matcher_with_empty_rules():
    m = AllocationRuleMatcher([])
    jus = [{"ju_code": "J1", "metier": "Backend"}]
    result = m.forward(jus)
    assert len(result) == 1
    assert result[0].get("societe") is None

def test_rule_matcher_skips_assigned():
    m = AllocationRuleMatcher([
        {"fields": {"metier": "Backend"}, "societe": "Horse Spain", "exception": False},
    ])
    jus = [
        {"ju_code": "J1", "metier": "Backend", "societe": "Already Set"},
        {"ju_code": "J2", "metier": "Backend"},
    ]
    result = m.forward(jus)
    assert result[0]["societe"] == "Already Set"  # Skipped
    assert result[1]["societe"] == "Horse Spain"

def test_ke_calculator():
    c = KECalculator()
    jus = [{
        "ju_code": "J1",
        "cost_type": "FTE",
        "societe": "Horse Spain S.L.-Valladolid",
        "fte_yearly": {"2024": 1.0, "2025": 0.5},
    }]
    result = c.forward(jus)
    assert result[0]["ke_yearly"]["2024"] == 107.0
    assert result[0]["ke_yearly"]["2025"] == 53.0  # 0.5 × 106

def test_tc_handler():
    h = TCPopupHandler()
    result = h.forward({"fte_yearly": {"2024": 2.0, "2025": 1.0}}, 150.0)
    assert result["total_ke"] == 150.0
    assert result["cost_type"] == "TC"
    assert result["ke_yearly"]["2024"] == 100.0

def test_save_validator():
    v = AllocationSaveValidator()
    jus = [
        {"ju_code": "J1", "cost_type": "FTE", "societe": ""},
        {"ju_code": "J2", "cost_type": "TC", "societe": ""},
    ]
    result = v.forward(jus)
    assert result["can_save"] is False  # TC without societe
    assert len(result["errors"]) == 1
    assert len(result["warnings"]) == 1

def test_save_validator_ok():
    v = AllocationSaveValidator()
    jus = [
        {"ju_code": "J1", "cost_type": "FTE", "societe": "Horse Spain"},
        {"ju_code": "J2", "cost_type": "TC", "societe": "Horse Romania"},
    ]
    result = v.forward(jus)
    assert result["can_save"] is True
    assert len(result["errors"]) == 0

def test_bulk_assigner():
    b = BulkAssigner()
    rows = [
        {"ju_code": "J1", "societe": ""},
        {"ju_code": "J2", "societe": "Old"},
    ]
    result = b.forward(rows, "New Societe")
    assert all(r["societe"] == "New Societe" for r in result)
    assert all(r["_bulk_assigned"] for r in result)

def test_split_handler():
    s = SplitAllocationHandler()
    ju = {"ju_code": "J1", "fte_yearly": {"2024": 1.0, "2025": 0.5}}
    result = s.forward(ju, [{"societe": "A", "percentage": 60}, {"societe": "B", "percentage": 40}])
    assert len(result) == 2
    assert result[0]["_is_split_child"] is True
    assert result[0]["fte_yearly"]["2024"] == 0.6


from great_sdd.specs.pre_estimation_specs import LineStatus, Role