"""
GREAT Final Review — Tests.

Tests cover:
- Spec-level: permissions, eligibility, aggregation levels, stage3 config, rules count
- Module-level: each SignatureModule's forward() with proper kwargs
- Pipeline-level: end-to-end FinalReviewPipeline.run_final_review()
- Business rules: FR-BR-01 through FR-BR-10
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import json
import pytest

from great_sdd.specs.pre_estimation_specs import LineStatus, Role
from great_sdd.specs.final_review_specs import (
    FINAL_REVIEW_PERMISSIONS, FINAL_REVIEW_ELIGIBLE_STATUSES,
    AGGREGATION_LEVELS, STAGE3_SEND_CONFIG, FINAL_REVIEW_RULES,
    aggregate_at_level, calculate_subtotals,
)
from great_sdd.modules.final_review import (
    FinalReviewPermissionChecker, FinalReviewEligibilityFilter,
    AggregationEngine, CSVGlobalExporter, Stage3Sender,
)
from great_sdd.pipeline.final_review_pipeline import run_final_review

# ──────────────────────────────────────────────
# Spec tests
# ──────────────────────────────────────────────

def test_permissions():
    assert FINAL_REVIEW_PERMISSIONS[Role.ADMIN].can_send_stage3 is True
    assert FINAL_REVIEW_PERMISSIONS[Role.PMO].can_send_stage3 is True
    assert FINAL_REVIEW_PERMISSIONS[Role.CPO].can_send_stage3 is False
    assert FINAL_REVIEW_PERMISSIONS[Role.ENGINEER].can_send_stage3 is False
    assert FINAL_REVIEW_PERMISSIONS[Role.RCRC].can_send_stage3 is False

def test_all_roles_see_all():
    """FR-BR-04: All roles see all lines"""
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
        {"metier": "H-DESIGN", "societe": "A", "total_fte": 1.0, "total_ke": 50.0},
        {"metier": "H-DESIGN", "societe": "A", "total_fte": 0.5, "total_ke": 25.0},
        {"metier": "H-SOFTWARE", "societe": "B", "total_fte": 2.0, "total_ke": 100.0},
    ]
    result = aggregate_at_level(jus, ["metier"], ["total_fte", "total_ke"])
    assert len(result) == 2
    backend = [r for r in result if r["metier"] == "H-DESIGN"][0]
    assert backend["total_fte"] == 1.5

def test_calculate_subtotals():
    rows = [
        {"total_fte": 1.0, "total_ke": 50.0},
        {"total_fte": 0.5, "total_ke": 25.0},
    ]
    result = calculate_subtotals(rows, ["total_fte", "total_ke"])
    assert result["total_fte"] == 1.5
    assert result["total_ke"] == 75.0


# ──────────────────────────────────────────────
# Module-level tests (Signature-driven)
# ──────────────────────────────────────────────

def test_permission_checker():
    """CHECK_FINAL_REVIEW_PERMISSION signature"""
    c = FinalReviewPermissionChecker()
    assert c.forward(role="Admin", action="view")["allowed"] is True
    assert c.forward(role="Admin", action="send_stage3")["allowed"] is True
    assert c.forward(role="Engineer", action="send_stage3")["allowed"] is False
    assert c.forward(role="CPO", action="view")["allowed"] is True  # CPO can view FR

def test_eligibility_filter():
    """FILTER_FINAL_REVIEW_JUS signature — FR-BR-03"""
    f = FinalReviewEligibilityFilter()
    jus = [
        {"ju_code": "J1", "status": "approved"},
        {"ju_code": "J2", "status": "estimated"},
    ]
    result = f.forward(job_units_json=json.dumps(jus))
    approved = json.loads(result["approved_jus_json"])
    assert len(approved) == 1
    assert result["excluded_count"] == "1"

def test_aggregation_engine():
    """AGGREGATE_FINAL_REVIEW signature"""
    e = AggregationEngine()
    jus = [
        {"metier": "H-DESIGN", "societe": "A", "cost_type": "FTE",
         "total_fte": 1.0, "total_ke": 50.0, "total_bh": 0, "total_km": 0},
        {"metier": "H-DESIGN", "societe": "A", "cost_type": "TC",
         "total_fte": 0.0, "total_ke": 30.0, "total_bh": 0, "total_km": 0},
    ]
    result = e.forward(job_units_json=json.dumps(jus))
    agg = json.loads(result["aggregations_json"])
    assert len(agg["by_cost_type"]) == 2
    assert agg["pl_total"]["total_fte"] == 1.0
    assert agg["pl_total"]["total_ke"] == 80.0

def test_csv_exporter():
    """EXPORT_FINAL_REVIEW_CSV signature — FR-BR-10"""
    e = CSVGlobalExporter()
    jus = [{"pl_number": "PL-001", "pl_name": "Test", "metier": "H-DESIGN",
            "total_fte": 1.0, "total_ke": 50.0, "total_bh": 0, "total_km": 0,
            "owner_n2": "", "societe": "A", "cost_type": "FTE",
            "fmm_description": "", "ju_description": "", "ju_code": "J1"}]
    result = e.forward(job_units_json=json.dumps(jus))
    assert result["row_count"] == "1"
    assert "PL-001" in result["csv_content"]
    assert "H-DESIGN" in result["csv_content"]

def test_csv_exporter_empty():
    """EXPORT_FINAL_REVIEW_CSV — empty input"""
    e = CSVGlobalExporter()
    result = e.forward(job_units_json="[]")
    assert result["row_count"] == "0"
    assert result["csv_content"] == ""

def test_stage3_sender_no_warning():
    """SEND_STAGE3 — all JUs assigned, no warning needed"""
    s = Stage3Sender()
    jus = [{"pl_number": "PL-001", "societe": "A", "total_fte": 1.0}]
    result = s.forward(job_units_json=json.dumps(jus), confirmed=True)
    assert result["success"] is True
    payload = json.loads(result["payload_json"])
    assert payload["total_fte"] == 1.0

def test_stage3_sender_needs_confirmation():
    """SEND_STAGE3 — FR-BR-06: unassigned JUs need confirmation but don't block"""
    s = Stage3Sender()
    jus = [{"pl_number": "PL-001", "societe": "", "total_fte": 1.0}]
    result = s.forward(job_units_json=json.dumps(jus), confirmed=False)
    assert result["success"] is False
    assert result["needs_confirmation"] is True
    assert "societe" in result["warning"].lower()

