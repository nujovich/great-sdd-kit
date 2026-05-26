"""
GREAT Transversal Features — Tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from great_dspy.specs.transversal_specs import (
    EstimationCycle, WorkloadStandardVersion,
    CYCLE_MANAGERS, WORKLOAD_UPLOADERS,
    CYCLE_RULES, WORKLOAD_RULES, TABLE_RULES, EMAIL_RULES,
    TRANSVERSAL_RULES,
)
from great_dspy.modules.transversal import (
    CycleManager, WorkloadStandardManager,
    TableStateManager, EmailAlertService,
)
from great_dspy.specs.pre_estimation_specs import Role

# ── Spec tests ──

def test_cycle_managers():
    assert Role.PMO in CYCLE_MANAGERS
    assert Role.ADMIN in CYCLE_MANAGERS
    assert Role.ENGINEER not in CYCLE_MANAGERS

def test_workload_uploaders():
    assert Role.ADMIN in WORKLOAD_UPLOADERS
    assert Role.RCRC in WORKLOAD_UPLOADERS
    assert Role.PMO not in WORKLOAD_UPLOADERS

def test_cycle_rules():
    assert len(CYCLE_RULES) == 4

def test_workload_rules():
    assert len(WORKLOAD_RULES) == 6

def test_table_rules():
    assert len(TABLE_RULES) == 3

def test_email_rules():
    assert len(EMAIL_RULES) == 4

def test_transversal_rules():
    assert len(TRANSVERSAL_RULES) == 17

def test_transversal_rules_match():
    assert len(TRANSVERSAL_RULES) == len(CYCLE_RULES) + len(WORKLOAD_RULES) + len(TABLE_RULES) + len(EMAIL_RULES)

# ── Cycle Manager tests ──

def test_create_cycle():
    m = CycleManager()
    result = m.create_cycle("2026 H1", "2026-01-01", "Admin")
    assert result["success"] is True
    assert result["cycle"].name == "2026 H1"
    assert result["cycle"].active is True

def test_create_cycle_auto_deactivates():
    m = CycleManager()
    m.create_cycle("2025 H2", "2025-07-01", "Admin")
    m.create_cycle("2026 H1", "2026-01-01", "Admin")
    cycles = m.list_cycles()
    active_cycles = [c for c in cycles if c["active"]]
    assert len(active_cycles) == 1
    assert active_cycles[0]["name"] == "2026 H1"

def test_engineer_cannot_create_cycle():
    m = CycleManager()
    result = m.create_cycle("Test", "2026-01-01", "Engineer")
    assert result["success"] is False

def test_cpo_cannot_create_cycle():
    m = CycleManager()
    result = m.create_cycle("Test", "2026-01-01", "CPO")
    assert result["success"] is False

def test_get_active_cycle():
    m = CycleManager()
    assert m.get_active_cycle() is None
    m.create_cycle("Active", "2026-01-01", "Admin")
    assert m.get_active_cycle() is not None
    assert m.get_active_cycle().name == "Active"

def test_no_reactivation():
    m = CycleManager()
    m.create_cycle("Old", "2025-01-01", "Admin")
    m.create_cycle("New", "2026-01-01", "Admin")
    result = m.validate_no_reactivation("Old")
    assert result["valid"] is False
    assert "reactivated" in result["error"].lower()

def test_cycle_not_found():
    m = CycleManager()
    result = m.validate_no_reactivation("NonExistent")
    assert result["valid"] is False

# ── Workload Standard tests ──

def test_upload_xlsx():
    m = WorkloadStandardManager()
    result = m.upload_version("standards.xlsx", "Admin", "Admin")
    assert result["success"] is True
    assert result["version"].status == "active"

def test_upload_non_xlsx_rejected():
    m = WorkloadStandardManager()
    result = m.upload_version("standards.csv", "Admin", "Admin")
    assert result["success"] is False

def test_upload_permission_denied():
    m = WorkloadStandardManager()
    result = m.upload_version("standards.xlsx", "Engineer", "Engineer")
    assert result["success"] is False

def test_version_supersedes_previous():
    m = WorkloadStandardManager()
    m.upload_version("v1.xlsx", "Admin", "Admin")
    m.upload_version("v2.xlsx", "Admin", "Admin")
    versions = m.list_versions()
    v1 = [v for v in versions if v["version_id"] == "WL-0001"][0]
    v2 = [v for v in versions if v["version_id"] == "WL-0002"][0]
    assert v1["status"] == "superseded"
    assert v2["status"] == "active"

def test_get_active_version():
    m = WorkloadStandardManager()
    assert m.get_active_version() is None
    m.upload_version("v1.xlsx", "Admin", "Admin")
    assert m.get_active_version() is not None

def test_validate_file():
    m = WorkloadStandardManager()
    assert len(m.validate_file("data.csv")) > 0
    assert len(m.validate_file("data.xlsx")) == 0

# ── Table State tests ──

def test_table_state_initial():
    m = TableStateManager()
    state = m.get_state("Pre-Estimation")
    assert state.page == "Pre-Estimation"
    assert state.filters == {}

def test_set_filter():
    m = TableStateManager()
    m.set_filter("Allocation", "metier", "Backend")
    state = m.get_state("Allocation")
    assert state.filters["metier"] == "Backend"

def test_set_sort():
    m = TableStateManager()
    m.set_sort("Estimation Review", "status", "desc")
    state = m.get_state("Estimation Review")
    assert state.sort_column == "status"
    assert state.sort_direction == "desc"

def test_set_column_width():
    m = TableStateManager()
    m.set_column_width("Pre-Estimation", "PL Name", 300)
    state = m.get_state("Pre-Estimation")
    assert state.column_widths["PL Name"] == 300

def test_reset_page():
    m = TableStateManager()
    m.set_filter("Allocation", "metier", "Backend")
    m.reset_page("Allocation")
    state = m.get_state("Allocation")
    assert state.filters == {}

def test_reset_all():
    m = TableStateManager()
    m.set_filter("A", "f", "v")
    m.set_filter("B", "f", "v")
    m.reset_all()
    assert m.get_state("A").filters == {}
    assert m.get_state("B").filters == {}

# ── Email Alert tests ──

def test_engineer_weekly():
    s = EmailAlertService()
    result = s.send_engineer_weekly("ana@great.com", [
        {"status": "estimated"}, {"status": "approved"}
    ], "2026 H1")
    assert result["success"] is True
    assert "estimated" in result["body"].lower()
    assert "approved" in result["body"].lower()

def test_rcrc_weekly():
    s = EmailAlertService()
    result = s.send_rcrc_weekly(
        ["rcrc@great.com"],
        {"total_jus": 100, "assigned_jus": 80, "unassigned_jus": 20, "split_rows": 5},
        "2026 H1",
    )
    assert result["success"] is True
    assert "100" in result["body"]

def test_rejection_notification():
    s = EmailAlertService()
    result = s.send_rejection_notification(
        "ana@great.com", "PL-001", "Backend",
        "Insufficient detail", "2026 H1"
    )
    assert result["success"] is True
    assert "PL-001" in result["body"]
    assert "rejected" in result["subject"].lower()

def test_email_log():
    s = EmailAlertService()
    s.send_engineer_weekly("ana@great.com", [], "2026 H1")
    s.send_rejection_notification("ana@great.com", "PL-001", "Backend", "Rework", "2026 H1")
    log = s.get_log()
    assert len(log) == 2
    assert log[0].alert_type == "engineer_weekly"
    assert log[1].alert_type == "rejection_notification"


# Remove unused import from the autogenerated test
# (already imported at top)