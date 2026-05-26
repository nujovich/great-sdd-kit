"""
GREAT Management View — Tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from great_dspy.specs.management_view_specs import (
    MANAGEMENT_ACCESS, MGMT_EXCLUDED_METIERS, MANAGEMENT_RULES,
    compute_pie_chart, PieChartSlice,
)
from great_dspy.modules.management_view import (
    ManagementAccessChecker, PieChartBuilder, TimelineBuilder, MetierFilter,
)
from great_dspy.specs.pre_estimation_specs import LineStatus, Role

# ── Spec tests ──

def test_access():
    assert MANAGEMENT_ACCESS[Role.ADMIN] is True
    assert MANAGEMENT_ACCESS[Role.PMO] is True
    assert MANAGEMENT_ACCESS[Role.CPO] is False
    assert MANAGEMENT_ACCESS[Role.ENGINEER] is False
    assert MANAGEMENT_ACCESS[Role.RCRC] is False

def test_excluded_metiers():
    assert "H-NP" in MGMT_EXCLUDED_METIERS
    assert "H-PROJECT" in MGMT_EXCLUDED_METIERS

def test_8_rules():
    assert len(MANAGEMENT_RULES) == 8

def test_pie_chart():
    slices = compute_pie_chart({"to_do": 10, "draft": 5, "estimated": 3,
                                "sent": 2, "rejected": 1, "approved": 4})
    assert len(slices) == 6
    total_pct = sum(s.percentage for s in slices)
    assert total_pct == 100.0

def test_pie_chart_empty():
    slices = compute_pie_chart({})
    assert all(s.count == 0 for s in slices)

def test_pie_chart_single():
    slices = compute_pie_chart({"approved": 10})
    approved = [s for s in slices if s.status == "approved"][0]
    assert approved.count == 10
    assert approved.percentage == 100.0

# ── Module tests ──

def test_access_checker():
    c = ManagementAccessChecker()
    assert c.forward("Admin")["allowed"] is True
    assert c.forward("PMO")["allowed"] is True
    assert c.forward("CPO")["allowed"] is False
    assert c.forward("Engineer")["allowed"] is False

def test_metier_filter():
    f = MetierFilter()
    pairs = [
        {"metier": "H-DESIGN", "status": "estimated"},
        {"metier": "H-NP", "status": "approved"},
        {"metier": "H-PROJECT", "status": "draft"},
        {"metier": "Backend", "status": "to_do"},
    ]
    filtered = f.forward(pairs, "All")
    assert len(filtered) == 2  # H-NP and H-PROJECT excluded
    assert all(p["metier"] not in MGMT_EXCLUDED_METIERS for p in filtered)

def test_metier_filter_specific():
    f = MetierFilter()
    pairs = [{"metier": "H-DESIGN", "status": "estimated"}]
    filtered = f.forward(pairs, "H-DESIGN")
    assert len(filtered) == 1

def test_count_by_status():
    f = MetierFilter()
    pairs = [
        {"status": "estimated"},
        {"status": "estimated"},
        {"status": "approved"},
    ]
    counts = f.count_by_status(pairs)
    assert counts["estimated"] == 2
    assert counts["approved"] == 1
    assert counts["to_do"] == 0  # All statuses present

def test_pie_chart_builder():
    b = PieChartBuilder()
    result = b.forward({"estimated": 5, "approved": 5}, "All")
    assert result["total"] == 10
    assert len(result["slices"]) == 6

def test_timeline_builder_empty():
    b = TimelineBuilder()
    result = b.forward([], "All")
    assert result["data_points"] == 0

def test_timeline_builder():
    b = TimelineBuilder()
    data = [
        {"date": "2026-01-01", "status_counts": {"to_do": 10, "estimated": 0}},
        {"date": "2026-01-15", "status_counts": {"to_do": 5, "estimated": 5}},
    ]
    result = b.forward(data, "All")
    assert result["data_points"] == 2
    assert len(result["lines"]) == 6  # One per status