def test_stage3_sender_confirmed():
    """SEND_STAGE3 — FR-BR-06: confirmed despite warning"""
    s = Stage3Sender()
    jus = [{"pl_number": "PL-001", "societe": "", "total_fte": 1.0}]
    result = s.forward(job_units_json=json.dumps(jus), confirmed=True)
    assert result["success"] is True


# ──────────────────────────────────────────────
# Pipeline-level tests
# ──────────────────────────────────────────────

def test_pipeline_full():
    """End-to-end FinalReviewPipeline with approved JUs"""
    jus = [
        {"ju_code": "J1", "status": "approved", "metier": "H-DESIGN",
         "societe": "Horse Spain", "cost_type": "FTE",
         "total_fte": 1.0, "total_ke": 107.0, "total_bh": 0, "total_km": 0},
        {"ju_code": "J2", "status": "estimated", "metier": "H-SOFTWARE",
         "societe": "", "cost_type": "FTE",
         "total_fte": 2.0, "total_ke": 0, "total_bh": 0, "total_km": 0},
    ]
    ctx = run_final_review("Admin", jus)
    assert ctx.permission_allowed is True
    assert len(ctx.eligible_jus) == 1  # Only approved
    assert ctx.can_send_stage3 is True

def test_pipeline_denied_send():
    """Engineer can view but not send Stage 3"""
    ctx = run_final_review("Engineer", [])
    assert ctx.permission_allowed is True
    assert ctx.can_send_stage3 is False

