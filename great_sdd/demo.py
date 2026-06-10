"""
GREAT Pre-Estimation — Demo Runner.

Shows the full pipeline in action.
Run with: python -m great_sdd.demo
"""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from great_sdd.modules.base import LMClient
from great_sdd.pipeline.pre_estimation_pipeline import PreEstimationPipeline
from tests.sample_data import (
    SAMPLE_PROJECT_LINES,
    INCOMPATIBLE_LINE,
    SAMPLE_JOB_UNITS,
    ENGINEER_ANA,
    PMO_USER,
)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(label: str, data: dict):
    """Pretty-print a pipeline step result."""
    print(f"\n  📍 {label}:")
    for k, v in data.items():
        if isinstance(v, (list, dict)):
            print(f"     {k}: {json.dumps(v, indent=6)}"[:200])
        else:
            print(f"     {k}: {v}")


def demo_specs():
    """Demo: Show the spec registry (no LM needed)."""
    print_section("SPEC REGISTRY — Business Rules")
    from great_sdd.specs.pre_estimation_specs import BUSINESS_RULES, STATUS_TRANSITIONS
    for rule in BUSINESS_RULES:
        print(f"  {rule['id']}: {rule['rule']}")

    print("\n  State Machine:")
    from great_sdd.specs.pre_estimation_specs import LineStatus
    for status, targets in STATUS_TRANSITIONS.items():
        target_names = [t.value for t in targets] if targets else ["(terminal)"]
        print(f"    {status.value:12s} → {', '.join(target_names)}")


def demo_compatibility():
    """Demo: Validate line compatibility (pure Python)."""
    print_section("STAGE 1: SELECTION COMPATIBILITY")

    # Compatible lines (same organ type + energy + ranking + injection)
    print("\n  ✅ Compatible selection (same fields):")
    from great_sdd.modules.pre_estimation import SelectionValidator
    validator = SelectionValidator()
    result = validator.forward(SAMPLE_PROJECT_LINES[:2])  # PL-001 + PL-002
    print(f"     Compatible: {result['is_compatible']}")

    # Incompatible lines
    print("\n  ❌ Incompatible selection (different organ_type):")
    result = validator.forward([SAMPLE_PROJECT_LINES[0], INCOMPATIBLE_LINE])
    print(f"     Compatible: {result['is_compatible']}")
    if not result['is_compatible']:
        print(f"     Reason: {result['incompatibility_reason']}")


def demo_permissions():
    """Demo: Check role permissions (pure Python)."""
    print_section("STAGE 2: ROLE PERMISSIONS")

    from great_sdd.modules.pre_estimation import PermissionChecker
    checker = PermissionChecker()

    scenarios = [
        ("Engineer", "Ana Martinez", "Ana Martinez", "edit", "✅ Engineer edits own line"),
        ("Engineer", "Ana Martinez", "Carlos Ruiz", "edit",    "❌ Engineer edits other's line"),
        ("Admin",    "Ana Martinez", "Admin",        "edit",   "✅ Admin edits any line"),
        ("PMO",      "Ana Martinez", "Laura Gomez",  "edit",   "❌ PMO tries to edit"),
        ("PMO",      "Ana Martinez", "Laura Gomez",  "view",   "✅ PMO views"),
        ("CPO",      "Ana Martinez", "CPO User",     "view",   "❌ CPO no access"),
    ]

    for role, assignee, user, action, label in scenarios:
        result = checker.forward(role, assignee, user, action)
        icon = "✅" if result["allowed"] else "❌"
        print(f"  {icon} {label}: {result['reason'][:80]}")


def demo_state_machine():
    """Demo: Validate status transitions (pure Python)."""
    print_section("STAGE 3: STATE MACHINE TRANSITIONS")

    from great_sdd.modules.pre_estimation import StatusTransitionValidator
    validator = StatusTransitionValidator()

    transitions = [
        ("to_do",      "draft",     False, "✅ To do → Draft (no session)"),
        ("to_do",      "estimated", False, "❌ To do → Estimated (no draft gate)"),
        ("draft",      "estimated", True,  "✅ Draft → Estimated (with draft gate)"),
        ("estimated",  "sent",      False, "✅ Estimated → Sent"),
        ("sent",       "approved",  False, "✅ Sent → Approved"),
        ("approved",   "draft",     False, "❌ Approved → Draft (terminal)"),
        ("modification_requested",   "draft",     False, "✅ Modification Requested → Draft (rework)"),
    ]

    for current, target, has_draft, label in transitions:
        result = validator.forward(current, target, has_draft)
        icon = "✅" if result["is_valid"] else "❌"
        print(f"  {icon} {label}")


