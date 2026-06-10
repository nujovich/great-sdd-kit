"""Generate GREAT golden conformance fixtures from the deterministic oracle.

Every probe runs against modules constructed with TripwireLM — if a covered
path calls the LM, generation aborts loudly (NonDeterministicError). Probes
never touch timestamps or randomness, so fixtures are byte-stable.

Rules with no pure-function surface (UI / policy / persistence) are NOT probed
here; they are documented in exclusions.NO_FUNCTION_SURFACE_RULES. LM-only
capabilities are documented in exclusions.NON_DETERMINISTIC_RULES.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sdd.base_conformance import (
    Probe, TripwireLM, generate_fixtures, write_fixture_file, read_version,
    canonical_json,
)
from great_sdd.conformance.rule_inventory import (
    business_rule_ids, pending_marker_ids, rule_count)
from great_sdd.conformance.exclusions import (
    NON_DETERMINISTIC_RULES, NO_FUNCTION_SURFACE_RULES)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

TRIP = TripwireLM()


# ── Pre-Estimation ──

def _pre_estimation_probes() -> list[Probe]:
    from great_sdd.specs.pre_estimation_specs import are_lines_compatible
    from great_sdd.modules.pre_estimation import (
        PermissionChecker, StatusTransitionValidator, EstimationCalculator,
        SaveValidator, MonthDistributor, InductorSelector, CustomJUPermissionChecker)

    def compat(inp):
        return {"is_compatible": are_lines_compatible(inp["lines"])}

    return [
        # BR-06 / BR-07 — decision via pure function (LM explanation excluded by design).
        Probe(["BR-06", "BR-07"], "line_compatibility", compat, cases=[
            {"lines": [{"organ_type": "A"}, {"organ_type": "A"}]},
            {"lines": [{"organ_type": "A"}, {"organ_type": "B"}]},
            {"lines": [{"injection_system": None}, {"injection_system": None}]},
            {"lines": [{"injection_system": None}, {"injection_system": "X"}]},
        ]),
        # BR-02 / BR-04 / BR-15 / BR-16 / BR-17 / ERev-BR-03 — state machine
        # (approved terminal == ERev-BR-03; sent locked == BR-16).
        Probe(["BR-02", "BR-04", "BR-15", "BR-16", "BR-17", "ERev-BR-03"], "status_transition",
              lambda inp: StatusTransitionValidator(TRIP).forward(**inp), cases=[
            {"current_status": "to_do", "target_status": "draft", "has_saved_draft_in_session": False},
            {"current_status": "draft", "target_status": "draft", "has_saved_draft_in_session": False},
            {"current_status": "draft", "target_status": "estimated", "has_saved_draft_in_session": False},
            {"current_status": "draft", "target_status": "estimated", "has_saved_draft_in_session": True},
            {"current_status": "sent", "target_status": "draft", "has_saved_draft_in_session": True},
            {"current_status": "approved", "target_status": "draft", "has_saved_draft_in_session": True},
        ]),
        # BR-08 / BR-11 / BR-12 — save validation.
        Probe(["BR-08", "BR-11", "BR-12"], "save_validation",
              lambda inp: SaveValidator(TRIP).forward(**inp), cases=[
            {"line_json": json.dumps({"sp_date": "", "status": "to_do", "inductors": []}),
             "save_type": "draft", "has_saved_draft_in_session": False},
            {"line_json": json.dumps({"sp_date": "2026-01-01", "status": "to_do",
             "inductors": [{"selected_cran": "Simple"}]}),
             "save_type": "draft", "has_saved_draft_in_session": False},
            {"line_json": json.dumps({"sp_date": "2026-01-01", "status": "to_do",
             "inductors": [{"is_custom": True}]}),
             "save_type": "draft", "has_saved_draft_in_session": False},
        ]),
        # BR-13 — estimation formula incl. zero occurrence.
        Probe(["BR-13"], "estimation_calc",
              lambda inp: EstimationCalculator(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"short_name": "A", "variable": 2.0, "occurrence": 3, "fixed": 1.0, "unit_type": "man_day"},
                {"short_name": "B", "variable": 5.0, "occurrence": 0, "fixed": 0.0, "unit_type": "bench_hours"}])},
        ]),
        # BR-03 — permission scope (Estimated read-only enforced via role edit gating + scope).
        Probe(["BR-03"], "permission_check",
              lambda inp: PermissionChecker(TRIP).forward(**inp), cases=[
            {"role": "Engineer", "line_assignee": "u1", "current_user": "u1", "action": "edit"},
            {"role": "Engineer", "line_assignee": "u2", "current_user": "u1", "action": "edit"},
            {"role": "CPO", "line_assignee": "u1", "current_user": "u1", "action": "view"},
        ]),
        # BR-12 — inductor selection deterministic surface (keyword/fallback).
        Probe(["BR-12"], "inductor_selection",
              lambda inp: InductorSelector(TRIP).forward(**inp), cases=[
            {"line_description": "complex REST API", "metier": "Backend", "available_inductors_json": "[]"},
            {"line_description": "", "metier": "Frontend", "available_inductors_json": "[]"},
            {"line_description": "x", "metier": "Nonexistent", "available_inductors_json": "[]"},
        ]),
        # BR-08 — month distribution (deterministic split from SP date).
        Probe(["BR-08"], "month_distribution",
              lambda inp: MonthDistributor(TRIP).forward(**inp), cases=[
            {"total_fte": "12.0", "total_bh": "0.0", "total_km": "0.0",
             "sp_date": "2026-01-01", "project_duration_months": "12"},
        ]),
        # BR-20 — custom JU permissions.
        Probe(["BR-20"], "custom_ju_permission",
              lambda inp: CustomJUPermissionChecker().forward(**inp), cases=[
            {"role": "Engineer"}, {"role": "PMO"}, {"role": "Admin"},
            {"role": "RCRC"}, {"role": "CPO"}]),
    ]


# ── Estimation Review ──

def _estimation_review_probes() -> list[Probe]:
    from great_sdd.modules.estimation_review import (
        EstimationReviewPermissionChecker, ApprovalColumnDeriver,
        SendEligibilityChecker, HVTCallbackProcessor)

    return [
        # ERev-BR-04 — only Estimated rows eligible; role gates send.
        Probe(["ERev-BR-04"], "send_eligibility",
              lambda inp: SendEligibilityChecker(TRIP).forward(**inp), cases=[
            {"status": "estimated", "role": "PMO"},
            {"status": "draft", "role": "PMO"},
            {"status": "approved", "role": "PMO"},
            {"status": "estimated", "role": "Engineer"},
        ]),
        # ERev-BR-08 / BR-05 — approval columns fully status-derived (no gestures).
        Probe(["ERev-BR-08", "BR-05"], "approval_columns",
              lambda inp: ApprovalColumnDeriver(TRIP).forward(**inp), cases=[
            {"status": "to_do"}, {"status": "draft"}, {"status": "estimated"},
            {"status": "sent"}, {"status": "approved"}, {"status": "rejected"}]),
        # ERev-BR-02 / ERev-BR-10 — CPO approve/reject only via HVT callback; sent is terminal-by-HVT.
        Probe(["ERev-BR-02", "ERev-BR-10"], "hvt_callback",
              lambda inp: HVTCallbackProcessor(TRIP).forward(**inp), cases=[
            {"project_line": "PL1", "metier": "Backend", "approved": True, "comment": ""},
            {"project_line": "PL1", "metier": "Backend", "approved": False, "comment": "redo"}]),
        # ERev-BR-04 — role permissions for send/export in Estimation Review.
        Probe(["ERev-BR-04"], "er_permission",
              lambda inp: EstimationReviewPermissionChecker(TRIP).forward(**inp), cases=[
            {"role": "PMO", "action": "send_to_hvt"},
            {"role": "Engineer", "action": "send_to_hvt"},
            {"role": "RCRC", "action": "export_csv"}]),
    ]


# ── Allocation ──

def _allocation_probes() -> list[Probe]:
    from great_sdd.modules.allocation import (
        AllocationEligibilityFilter, AllocationRuleMatcher, KECalculator,
        AllocationSaveValidator, DiversityDropdownHandler, BulkAssigner,
        SplitAllocationHandler, JUMetierRouter)

    def metier_routing(inp):
        r = JUMetierRouter()
        return {"resolved_metier": r.resolve(inp["unit_type"], inp["project_line_metier"])}

    return [
        # ALLOC-BR-01 — only Approved (PL, Métier) pairs.
        Probe(["ALLOC-BR-01"], "alloc_eligibility",
              lambda inp: AllocationEligibilityFilter(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"ju_code": "a", "status": "approved"},
                {"ju_code": "b", "status": "estimated"},
                {"ju_code": "c", "status": "approved"}])}]),
        # ALLOC-BR-02 — rule engine skips rows that already have a societe.
        Probe(["ALLOC-BR-02"], "alloc_rule_match",
              lambda inp: AllocationRuleMatcher(lm=TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"ju_code": "a", "metier": "Backend"},
                {"ju_code": "b", "metier": "Backend", "societe": "Already S.L."}]),
             "rules_json": json.dumps([
                {"id": "R1", "fields": {"metier": "Backend"}, "societe": "Horse Spain S.L.", "cost_type": "FTE"}])}]),
        # ALLOC-BR-04 — K€ recalculated from FTE via rate tables.
        Probe(["ALLOC-BR-04"], "alloc_ke_calc",
              lambda inp: KECalculator(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"ju_code": "a", "cost_type": "FTE", "societe": "Horse Spain S.L.-Valladolid",
                 "fte_yearly": {"2026": 1.0, "2027": 2.0}}])}]),
        # ALLOC-BR-06 / ALLOC-BR-07 / ALLOC-BR-13 — save gating by cost type + societe.
        Probe(["ALLOC-BR-06", "ALLOC-BR-07", "ALLOC-BR-13"], "alloc_save_validation",
              lambda inp: AllocationSaveValidator(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"ju_code": "tsa1", "cost_type": "TSA", "societe": ""},
                {"ju_code": "tc1", "cost_type": "TC", "societe": ""},
                {"ju_code": "fte1", "cost_type": "FTE", "societe": ""},
                {"ju_code": "ok1", "cost_type": "FTE", "societe": "Horse Spain S.L.-Valladolid"}])}]),
        # ALLOC-BR-08 — diversity dropdown is non-blocking (flags only).
        Probe(["ALLOC-BR-08"], "alloc_diversity",
              lambda inp: DiversityDropdownHandler(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"ju_code": "a", "metier": "Backend"}])}]),
        # ALLOC-BR-09 / ALLOC-BR-10 — bulk assign overwrites societe, never cost type.
        Probe(["ALLOC-BR-09", "ALLOC-BR-10"], "alloc_bulk_assign",
              lambda inp: BulkAssigner(TRIP).forward(**inp), cases=[
            {"rows_json": json.dumps([
                {"ju_code": "a", "societe": "Old S.L.", "cost_type": "FTE"},
                {"ju_code": "b", "cost_type": "TSA"}]),
             "societe": "Horse Spain S.L."}]),
        # ALLOC-BR-11 — split percentages must sum to 100%.
        Probe(["ALLOC-BR-11"], "alloc_split",
              lambda inp: SplitAllocationHandler(TRIP).forward(**inp), cases=[
            {"ju_json": json.dumps({"ju_id": "j1", "fte_yearly": {"2026": 1.0}}),
             "splits_json": json.dumps([{"societe": "A", "percentage": 60},
                                        {"societe": "B", "percentage": 40}])},
            {"ju_json": json.dumps({"ju_id": "j1", "fte_yearly": {"2026": 1.0}}),
             "splits_json": json.dumps([{"societe": "A", "percentage": 60},
                                        {"societe": "B", "percentage": 30}])}]),
        # ALLOC-BR-17 — BH/KM -> H-TESTING; else -> project line métier.
        Probe(["ALLOC-BR-17"], "alloc_ju_metier_routing", metier_routing, cases=[
            {"unit_type": "Bench Hours", "project_line_metier": "Backend"},
            {"unit_type": "Kilometres", "project_line_metier": "Frontend"},
            {"unit_type": "Man Day", "project_line_metier": "Backend"}]),
    ]


# ── Final Review ──

def _final_review_probes() -> list[Probe]:
    from great_sdd.modules.final_review import (
        FinalReviewPermissionChecker, FinalReviewEligibilityFilter,
        CSVGlobalExporter, Stage3Sender)

    return [
        # FR-BR-03 — only Approved (PL, Métier) pairs.
        Probe(["FR-BR-03"], "fr_eligibility",
              lambda inp: FinalReviewEligibilityFilter(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"ju_code": "a", "status": "approved"},
                {"ju_code": "b", "status": "sent"}])}]),
        # FR-BR-04 — all roles see all lines (no scoping).
        Probe(["FR-BR-04"], "fr_permission",
              lambda inp: FinalReviewPermissionChecker(TRIP).forward(**inp), cases=[
            {"role": "Engineer", "action": "view"},
            {"role": "RCRC", "action": "view"},
            {"role": "PMO", "action": "send_stage3"},
            {"role": "Engineer", "action": "send_stage3"}]),
        # FR-BR-06 / FR-BR-07 / FR-BR-08 — Stage 3 non-blocking, re-sendable, whole-cycle.
        Probe(["FR-BR-06", "FR-BR-07", "FR-BR-08"], "fr_stage3",
              lambda inp: Stage3Sender(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"pl_number": "PL1", "societe": "", "total_fte": 1.0, "total_ke": 0.0}]),
             "confirmed": False},
            {"job_units_json": json.dumps([
                {"pl_number": "PL1", "societe": "", "total_fte": 1.0, "total_ke": 0.0}]),
             "confirmed": True},
            {"job_units_json": json.dumps([
                {"pl_number": "PL1", "societe": "Horse Spain S.L.", "total_fte": 2.0, "total_ke": 200.0}]),
             "confirmed": False}]),
        # FR-BR-10 — flat CSV, one row per JU.
        Probe(["FR-BR-10"], "fr_csv",
              lambda inp: CSVGlobalExporter(TRIP).forward(**inp), cases=[
            {"job_units_json": json.dumps([
                {"pl_number": "PL1", "ju_code": "a", "total_fte": 1.0},
                {"pl_number": "PL1", "ju_code": "b", "total_fte": 2.0}])}]),
    ]


# ── Management View ──

def _management_view_probes() -> list[Probe]:
    from great_sdd.modules.management_view import (
        ManagementAccessChecker, PieChartBuilder, MetierFilter)

    def counts(inp):
        return {"counts": MetierFilter(TRIP).count_by_status(inp["pairs"])}

    def metier_filter(inp):
        return {"filtered": MetierFilter(TRIP).forward(inp["pairs"], inp.get("metier", "All"))}

    return [
        # MGMT-BR-01 — PMO/Admin only.
        Probe(["MGMT-BR-01"], "mgmt_access",
              lambda inp: ManagementAccessChecker(TRIP).forward(**inp), cases=[
            {"role": "Admin"}, {"role": "PMO"}, {"role": "Engineer"},
            {"role": "RCRC"}, {"role": "CPO"}]),
        # MGMT-BR-02 — charts count (PL, Métier) pairs.
        Probe(["MGMT-BR-02"], "mgmt_pie",
              lambda inp: PieChartBuilder(TRIP).forward(**inp), cases=[
            {"pairs_by_status": {"to_do": 2, "approved": 3, "estimated": 1}}]),
        # MGMT-BR-03 — full status model (all 6 statuses present).
        Probe(["MGMT-BR-03"], "mgmt_status_model", counts, cases=[
            {"pairs": [{"status": "approved"}, {"status": "approved"}, {"status": "draft"}]}]),
        # MGMT-BR-04 — H-NP / H-PROJECT excluded.
        Probe(["MGMT-BR-04"], "mgmt_metier_filter", metier_filter, cases=[
            {"pairs": [{"metier": "Backend", "status": "approved"},
                       {"metier": "H-NP", "status": "approved"},
                       {"metier": "H-PROJECT", "status": "draft"}], "metier": "All"}]),
    ]


# ── Transversal ──

def _transversal_probes() -> list[Probe]:
    from great_sdd.specs.transversal_specs import EstimationCycle, WorkloadStandardVersion
    from great_sdd.modules.transversal import (
        CycleManager, WorkloadStandardManager, BulkInductorDeleter,
        TableStateManager, EmailAlertService)

    def cycle_create(inp):
        mgr = CycleManager(TRIP)
        mgr.set_cycles([EstimationCycle(name="C1", start_date="2026-01-01", active=True)])
        res = mgr.create_cycle(inp["name"], inp["start_date"], inp["role"])
        return {"deactivated_previous": res.get("deactivated_previous"),
                "cycles": mgr.list_cycles()}

    def cycle_reactivation(inp):
        mgr = CycleManager(TRIP)
        mgr.set_cycles([EstimationCycle(name="C1", start_date="2026-01-01", active=True),
                        EstimationCycle(name="C0", start_date="2025-01-01", active=False)])
        return mgr.validate_no_reactivation(inp["cycle_name"])

    def wl_validate(inp):
        return {"errors": WorkloadStandardManager(TRIP).validate_file(inp["filename"])}

    def wl_upload_denied(inp):
        return WorkloadStandardManager(TRIP).upload_version(
            inp["filename"], inp["user"], inp["role"])

    def _versions(*specs):
        out = []
        for vid, status in specs:
            v = WorkloadStandardVersion(version_id=vid, uploaded_at="2026-01-01T00:00:00",
                                        uploaded_by="u", filename="wl.xlsx", status=status)
            v._inductors = [{"id": "i1", "name": "A"}, {"id": "i2", "name": "B"}]
            out.append(v)
        return out

    def del_denied(inp):
        d = BulkInductorDeleter(TRIP)
        d.set_versions(_versions(("WL-0001", "active"), ("WL-0000", "superseded")))
        return d.bulk_delete("WL-0001", ["i1"], inp["role"])

    def del_empty(inp):
        d = BulkInductorDeleter(TRIP)
        d.set_versions(_versions(("WL-0001", "active")))
        return d.bulk_delete("WL-0001", [], inp["role"])

    def del_only_active(inp):
        d = BulkInductorDeleter(TRIP)
        d.set_versions(_versions(("WL-0001", "active")))
        return d.bulk_delete("WL-0001", ["i1"], inp["role"])

    def del_list(inp):
        d = BulkInductorDeleter(TRIP)
        d.set_versions(_versions(("WL-0001", "active")))
        return {"inductors": d.list_deletable_inductors("WL-0001")}

    def del_success(inp):
        d = BulkInductorDeleter(TRIP)
        d.set_versions(_versions(("WL-0002", "active"), ("WL-0001", "superseded")))
        return d.bulk_delete("WL-0001", ["i1"], inp["role"])

    def _state_dict(s):
        return {"page": s.page, "filters": s.filters, "sort_column": s.sort_column,
                "sort_direction": s.sort_direction, "column_widths": s.column_widths}

    def table_filter_sort(inp):
        m = TableStateManager(TRIP)
        m.set_filter("p", "metier", "Backend")
        m.set_sort("p", "name", "asc")
        rows = [{"metier": "Backend", "name": "b"}, {"metier": "Frontend", "name": "a"},
                {"metier": "Backend", "name": "a"}]
        return {"filtered": m.apply_filters(rows, "p"), "sorted": m.apply_sort(rows, "p")}

    def table_persist(inp):
        m = TableStateManager(TRIP)
        m.set_filter("p", "metier", "Backend")
        return _state_dict(m.get_state("p"))

    def table_reset(inp):
        m = TableStateManager(TRIP)
        m.set_filter("p", "metier", "Backend")
        m.reset_page("p")
        return _state_dict(m.get_state("p"))

    def email_logged(inp):
        svc = EmailAlertService(TRIP)
        r = svc.send_rcrc_weekly(inp["emails"], inp["metrics"], inp["cycle"])
        return {"subject": r["subject"], "recipients": r["recipients"],
                "log_count": len(svc.get_log())}

    return [
        # CYCLE-BR-01 / CYCLE-BR-04 — one active cycle; create auto-deactivates previous.
        Probe(["CYCLE-BR-01", "CYCLE-BR-04"], "cycle_create", cycle_create, cases=[
            {"name": "C2", "start_date": "2026-06-01", "role": "Admin"}]),
        # CYCLE-BR-02 — inactive cycles cannot be reactivated.
        Probe(["CYCLE-BR-02"], "cycle_reactivation", cycle_reactivation, cases=[
            {"cycle_name": "C0"}, {"cycle_name": "C1"}]),
        # WL-BR-01 — only Admin/RCRC may upload (denied paths are deterministic).
        Probe(["WL-BR-01"], "wl_upload_denied", wl_upload_denied, cases=[
            {"filename": "wl.xlsx", "user": "u", "role": "Engineer"},
            {"filename": "wl.xlsx", "user": "u", "role": "Bogus"}]),
        # WL-BR-02 — only .xlsx accepted.
        Probe(["WL-BR-02"], "wl_validate_file", wl_validate, cases=[
            {"filename": "data.csv"}, {"filename": "data.xlsx"}]),
        # DEL-BR-01 — only Admin/RCRC may bulk-delete.
        Probe(["DEL-BR-01"], "del_permission", del_denied, cases=[{"role": "PMO"}]),
        # DEL-BR-09 — empty selection blocked.
        Probe(["DEL-BR-09"], "del_empty_selection", del_empty, cases=[{"role": "Admin"}]),
        # DEL-BR-05 — cannot delete from the only active version.
        Probe(["DEL-BR-05"], "del_only_active", del_only_active, cases=[{"role": "Admin"}]),
        # DEL-BR-02 — deletion view lists only loaded inductors.
        Probe(["DEL-BR-02"], "del_list_loaded", del_list, cases=[{}]),
        # DEL-BR-10 / DEL-BR-07 — deletion summary; superseded delete doesn't touch active.
        Probe(["DEL-BR-10", "DEL-BR-07"], "del_success_summary", del_success, cases=[{"role": "Admin"}]),
        # TABLE-BR-01 — filtering + sorting.
        Probe(["TABLE-BR-01"], "table_filter_sort", table_filter_sort, cases=[{}]),
        # TABLE-BR-02 — state persists within the page session.
        Probe(["TABLE-BR-02"], "table_persist", table_persist, cases=[{}]),
        # TABLE-BR-03 — navigating away resets table state.
        Probe(["TABLE-BR-03"], "table_reset", table_reset, cases=[{}]),
        # EMAIL-BR-03 — every sent email is logged.
        Probe(["EMAIL-BR-03"], "email_logged", email_logged, cases=[
            {"emails": ["a@x.com", "b@x.com"],
             "metrics": {"total_jus": 10, "assigned_jus": 7, "unassigned_jus": 3, "split_rows": 1},
             "cycle": "C1"}]),
    ]


def build_probes() -> dict[str, list[Probe]]:
    return {
        "pre_estimation": _pre_estimation_probes(),
        "estimation_review": _estimation_review_probes(),
        "allocation": _allocation_probes(),
        "final_review": _final_review_probes(),
        "management_view": _management_view_probes(),
        "transversal": _transversal_probes(),
    }


def covered_rule_ids() -> list[str]:
    ids: set[str] = set()
    for probes in build_probes().values():
        for p in probes:
            ids.update(p.rule_ids)
    return sorted(ids)


def _emit(check: bool) -> int:
    version = read_version(REPO_ROOT)
    views = build_probes()
    drift = []
    for view, probes in views.items():
        entries = generate_fixtures(probes, version)
        path = FIXTURES_DIR / f"{view}.json"
        new = canonical_json(entries)
        if check:
            old = path.read_text() if path.exists() else ""
            if old != new:
                drift.append(view)
        else:
            write_fixture_file(path, entries)

    inv = {
        "sdd_version": version,
        "business_rule_count": rule_count(),
        "business_rule_ids": business_rule_ids(),
        "pending_marker_ids": pending_marker_ids(),
        "covered_rule_ids": covered_rule_ids(),
        "non_deterministic_rules": NON_DETERMINISTIC_RULES,
        "no_function_surface_rules": NO_FUNCTION_SURFACE_RULES,
    }
    inv_path = FIXTURES_DIR / "_inventory.json"
    new_inv = canonical_json(inv)
    if check:
        if (inv_path.read_text() if inv_path.exists() else "") != new_inv:
            drift.append("_inventory")
    else:
        write_fixture_file(inv_path, inv)

    if check and drift:
        print(f"FIXTURE DRIFT in: {', '.join(drift)}. "
              f"Run: python -m great_sdd.conformance.generate", file=sys.stderr)
        return 1
    print(f"{'checked' if check else 'wrote'} fixtures for {len(views)} views @ v{version}; "
          f"{len(covered_rule_ids())}/{rule_count()} business rules covered.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate/verify GREAT conformance fixtures.")
    ap.add_argument("--check", action="store_true",
                    help="Verify committed fixtures are in sync (exit 1 on drift).")
    args = ap.parse_args(argv)
    return _emit(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