def test_pipeline_no_approved():
    """No approved JUs = empty final review"""
    jus = [{"ju_code": "J1", "status": "estimated"}]
    ctx = run_final_review("Admin", jus)
    assert ctx.permission_allowed is True
    assert len(ctx.eligible_jus) == 0


# ──────────────────────────────────────────────
# Business rule coverage tests
# ──────────────────────────────────────────────

def test_fr_br_01_read_only():
    """FR-BR-01: Read-only page — no data can be edited"""
    c = FinalReviewPermissionChecker()
    # All roles can view
    for role in ["Admin", "PMO", "CPO", "Engineer", "RCRC"]:
        assert c.forward(role=role, action="view")["allowed"] is True

def test_fr_br_03_approved_only():
    """FR-BR-03: Only Approved (PL, Metier) pairs appear"""
    f = FinalReviewEligibilityFilter()
    jus = [
        {"status": "approved"}, {"status": "estimated"},
        {"status": "draft"}, {"status": "sent"},
    ]
    result = f.forward(job_units_json=json.dumps(jus))
    approved = json.loads(result["approved_jus_json"])
    assert len(approved) == 1
    assert approved[0]["status"] == "approved"

def test_fr_br_04_all_roles_see_all():
    """FR-BR-04: All roles see all lines — no scoping by assignee"""
    for role in Role:
        perm = FINAL_REVIEW_PERMISSIONS[role]
        assert perm.scope == "all_lines"

def test_fr_br_06_stage3_non_blocking():
    """FR-BR-06: Stage 3 non-blocking — PMO can send with incomplete allocation"""
    s = Stage3Sender()
    jus = [{"pl_number": "PL-001", "societe": "", "total_fte": 1.0}]
    # Without confirmation: needs_confirmation=True but not blocked
    result = s.forward(job_units_json=json.dumps(jus), confirmed=False)
    assert result["needs_confirmation"] is True
    assert result["success"] is False  # Needs confirmation first
    # With confirmation: succeeds
    result = s.forward(job_units_json=json.dumps(jus), confirmed=True)
    assert result["success"] is True

def test_fr_br_07_stage3_resendable():
    """FR-BR-07: Stage 3 re-sendable — can be triggered multiple times"""
    s = Stage3Sender()
    jus = [{"pl_number": "PL-001", "societe": "A", "total_fte": 1.0}]
    result1 = s.forward(job_units_json=json.dumps(jus), confirmed=True)
    result2 = s.forward(job_units_json=json.dumps(jus), confirmed=True)
    assert result1["success"] is True
    assert result2["success"] is True

def test_fr_br_08_stage3_all_lines():
    """FR-BR-08: Stage 3 sends entire active cycle, no per-line send"""
    assert STAGE3_SEND_CONFIG["scope"] == "all_lines"
    assert STAGE3_SEND_CONFIG["per_line_send"] is False

def test_fr_br_10_csv_flat():
    """FR-BR-10: CSV flat export — one row per JU, no subtotal rows"""
    e = CSVGlobalExporter()
    jus = [
        {"pl_number": "PL-001", "pl_name": "Test", "metier": "H-DESIGN",
         "total_fte": 1.0, "total_ke": 50.0, "total_bh": 0, "total_km": 0,
         "owner_n2": "", "societe": "A", "cost_type": "FTE",
         "fmm_description": "", "ju_description": "", "ju_code": "J1"},
        {"pl_number": "PL-001", "pl_name": "Test", "metier": "H-DESIGN",
         "total_fte": 0.5, "total_ke": 25.0, "total_bh": 0, "total_km": 0,
         "owner_n2": "", "societe": "A", "cost_type": "FTE",
         "fmm_description": "", "ju_description": "", "ju_code": "J2"},
    ]
    result = e.forward(job_units_json=json.dumps(jus))
    # 2 data rows + 1 header = 3 lines
    lines = result["csv_content"].strip().split("\n")
    assert len(lines) == 3  # header + 2 JU rows (no subtotals)
    assert result["row_count"] == "2"
