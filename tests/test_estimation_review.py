"""
GREAT Estimation Review — Tests.

Covers:
  1. Spec data structures (permissions, eligibility, approval maps)
  2. Module unit tests (all pure Python)
  3. Pipeline integration
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from great_sdd.specs.pre_estimation_specs import (
    LineStatus, Role,
)
from great_sdd.specs.estimation_review_specs import (
    ESTIMATION_REVIEW_PERMISSIONS,
    SEND_ELIGIBLE_STATUSES,
    ENGINEER_APPROVAL_MAP,
    CPO_APPROVAL_MAP,
    process_hvt_callback,
    HVTCallback,
    ESTIMATION_REVIEW_RULES,
    ALL_BUSINESS_RULES,
    PENDING_DEFINITIONS,
    ESTIMATION_REVIEW_GRID_COLUMNS,
)
from great_sdd.modules.estimation_review import (
    EstimationReviewPermissionChecker,
    ApprovalColumnDeriver,
    SendEligibilityChecker,
    HVTCallbackProcessor,
    CSVExporter,
    HVTPayloadGenerator,
)


# ═══════════════════════════════════════════════════════════
# 1. Spec Data Structure Tests
# ═══════════════════════════════════════════════════════════

class TestEstimationReviewPermissions:
    """Spec §2: Role Permissions"""

    def test_all_roles_have_permissions(self):
        """Every role has a permission entry for Estimation Review."""
        for role in Role:
            assert role in ESTIMATION_REVIEW_PERMISSIONS, f"{role} missing"

    def test_pmo_can_send_to_hvt(self):
        """PMO can send to HVT."""
        assert ESTIMATION_REVIEW_PERMISSIONS[Role.PMO].can_send_to_hvt is True

    def test_admin_can_send_to_hvt(self):
        """Admin can send to HVT."""
        assert ESTIMATION_REVIEW_PERMISSIONS[Role.ADMIN].can_send_to_hvt is True

    def test_engineer_cannot_send_to_hvt(self):
        """Engineer cannot send to HVT."""
        assert ESTIMATION_REVIEW_PERMISSIONS[Role.ENGINEER].can_send_to_hvt is False

    def test_cpo_cannot_send_to_hvt(self):
        """CPO cannot send to HVT."""
        assert ESTIMATION_REVIEW_PERMISSIONS[Role.CPO].can_send_to_hvt is False

    def test_engineer_sees_only_own_rows(self):
        """Engineer scope is own_rows_only."""
        assert ESTIMATION_REVIEW_PERMISSIONS[Role.ENGINEER].scope == "own_rows_only"

    def test_all_roles_can_view(self):
        """All roles can view Estimation Review."""
        for role in Role:
            assert ESTIMATION_REVIEW_PERMISSIONS[role].can_view is True

    def test_all_roles_can_export_csv(self):
        """All roles can export CSV."""
        for role in Role:
            assert ESTIMATION_REVIEW_PERMISSIONS[role].can_export_csv is True


class TestSendEligibility:
    """Spec §6: Send to HVT Eligibility"""

    def test_only_estimated_is_eligible(self):
        """Only status=Estimated is eligible for sending."""
        assert SEND_ELIGIBLE_STATUSES == {LineStatus.ESTIMATED}

    def test_other_statuses_not_eligible(self):
        """Other statuses are not in the eligible set."""
        for status in LineStatus:
            if status != LineStatus.ESTIMATED:
                assert status not in SEND_ELIGIBLE_STATUSES


class TestApprovalColumns:
    """Spec §5: Approval Column Derivation"""

    def test_engineer_approval_map_covers_all_statuses(self):
        """Every status has an engineer approval display value."""
        for status in LineStatus:
            assert status in ENGINEER_APPROVAL_MAP, f"{status} missing"

    def test_cpo_approval_map_covers_all_statuses(self):
        """Every status has a CPO approval display value."""
        for status in LineStatus:
            assert status in CPO_APPROVAL_MAP, f"{status} missing"

    def test_estimated_shows_engineer_check(self):
        """Estimated shows ✓ for engineer approval."""
        assert ENGINEER_APPROVAL_MAP[LineStatus.ESTIMATED] == "✓"

    def test_estimated_shows_not_yet_sent_for_cpo(self):
        """Estimated shows '— (not yet sent)' for CPO approval."""
        assert CPO_APPROVAL_MAP[LineStatus.ESTIMATED] == "— (not yet sent)"

    def test_sent_shows_pending_for_cpo(self):
        """Sent shows '⏳ Pending' for CPO approval."""
        assert CPO_APPROVAL_MAP[LineStatus.SENT] == "⏳ Pending"

    def test_approved_shows_approved_for_cpo(self):
        """Approved shows '✓ Approved' for CPO approval."""
        assert CPO_APPROVAL_MAP[LineStatus.APPROVED] == "✓ Approved"

    def test_modification_requested_shows_rejected_for_cpo(self):
        """Modification Requested shows '✗ Rejected' for CPO approval."""
        assert CPO_APPROVAL_MAP[LineStatus.MODIFICATION_REQUESTED] == "✗ Rejected"

    def test_todo_shows_dash_for_both(self):
        """To do shows — for both approvals."""
        assert ENGINEER_APPROVAL_MAP[LineStatus.TODO] == "—"
        assert CPO_APPROVAL_MAP[LineStatus.TODO] == "—"


class TestHVTCallbackProcessing:
    """Spec §7: HVT Callback Handling"""

    def test_approval_transitions_to_approved(self):
        """Approved callback → target_status=approved."""
        result = process_hvt_callback(HVTCallback("PL-001", "H-DESIGN", True))
        assert result["target_status"] == LineStatus.APPROVED
        assert result["comment"] == ""
        assert result["notify_engineer"] is False

    def test_rejection_transitions_to_modification_requested(self):
        """Rejected callback → target_status=Modification Requested + comment + notify."""
        result = process_hvt_callback(
            HVTCallback("PL-001", "H-DESIGN", False, "Insufficient detail")
        )
        assert result["target_status"] == LineStatus.MODIFICATION_REQUESTED
        assert result["comment"] == "Insufficient detail"
        assert result["notify_engineer"] is True

    def test_approval_no_comment(self):
        """Approval callback with empty comment."""
        result = process_hvt_callback(
            HVTCallback("PL-002", "H-SOFTWARE", True, "")
        )
        assert result["target_status"] == LineStatus.APPROVED
        assert result["comment"] == ""


class TestEstimationReviewBusinessRules:
    """Spec §10: Business Rules"""

    def test_ten_erev_rules(self):
        """There are exactly 10 Estimation Review business rules."""
        assert len(ESTIMATION_REVIEW_RULES) == 10

    def test_total_rules_30(self):
        """20 (Pre-Estimation, was 19 + BR-20) + 10 (ER) = 30 total rules."""
        assert len(ALL_BUSINESS_RULES) == 30

    def test_read_only_rule_exists(self):
        """ERev-BR-01: Read-only page rule exists."""
        assert any("Read-only page" in r["rule"] for r in ESTIMATION_REVIEW_RULES)

    def test_sent_irreversible_rule(self):
        """ERev-BR-02: Sent irreversible rule exists."""
        assert any("irreversible" in r["rule"] for r in ESTIMATION_REVIEW_RULES)


class TestPendingDefinitions:
    """Spec §12: Pending Definitions"""

    def test_three_pending_definitions(self):
        """There are exactly 3 pending definitions for ER."""
        assert len(PENDING_DEFINITIONS) == 3

    def test_erev01_is_blocking(self):
        """ERev-01 is blocking."""
        erev01 = [p for p in PENDING_DEFINITIONS if p["id"] == "ERev-01"]
        assert len(erev01) == 1
        assert erev01[0]["blocking"] is True

    def test_erev02_is_blocking(self):
        """ERev-02 is blocking."""
        erev02 = [p for p in PENDING_DEFINITIONS if p["id"] == "ERev-02"]
        assert len(erev02) == 1
        assert erev02[0]["blocking"] is True

    def test_erev03_is_not_blocking(self):
        """ERev-03 is not blocking (fallback exists)."""
        erev03 = [p for p in PENDING_DEFINITIONS if p["id"] == "ERev-03"]
        assert len(erev03) == 1
        assert erev03[0]["blocking"] is False


# ═══════════════════════════════════════════════════════════
# 2. Module Unit Tests
# ═══════════════════════════════════════════════════════════

class TestEstimationReviewPermissionCheckerModule:
    """Module tests for ERevPermissionChecker."""

    def setup_method(self):
        self.checker = EstimationReviewPermissionChecker()

    def test_pmo_can_send_to_hvt(self):
        result = self.checker.forward(role="PMO", action="send_to_hvt")
        assert result["allowed"] is True

    def test_admin_can_send_to_hvt(self):
        result = self.checker.forward(role="Admin", action="send_to_hvt")
        assert result["allowed"] is True

    def test_engineer_cannot_send_to_hvt(self):
        result = self.checker.forward(role="Engineer", action="send_to_hvt")
        assert result["allowed"] is False

    def test_cpo_cannot_send_to_hvt(self):
        result = self.checker.forward(role="CPO", action="send_to_hvt")
        assert result["allowed"] is False

    def test_all_roles_can_view(self):
        for role_name in ["Admin", "Engineer", "PMO", "RCRC", "CPO"]:
            result = self.checker.forward(role=role_name, action="view")
            assert result["allowed"] is True, f"{role_name} should be able to view"

    def test_invalid_role(self):
        result = self.checker.forward(role="Invalid", action="view")
        assert result["allowed"] is False


class TestApprovalColumnDeriverModule:
    """Module tests for ApprovalColumnDeriver."""

    def setup_method(self):
        self.deriver = ApprovalColumnDeriver()

    def test_derives_estimated_row(self):
        row = {"id": "PL-001", "status": "estimated", "metier": "H-DESIGN"}
        derived = self.deriver.derive_row(row)
        assert derived["engineer_approval"] == "✓"
        assert derived["cpo_approval"] == "— (not yet sent)"

    def test_derives_sent_row(self):
        row = {"id": "PL-001", "status": "sent"}
        derived = self.deriver.derive_row(row)
        assert derived["engineer_approval"] == "✓"
        assert derived["cpo_approval"] == "⏳ Pending"

    def test_derives_approved_row(self):
        row = {"id": "PL-001", "status": "approved"}
        derived = self.deriver.derive_row(row)
        assert derived["engineer_approval"] == "✓"
        assert derived["cpo_approval"] == "✓ Approved"

    def test_derives_modification_requested_row(self):
        row = {"id": "PL-001", "status": "modification_requested"}
        derived = self.deriver.derive_row(row)
        assert derived["engineer_approval"] == "—"
        assert derived["cpo_approval"] == "✗ Rejected"

    def test_derives_preserves_original_fields(self):
        row = {"id": "PL-001", "status": "estimated", "total_fte": 1.5, "assignee": "Ana"}
        derived = self.deriver.derive_row(row)
        assert derived["id"] == "PL-001"
        assert derived["total_fte"] == 1.5
        assert derived["assignee"] == "Ana"


class TestSendEligibilityCheckerModule:
    """Module tests for SendEligibilityChecker."""

    def setup_method(self):
        self.checker = SendEligibilityChecker()

    def test_estimated_is_eligible_for_pmo(self):
        result = self.checker.forward(status="estimated", role="PMO")
        assert result["eligible"] is True

    def test_draft_not_eligible(self):
        result = self.checker.forward(status="draft", role="PMO")
        assert result["eligible"] is False

    def test_to_do_not_eligible(self):
        result = self.checker.forward(status="to_do", role="PMO")
        assert result["eligible"] is False

    def test_engineer_not_eligible_even_if_estimated(self):
        """Engineer cannot send even if status is Estimated."""
        result = self.checker.forward(status="estimated", role="Engineer")
        assert result["eligible"] is False

    def test_find_eligible_rows(self):
        rows = [
            {"id": "PL-001", "status": "estimated"},
            {"id": "PL-002", "status": "draft"},
            {"id": "PL-003", "status": "estimated"},
            {"id": "PL-004", "status": "to_do"},
        ]
        eligible, skipped = self.checker.find_eligible_rows(rows, "PMO")
        assert len(eligible) == 2  # PL-001 and PL-003
        assert len(skipped) == 2   # PL-002 and PL-004

    def test_no_eligible_rows(self):
        rows = [
            {"id": "PL-001", "status": "draft"},
            {"id": "PL-002", "status": "to_do"},
        ]
        eligible, skipped = self.checker.find_eligible_rows(rows, "PMO")
        assert len(eligible) == 0
        assert len(skipped) == 2


class TestHVTCallbackProcessorModule:
    """Module tests for HVTCallbackProcessor."""

    def setup_method(self):
        self.processor = HVTCallbackProcessor()

    def test_approval(self):
        result = self.processor.forward(
            project_line="PL-001", metier="H-DESIGN", approved=True
        )
        assert result["target_status"] == "approved"
        assert result["transition_valid"] is True

    def test_rejection(self):
        result = self.processor.forward(
            project_line="PL-001", metier="H-DESIGN", approved=False, comment="Too optimistic"
        )
        assert result["target_status"] == "modification_requested"
        assert result["transition_valid"] is True


class TestCSVExporterModule:
    """Module tests for CSVExporter."""

    def setup_method(self):
        self.exporter = CSVExporter()

    def test_export_empty(self):
        result = self.exporter.forward(rows_json="[]", mode="all_filtered")
        assert result["csv_content"] == ""
        assert result["row_count"] == "0"

    def test_export_simple_rows(self):
        rows = [{"id": "PL-001", "name": "Auth API", "metier": "H-DESIGN",
                 "total_fte": 1.5, "total_bh": 0, "total_km": 0}]
        result = self.exporter.forward(
            rows_json=json.dumps(rows), mode="all_filtered",
            yearly_keys_json=json.dumps(["2024", "2025"]),
        )
        assert result["row_count"] == "1"
        assert "PL-001" in result["csv_content"]
        assert "Auth API" in result["csv_content"]
        assert "H-DESIGN" in result["csv_content"]

    def test_export_with_yearly_columns(self):
        rows = [{"id": "PL-001", "name": "Auth API", "metier": "H-DESIGN",
                 "total_fte": 1.5, "total_bh": 0, "total_km": 0}]
        result = self.exporter.forward(
            rows_json=json.dumps(rows), mode="all_filtered",
            yearly_keys_json=json.dumps(["2024", "2025"]),
        )
        assert result["row_count"] == "1"
        assert "FTE 2024" in result["csv_content"]
        assert "BH 2025" in result["csv_content"]

    def test_export_with_inductors(self):
        rows = [{
            "id": "PL-001", "name": "Auth API", "metier": "H-DESIGN",
            "inductors": [
                {
                    "name": "API endpoints",
                    "job_units": [
                        {"short_name": "API-DEV", "description": "API Dev",
                         "fmm": "FMM001", "fte": 1.0, "bh": 0, "km": 0},
                    ],
                }
            ],
        }]
        result = self.exporter.forward(rows_json=json.dumps(rows), mode="selected")
        assert result["row_count"] == "1"
        assert "API-DEV" in result["csv_content"]
        assert "FMM001" in result["csv_content"]


# ═══════════════════════════════════════════════════════════
# 3. Pipeline Tests
# ═══════════════════════════════════════════════════════════

class TestEstimationReviewPipeline:
    """Integration tests for the Estimation Review pipeline."""

    def test_pipeline_imports(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
            EstimationReviewContext,
        )
        assert EstimationReviewPipeline is not None
        assert EstimationReviewContext is not None

    def test_pipeline_can_be_instantiated(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        assert pipeline is not None

    def test_pipeline_rejects_cpo(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        ctx = pipeline.forward(role="CPO", grid_rows=[])
        assert len(ctx.errors) == 0  # CPO can view

    def test_pipeline_detects_eligible_rows(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        rows = [
            {"id": "PL-001", "status": "estimated", "metier": "H-DESIGN"},
            {"id": "PL-002", "status": "draft", "metier": "H-DESIGN"},
        ]
        ctx = pipeline.forward(role="PMO", grid_rows=rows)
        assert ctx.has_eligible_rows is True
        assert len(ctx.eligible_rows) == 1

    def test_pipeline_adds_derived_columns(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        rows = [
            {"id": "PL-001", "status": "estimated", "metier": "H-DESIGN"},
            {"id": "PL-002", "status": "approved", "metier": "H-SOFTWARE"},
        ]
        ctx = pipeline.forward(role="PMO", grid_rows=rows)
        assert len(ctx.derived_columns) == 2
        assert ctx.derived_columns[0]["engineer_approval"] == "✓"
        assert ctx.derived_columns[1]["cpo_approval"] == "✓ Approved"

    def test_send_to_hvt(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        rows = [
            {"id": "PL-001", "status": "estimated", "metier": "H-DESIGN",
             "yearly_aggregation": {"2024": {"fte": 1.0, "bh": 0, "km": 0}}},
            {"id": "PL-002", "status": "draft", "metier": "H-DESIGN"},
        ]
        result = pipeline.send_to_hvt("PMO", rows)
        assert result["success"] is True
        assert result["sent_count"] == 1  # Only PL-001
        assert result["skipped_count"] == 1
        assert len(result["payloads"]) == 1
        payload = json.loads(result["payloads"][0])
        assert payload["project_line"] == "PL-001"

    def test_engineer_cannot_send_to_hvt(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        result = pipeline.send_to_hvt("Engineer", [{"id": "PL-001", "status": "estimated"}])
        assert result["success"] is False
        assert result["sent_count"] == 0

    def test_process_hvt_callback_approval(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        result = pipeline.process_callback("PL-001", "H-DESIGN", True)
        assert result["target_status"] == "approved"
        assert result["transition_valid"] is True

    def test_process_hvt_callback_rejection(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        result = pipeline.process_callback("PL-001", "H-DESIGN", False, "Rework needed")
        assert result["target_status"] == "modification_requested"
        assert result["transition_valid"] is True
        assert result["notify_engineer"] is True

    def test_export_csv_from_pipeline(self):
        from great_sdd.pipeline.estimation_review_pipeline import (
            EstimationReviewPipeline,
        )
        pipeline = EstimationReviewPipeline()
        rows = [{"id": "PL-001", "name": "Test", "metier": "H-DESIGN",
                 "total_fte": 1.0, "total_bh": 0, "total_km": 0}]
        result = pipeline.export_csv(rows, "all_filtered")
        assert result["row_count"] == "1"
        assert "PL-001" in result["csv_content"]