def demo_estimation_calculation():
    """Demo: Calculate estimation from JUs (pure Python)."""
    print_section("STAGE 4: ESTIMATION CALCULATION")

    from great_sdd.modules.pre_estimation import EstimationCalculator
    calculator = EstimationCalculator()

    result = calculator.forward(SAMPLE_JOB_UNITS)
    print(f"\n  Job Units: 3 (API-DEV, API-TEST, DB-DESIGN)")
    print(f"  Total FTE:  {result['total_fte']}")
    print(f"  Total BH:   {result['total_bh']}")
    print(f"  Total KM:   {result['total_km']}")
    print(f"\n  Breakdown per JU:")
    for ju in result["breakdown"]:
        print(f"    {ju['short_name']:10s} | {ju['variable']}×{ju['occurrence']} + {ju['fixed']} = {ju['total']} {ju['unit_type']}")


def demo_save_validation():
    """Demo: Validate pre-save conditions (pure Python)."""
    print_section("STAGE 5: SAVE VALIDATION")

    from great_sdd.modules.pre_estimation import SaveValidator
    validator = SaveValidator()

    # Valid save
    print("\n  ✅ Valid Draft save:")
    line_valid = {
        "status": "to_do",
        "sp_date": "2026-01-01",
        "inductors": [{"name": "API endpoints", "selected_cran": "Simple"}],
    }
    result = validator.forward(line_valid, "draft")
    print(f"     Can save: {result['can_save']}")

    # Missing SP date
    print("\n  ❌ Missing SP date:")
    line_no_sp = {
        "status": "to_do",
        "sp_date": None,
        "inductors": [{"name": "API endpoints", "selected_cran": "Simple"}],
    }
    result = validator.forward(line_no_sp, "draft")
    print(f"     Can save: {result['can_save']}")
    for err in result["validation_errors"]:
        print(f"     ⚠ {err}")

    # Draft gate violation
    print("\n  ❌ Definitive without Draft gate (BR-02):")
    result = validator.forward(line_valid, "definitive", has_saved_draft_in_session=False)
    print(f"     Can save: {result['can_save']}")
    for err in result["validation_errors"]:
        print(f"     ⚠ {err}")


def demo_monthly_distribution():
    """Demo: Monthly distribution (pure Python)."""
    print_section("STAGE 6: MONTHLY DISTRIBUTION")

    from great_sdd.modules.pre_estimation import MonthDistributor
    distributor = MonthDistributor()

    result = distributor.forward(
        total_fte=1.5,
        total_bh=40.0,
        total_km=100.0,
        sp_date="2026-01-01",
        project_duration_months=6,
    )
    print(f"\n  Distribution (6 months from 2026-01-01):")
    for m in result["monthly_distribution"]:
        if m["fte"] > 0:
            print(f"    Month {m['month']:2d}: FTE={m['fte']:.2f}, BH={m['bh']:.1f}, KM={m['km']:.1f}")

    print(f"\n  Yearly aggregation:")
    for year, data in result["yearly_aggregation"].items():
        print(f"    {year}: FTE={data.get('fte', 0):.2f}")


def demo_full_pipeline():
    """Demo: Run the full pipeline (requires LM)."""
    print_section("FULL PIPELINE (with LM)")

    lm = LMClient(model="deepseek/deepseek-chat", api_key=os.environ.get("DEEPSEEK_API_KEY"))

    pipeline = PreEstimationPipeline(lm=lm)

    # Select two compatible lines
    selected = SAMPLE_PROJECT_LINES[:2]  # PL-001 + PL-002 (both compatible)

    print(f"\n  Selected: {[l['id'] for l in selected]}")
    print(f"  Role: {ENGINEER_ANA['role']} ({ENGINEER_ANA['user']})")
    print(f"  Métier: Backend")

    context = pipeline.forward(
        selected_lines=selected,
        role=ENGINEER_ANA["role"],
        current_user=ENGINEER_ANA["user"],
        metier="Backend",
        line_description=selected[0]["description"],
        sp_date=selected[0]["sp_date"],
    )

    print(f"\n  📋 Pipeline Result:")
    print(f"     Selection valid:             {context.selection_valid}")
    print(f"     Permission allowed:          {context.permission_allowed}")
    print(f"     No standard found:           {context.no_standard_found}")
    print(f"     Can save draft:              {context.can_save_draft}")
    print(f"     Can save definitive:         {context.can_save_definitive}")
    print(f"     Total FTE:                   {context.total_fte:.2f}")
    print(f"     Total BH:                    {context.total_bh:.2f}")
    print(f"     Total KM:                    {context.total_km:.2f}")
    print(f"     Validation errors:           {context.validation_errors}")
    print(f"     Pipeline errors:             {context.errors}")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║   GREAT System — Pre-Estimation SDD Pipeline Demo        ║
║   Specification-Driven Development (SDD)                 ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Run all demos
    demo_specs()
    demo_compatibility()
    demo_permissions()
    demo_state_machine()
    demo_estimation_calculation()
    demo_save_validation()
    demo_monthly_distribution()

    print(f"\n{'='*60}")
    print("  Pipeline ready for LM-powered execution.")
    print("  Set DEEPSEEK_API_KEY and run demo_full_pipeline()")
    print(f"{'='*60}\n")
