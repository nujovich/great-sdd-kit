"""
GREAT Transversal Features — Tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from great_sdd.specs.transversal_specs import (
    EstimationCycle, WorkloadStandardVersion,
    CYCLE_MANAGERS, WORKLOAD_UPLOADERS, WORKLOAD_DELETERS,
    CYCLE_RULES, WORKLOAD_RULES, BULK_DELETION_RULES,
    TABLE_RULES, EMAIL_RULES,
    TRANSVERSAL_RULES,
)
from great_sdd.modules.transversal import (
    CycleManager, WorkloadStandardManager, BulkInductorDeleter,
    TableStateManager, EmailAlertService,
)
from great_sdd.specs.pre_estimation_specs import Role

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
    assert len(TRANSVERSAL_RULES) == 27

def test_transversal_rules_match():
    assert len(TRANSVERSAL_RULES) == len(CYCLE_RULES) + len(WORKLOAD_RULES) + len(BULK_DELETION_RULES) + len(TABLE_RULES) + len(EMAIL_RULES)

def test_bulk_deletion_rules_count():
    assert len(BULK_DELETION_RULES) == 10

def test_workload_deleters():
    assert Role.ADMIN in WORKLOAD_DELETERS
    assert Role.RCRC in WORKLOAD_DELETERS
    assert Role.ENGINEER not in WORKLOAD_DELETERS
    assert Role.PMO not in WORKLOAD_DELETERS


# ── Bulk Inductor Deletion tests ──

def _make_version_with_inductors(version_id, inductors, status="active"):
    """Helper: create a WorkloadStandardVersion with attached inductors."""
    from datetime import datetime
    v = WorkloadStandardVersion(
        version_id=version_id,
        uploaded_at=datetime.now().isoformat(),
        uploaded_by="Admin",
        filename="standards.xlsx",
        status=status,
    )
    v._inductors = inductors
    return v


def test_bulk_delete_success():
    deleter = BulkInductorDeleter()
    v1 = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "Backend Module A", "metier": "Backend"},
        {"id": "ind-2", "name": "Frontend Module B", "metier": "Frontend"},
        {"id": "ind-3", "name": "Data Pipeline C", "metier": "Data"},
    ], status="superseded")
    deleter.set_versions([v1])
    result = deleter.bulk_delete("WL-0001", ["ind-1", "ind-3"], "Admin")
    assert result["success"] is True
    assert result["deleted_count"] == 2
    assert "ind-1" in result["deleted_ids"]
    assert "ind-3" in result["deleted_ids"]
    assert result["remaining_count"] == 1

def test_bulk_delete_permission_denied():
    deleter = BulkInductorDeleter()
    version = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "Backend Module A"},
    ], status="superseded")
    deleter.set_versions([version])
    result = deleter.bulk_delete("WL-0001", ["ind-1"], "Engineer")
    assert result["success"] is False
    assert "DEL-BR-01" in result["error"]

def test_bulk_delete_empty_selection():
    deleter = BulkInductorDeleter()
    version = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "Backend Module A"},
    ], status="superseded")
    deleter.set_versions([version])
    result = deleter.bulk_delete("WL-0001", [], "Admin")
    assert result["success"] is False
    assert "DEL-BR-09" in result["error"]

def test_bulk_delete_active_version_protected():
    """DEL-BR-05: Cannot delete from active version if it's the only version."""
    deleter = BulkInductorDeleter()
    version = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "Backend Module A"},
    ], status="active")
    deleter.set_versions([version])
    result = deleter.bulk_delete("WL-0001", ["ind-1"], "Admin")
    assert result["success"] is False
    assert "DEL-BR-05" in result["error"]

def test_bulk_delete_superseded_version_ok():
    """Can delete from superseded version even if it's the only one."""
    deleter = BulkInductorDeleter()
    version = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "Backend Module A"},
    ], status="superseded")
    deleter.set_versions([version])
    result = deleter.bulk_delete("WL-0001", ["ind-1"], "Admin")
    assert result["success"] is True
    assert result["deleted_count"] == 1

def test_bulk_delete_not_found_version():
    deleter = BulkInductorDeleter()
    deleter.set_versions([])
    result = deleter.bulk_delete("WL-9999", ["ind-1"], "Admin")
    assert result["success"] is False
    assert "not found" in result["error"].lower()

def test_bulk_delete_list_deletable():
    """DEL-BR-02: List shows only loaded inductors."""
    deleter = BulkInductorDeleter()
    version = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "Backend A"},
        {"id": "ind-2", "name": "Frontend B"},
    ])
    deleter.set_versions([version])
    inductors = deleter.list_deletable_inductors("WL-0001")
    assert len(inductors) == 2
    assert inductors[0]["name"] == "Backend A"

def test_bulk_delete_list_empty_version():
    deleter = BulkInductorDeleter()
    deleter.set_versions([])
    inductors = deleter.list_deletable_inductors("WL-9999")
    assert inductors == []

def test_bulk_delete_log():
    """DEL-BR-10: Deletion log tracks operations."""
    deleter = BulkInductorDeleter()
    v1 = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "A"},
        {"id": "ind-2", "name": "B"},
    ], status="superseded")
    deleter.set_versions([v1])
    deleter.bulk_delete("WL-0001", ["ind-1"], "Admin")
    deleter.bulk_delete("WL-0001", ["ind-2"], "Admin")
    log = deleter.get_deletion_log()
    assert len(log) == 2
    assert log[0].deleted_count == 1
    assert log[1].deleted_count == 1

def test_bulk_delete_rcrc_can_delete():
    deleter = BulkInductorDeleter()
    version = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "A"},
    ], status="superseded")
    deleter.set_versions([version])
    result = deleter.bulk_delete("WL-0001", ["ind-1"], "RCRC")
    assert result["success"] is True

def test_bulk_delete_message_includes_summary():
    """DEL-BR-10: Message mentions deleted count."""
    deleter = BulkInductorDeleter()
    v1 = _make_version_with_inductors("WL-0001", [
        {"id": "ind-1", "name": "A"},
        {"id": "ind-2", "name": "B"},
    ], status="superseded")
    deleter.set_versions([v1])
    result = deleter.bulk_delete("WL-0001", ["ind-1", "ind-2"], "Admin")
    assert result["success"] is True
    assert "Deleted 2" in result["message"]
    assert "DEL-BR-10" in result["message"]

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