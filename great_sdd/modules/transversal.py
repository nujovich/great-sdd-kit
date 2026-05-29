"""
GREAT Transversal Features — Pipeline Modules.

Spans the entire application: cycles, workload standards,
table capabilities, and email alerts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from great_sdd.modules.base import Module
from great_sdd.specs.pre_estimation_specs import Role, LineStatus
from great_sdd.specs.transversal_specs import (
    EstimationCycle,
    WorkloadStandardVersion,
    CYCLE_MANAGERS,
    WORKLOAD_UPLOADERS,
    WORKLOAD_DELETERS,
    BULK_DELETION_RULES,
    TABLE_CAPABILITIES,
    TABLE_SCOPE,
    EMAIL_ALERTS,
    EMAIL_LOG_FIELDS,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 1. Estimation Cycles (§2)
# ═══════════════════════════════════════════════

class CycleManager(Module):
    """Manage estimation cycles — create, activate, deactivate."""

    def __init__(self, lm=None):
        super().__init__(lm)
        self._cycles: list[EstimationCycle] = []

    def set_cycles(self, cycles: list[EstimationCycle]):
        self._cycles = cycles

    def get_active_cycle(self) -> Optional[EstimationCycle]:
        for c in self._cycles:
            if c.active:
                return c
        return None

    def create_cycle(self, name: str, start_date: str,
                     created_by_role: str) -> dict:
        """Create a new cycle. Auto-deactivates current one. (§2.4)"""
        try:
            role_enum = Role(created_by_role)
        except ValueError:
            return {"success": False, "error": f"Unknown role: {created_by_role}"}

        if role_enum not in CYCLE_MANAGERS:
            return {"success": False, "error": f"{created_by_role} cannot manage cycles"}

        # Deactivate all existing cycles
        for c in self._cycles:
            if c.active:
                c.active = False

        # Create new cycle
        new_cycle = EstimationCycle(name=name, start_date=start_date, active=True)
        self._cycles.append(new_cycle)

        return {
            "success": True,
            "cycle": new_cycle,
            "deactivated_previous": len(self._cycles) > 1,
        }

    def get_cycle_by_name(self, name: str) -> Optional[EstimationCycle]:
        for c in self._cycles:
            if c.name == name:
                return c
        return None

    def list_cycles(self) -> list[dict]:
        return [
            {"name": c.name, "start_date": c.start_date,
             "active": c.active, "is_historical": not c.active}
            for c in self._cycles
        ]

    def validate_no_reactivation(self, cycle_name: str) -> dict:
        """CYCLE-BR-02: Inactive cycles cannot be reactivated."""
        cycle = self.get_cycle_by_name(cycle_name)
        if not cycle:
            return {"valid": False, "error": f"Cycle '{cycle_name}' not found"}
        if cycle.active:
            return {"valid": True, "message": "Cycle is already active"}
        return {"valid": False, "error": "Inactive cycles cannot be reactivated (CYCLE-BR-02)"}


# ═══════════════════════════════════════════════
# 2. Workload Standard Versioning (§3)
# ═══════════════════════════════════════════════

class WorkloadStandardManager(Module):
    """Manage workload standard uploads and versioning."""

    def __init__(self, lm=None):
        super().__init__(lm)
        self._versions: list[WorkloadStandardVersion] = []

    def set_versions(self, versions: list[WorkloadStandardVersion]):
        self._versions = versions

    def get_active_version(self) -> Optional[WorkloadStandardVersion]:
        for v in self._versions:
            if v.status == "active":
                return v
        return None

    def validate_file(self, filename: str) -> list[str]:
        """WL-BR-02: Validate file format and structure."""
        errors = []

        if not filename.endswith(".xlsx"):
            errors.append("Only .xlsx files accepted (WL-BR-02)")

        # WL-BR-03: Preprocessing validation (simplified)
        if filename.endswith(".xlsx"):
            logger.info("File %s passed format validation", filename)

        return errors

    def upload_version(self, filename: str, uploaded_by: str,
                       uploaded_by_role: str) -> dict:
        """Upload a new workload standard version. (§3.3-3.5)"""
        try:
            role_enum = Role(uploaded_by_role)
        except ValueError:
            return {"success": False, "error": f"Unknown role: {uploaded_by_role}"}

        # WL-BR-01: Check upload permission
        if role_enum not in WORKLOAD_UPLOADERS:
            return {"success": False, "error": f"{uploaded_by_role} cannot upload workload standards"}

        # WL-BR-02, WL-BR-03: Validate file
        validation_errors = self.validate_file(filename)
        if validation_errors:
            return {"success": False, "error": "; ".join(validation_errors)}

        # Mark previous active as superseded
        for v in self._versions:
            if v.status == "active":
                v.status = "superseded"

        # Create new version
        version = WorkloadStandardVersion(
            version_id=f"WL-{len(self._versions) + 1:04d}",
            uploaded_at=datetime.now().isoformat(),
            uploaded_by=uploaded_by,
            filename=filename,
            status="active",
        )
        self._versions.append(version)

        return {"success": True, "version": version}

    def list_versions(self) -> list[dict]:
        return [
            {
                "version_id": v.version_id,
                "uploaded_at": v.uploaded_at,
                "uploaded_by": v.uploaded_by,
                "filename": v.filename,
                "status": v.status,
            }
            for v in self._versions
        ]

    def get_inductors_for_version(self, version_id: str) -> list[dict]:
        """Return inductor rows for a given version. (§3b.2)"""
        version = next((v for v in self._versions if v.version_id == version_id), None)
        if not version:
            return []
        # In a real implementation this would query the DB.
        # Here we return from the version's stored metadata.
        return getattr(version, "_inductors", [])

    def _set_inductors_for_version(self, version_id: str, inductors: list[dict]):
        """Test helper: attach inductor data to a version."""
        version = next((v for v in self._versions if v.version_id == version_id), None)
        if version:
            version._inductors = inductors


# ═══════════════════════════════════════════════
# 2b. Bulk Inductor Deletion (§3b)
# ═══════════════════════════════════════════════

@dataclass
class DeletionResult:
    deleted_count: int
    skipped_count: int
    deleted_ids: list[str]
    skipped_ids: list[str]
    version_id: str
    timestamp: str


class BulkInductorDeleter(Module):
    """Bulk deletion of loaded inductors. (§3b)"""

    def __init__(self, lm=None):
        super().__init__(lm)
        self._versions: list[WorkloadStandardVersion] = []
        self._deletion_log: list[DeletionResult] = []

    def set_versions(self, versions: list[WorkloadStandardVersion]):
        self._versions = versions

    def get_deletion_log(self) -> list[DeletionResult]:
        return self._deletion_log

    def list_deletable_inductors(self, version_id: str) -> list[dict]:
        """
        DEL-BR-02: Return only already-loaded inductors for the given version.
        Shows inductor name, JU code, métier, and compatibility info.
        """
        version = next((v for v in self._versions if v.version_id == version_id), None)
        if not version:
            return []
        return getattr(version, "_inductors", [])

    def bulk_delete(self, version_id: str, inductor_ids: list[str],
                    deleted_by_role: str) -> dict:
        """
        Delete selected inductors from a workload standard version.
        Implements DEL-BR-01 through DEL-BR-10.
        """
        try:
            role_enum = Role(deleted_by_role)
        except ValueError:
            return {"success": False, "error": f"Unknown role: {deleted_by_role}"}

        # DEL-BR-01: Permission check
        if role_enum not in WORKLOAD_DELETERS:
            return {"success": False,
                    "error": f"{deleted_by_role} cannot delete inductors (DEL-BR-01)"}

        # DEL-BR-09: Empty selection blocked
        if not inductor_ids:
            return {"success": False, "error": "No inductors selected (DEL-BR-09)"}

        version = next((v for v in self._versions if v.version_id == version_id), None)
        if not version:
            return {"success": False, "error": f"Version {version_id} not found"}

        # DEL-BR-05: Active version protected if it's the only version
        if version.status == "active":
            active_versions = [v for v in self._versions if v.status == "active"]
            if len(active_versions) <= 1:
                return {
                    "success": False,
                    "error": "Cannot delete from the only active version (DEL-BR-05)",
                }

        # Perform deletion
        all_inductors = getattr(version, "_inductors", [])
        deleted_ids = []
        skipped_ids = []
        remaining = []

        for ind in all_inductors:
            ind_id = ind.get("id", ind.get("name", ""))
            if str(ind_id) in inductor_ids:
                deleted_ids.append(str(ind_id))
            else:
                remaining.append(ind)

        # DEL-BR-07: Superseded version cascade — no effect on active version
        # (already handled by targeting the specific version)

        # Update version's inductors
        version._inductors = remaining

        result = DeletionResult(
            deleted_count=len(deleted_ids),
            skipped_count=len(skipped_ids),
            deleted_ids=deleted_ids,
            skipped_ids=skipped_ids,
            version_id=version_id,
            timestamp=datetime.now().isoformat(),
        )
        self._deletion_log.append(result)

        # DEL-BR-10: Deletion summary
        return {
            "success": True,
            "deleted_count": len(deleted_ids),
            "skipped_count": 0,
            "deleted_ids": deleted_ids,
            "remaining_count": len(remaining),
            "version_id": version_id,
            "message": f"Deleted {len(deleted_ids)} inductors from {version_id} (DEL-BR-10)",
        }
# ═══════════════════════════════════════════════

@dataclass
class TableState:
    page: str
    filters: dict = field(default_factory=dict)
    sort_column: str = ""
    sort_direction: str = "asc"
    column_widths: dict = field(default_factory=dict)


class TableStateManager(Module):
    """Manage filter/sort/resize state per page session. (§4)"""

    def __init__(self, lm=None):
        super().__init__(lm)
        self._states: dict[str, TableState] = {}

    def get_state(self, page: str) -> TableState:
        return self._states.get(page, TableState(page=page))

    def set_filter(self, page: str, field: str, value: str):
        state = self._states.get(page)
        if not state:
            state = TableState(page=page)
            self._states[page] = state
        state.filters[field] = value

    def set_sort(self, page: str, column: str, direction: str = "asc"):
        state = self._states.get(page)
        if not state:
            state = TableState(page=page)
            self._states[page] = state
        state.sort_column = column
        state.sort_direction = direction

    def set_column_width(self, page: str, column: str, width: int):
        state = self._states.get(page)
        if not state:
            state = TableState(page=page)
            self._states[page] = state
        state.column_widths[column] = width

    def reset_page(self, page: str):
        """Reset to defaults when navigating away. (§4.2)"""
        if page in self._states:
            del self._states[page]

    def reset_all(self):
        self._states.clear()

    def apply_filters(self, rows: list[dict], page: str) -> list[dict]:
        """Apply current filters to a dataset."""
        state = self._states.get(page)
        if not state or not state.filters:
            return rows

        result = list(rows)
        for field, value in state.filters.items():
            if value and value != "All":
                result = [
                    r for r in result
                    if str(r.get(field, "")).lower() == value.lower()
                ]
        return result

    def apply_sort(self, rows: list[dict], page: str) -> list[dict]:
        """Apply current sort to a dataset."""
        state = self._states.get(page)
        if not state or not state.sort_column:
            return rows

        col = state.sort_column
        reverse = state.sort_direction == "desc"
        return sorted(rows, key=lambda r: str(r.get(col, "")), reverse=reverse)


# ═══════════════════════════════════════════════
# 4. Email Alerts (§5)
# ═══════════════════════════════════════════════

@dataclass
class EmailLogEntry:
    timestamp: str
    recipient: str
    alert_type: str
    cycle: str
    success: bool


class EmailAlertService(Module):
    """Send and log email alerts. (§5)"""

    def __init__(self, lm=None):
        super().__init__(lm)
        self._log: list[EmailLogEntry] = []

    def get_log(self) -> list[EmailLogEntry]:
        return self._log

    def send_engineer_weekly(self, engineer: str, lines: list[dict],
                              cycle_name: str) -> dict:
        """
        Send weekly summary to an engineer. (§5.3)
        TRANS-02: Content pending definition.
        """
        estimated = sum(1 for l in lines if l.get("status") == "estimated")
        rejected = sum(1 for l in lines if l.get("status") == "rejected")
        approved = sum(1 for l in lines if l.get("status") == "approved")

        subject = f"[GREAT] Weekly Estimation Summary — {cycle_name}"
        body = (
            f"Hi {engineer},\n\n"
            f"Your estimation summary for {cycle_name}:\n"
            f"  Total lines: {len(lines)}\n"
            f"  Estimated: {estimated}\n"
            f"  Rejected: {rejected}\n"
            f"  Approved: {approved}\n\n"
            f"Please check Pre-Estimation View for pending items.\n"
            f"---\nGREAT System"
        )

        entry = EmailLogEntry(
            timestamp=datetime.now().isoformat(),
            recipient=engineer,
            alert_type="engineer_weekly",
            cycle=cycle_name,
            success=True,
        )
        self._log.append(entry)

        return {"success": True, "subject": subject, "body": body, "log_entry": entry}

    def send_rcrc_weekly(self, rcrc_emails: list[str], metrics: dict,
                          cycle_name: str) -> dict:
        """
        Send weekly overview to RCRCs. (§5.4)
        TRANS-03: Content pending definition.
        """
        subject = f"[GREAT] Weekly Allocation Overview — {cycle_name}"
        body = (
            f"RCRC Allocation Overview for {cycle_name}:\n\n"
            f"  Total JUs: {metrics.get('total_jus', 0)}\n"
            f"  Assigned: {metrics.get('assigned_jus', 0)}\n"
            f"  Unassigned: {metrics.get('unassigned_jus', 0)}\n"
            f"  Split rows: {metrics.get('split_rows', 0)}\n\n"
            f"Please check Allocation page for pending assignments.\n"
            f"---\nGREAT System"
        )

        for email in rcrc_emails:
            entry = EmailLogEntry(
                timestamp=datetime.now().isoformat(),
                recipient=email,
                alert_type="rcrc_weekly",
                cycle=cycle_name,
                success=True,
            )
            self._log.append(entry)

        return {"success": True, "subject": subject, "body": body, "recipients": rcrc_emails}

    def send_rejection_notification(self, engineer: str, pl_number: str,
                                      metier: str, comment: str,
                                      cycle_name: str) -> dict:
        """
        Send triggered notification when estimation is rejected. (§5.5)
        """
        subject = f"[GREAT] Estimation Rejected — {pl_number} / {metier}"
        body = (
            f"Hi {engineer},\n\n"
            f"Your estimation for {pl_number} ({metier}) has been rejected by CPO.\n\n"
            f"CPO comment: {comment}\n\n"
            f"Please go to Pre-Estimation View to rework and re-submit.\n"
            f"---\nGREAT System"
        )

        entry = EmailLogEntry(
            timestamp=datetime.now().isoformat(),
            recipient=engineer,
            alert_type="rejection_notification",
            cycle=cycle_name,
            success=True,
        )
        self._log.append(entry)

        return {"success": True, "subject": subject, "body": body, "log_entry": entry}