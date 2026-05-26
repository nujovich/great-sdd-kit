"""
GREAT Final Review — Tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from great_dspy.specs.final_review_specs import (
    FINAL_REVIEW_PERMISSIONS, FINAL_REVIEW_ELIGIBLE_STATUSES,
    AGGREGATION_LEVELS, STAGE3_SEND_CONFIG, FINAL_REVIEW_RULES,
    aggregate_at_level, calculate_subtotals,
)
from great_dspy.modules.final_review import (
    FinalReviewPermissionChecker, FinalReviewEligibilityFilter,
    AggregationEngine, CSVGlobalExporter, Stage3Sender,
)
from great_dspy.specs.pre_estimation_specs import LineStatus, Role

# ── Spec tests ──

def test_permissions():
    assert FINAL_REVIEW_PERMISSIONS[Role.ADMIN].can_send_stage3 is True
    assert FINAL_REVIEW_PERMISSIONS[Role.PMO].can_send_stage3 is True
    assert FINAL_REVIEW_PERMISSIONS[Role.CPO].can_send_stage3 is False
    assert FINAL_REVIEW_PERMISSIONS[Role.ENGINEER].can_send_stage3 is False
    assert FINAL_REVIEW_PERMISSIONS[Role.RCRC].can_send_stage3 is False

def test_all_roles_see_all():
    for role in Role:
        assert FINAL_REVIEW_PERMISSIONS[role].scope == "all_lines"

def test_eligibility():
    assert FINAL_REVIEW_ELIGIBLE_STATUSES == {LineStatus.APPROVED}

def test_aggregation_levels():
    assert len(AGGREGATION_LEVELS) == 5
    assert AGGREGATION_LEVELS[0] == "job_unit_row"
    assert AGGREGATION_LEVELS[-1] == "pl_total"

def test_stage3_config():
    assert STAGE3_SEND_CONFIG["resendable"] is True
    assert STAGE3_SEND_CONFIG["blocking_prerequisites"] is False
    assert STAGE3_SEND_CONFIG["scope"] == "all_lines"

def test_10_rules():
    assert len(FINAL_REVIEW_RULES) == 10

def test_aggregate_at_level():
    jus = [
        {"metier": "Backend", "societe": "A", "total_fte": 1.0, "total_ke": 50.0},
        {"metier": "Backend", "societe": "A", "total_fte": 0.5, "total_ke": 25.0},
        {"metier": "Frontend", "societe": "B", "total_fte": 2.0, "total_ke": 100.0},
    ]
    result = aggregate_at_level(jus, ["metier"], ["total_fte", "total_ke"])
    assert len(result) == 2
    backend = [r for r in result if r["metier"] == "Backend"][0]
    assert backend["total_fte"] == 1.5

def test_calculate_subtotals():
    rows = [
        {"total_fte": 1.0, "total_ke": 50.0},
        {"total_fte": 0.5, "total_ke": 25.0},
    ]
    result = calculate_subtotals(rows, ["total_fte", "total_ke"])
    assert result["total_fte"] == 1.5
    assert result["total_ke"] == 75.0

# ── Module tests ──

def test_permission_checker():
    c = FinalReviewPermissionChecker()
    assert c.forward("Admin", "view")["allowed"] is True
    assert c.forward("Admin", "send_stage3")["allowed"] is True
    assert c.forward("Engineer", "send_stage3")["allowed"] is False
    assert c.forward("CPO", "view")["allowed"] is True  # CPO can view FR

def test_eligibility_filter():
    f = FinalReviewEligibilityFilter()
    jus = [
        {"ju_code": "J1", "status": "approved"},
        {"ju_code": "J2", "status": "estimated"},
    ]
    result = f.forward(jus)
    assert len(result) == 1

def test_aggregation_engine():
    e = AggregationEngine()
    jus = [
        {"metier": "Backend", "societe": "A", "cost_type": "FTE",
         "total_fte": 1.0, "total_ke": 50.0, "total_bh": 0, "total_km": 0},
        {"metier": "Backend", "societe": "A", "cost_type": "TC",
         "total_fte": 0.0, "total_ke": 30.0, "total_bh": 0, "total_km": 0},
    ]
    agg = e.forward(jus)
    assert len(agg["by_cost_type"]) == 2
    assert agg["pl_total"]["total_fte"] == 1.0
    assert agg["pl_total"]["total_ke"] == 80.0

def test_csv_exporter():
    e = CSVGlobalExporter()
    jus = [{"pl_number": "PL-001", "pl_name": "Test", "metier": "Backend",
            "total_fte": 1.0, "total_ke": 50.0, "total_bh": 0, "total_km": 0,
            "owner_n2": "", "societe": "A", "cost_type": "FTE",
            "fmm_description": "", "ju_description": "", "ju_code": "J1"}]
    result = e.forward(jus)
    assert result["row_count"] == 1
    assert "PL-001" in result["csv_content"]
    assert "Backend" in result["csv_content"]

def test_csv_exporter_empty():
    e = CSVGlobalExporter()
    result = e.forward([])
    assert result["row_count"] == 0
    assert result["csv_content"] == ""

def test_stage3_sender_no_warning():
    s = Stage3Sender()
    jus = [{"pl_number": "PL-001", "societe": "A", "total_fte": 1.0}]
    result = s.forward(jus, confirmed=True)
    assert result["success"] is True
    assert result["payload"]["total_fte"] == 1.0

def test_stage3_sender_needs_confirmation():
    s = Stage3Sender()
    jus = [{"pl_number": "PL-001", "societe": "", "total_fte": 1.0}]
    result = s.forward(jus, confirmed=False)
    assert result["success"] is False
    assert result["needs_confirmation"] is True
    assert "no societe" in result["warning"].lower()