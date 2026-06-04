"""
GREAT System — Allocation Spec Registry.

Financial layer: assigns job units to societes (business units) and
calculates K€ costs. Only Approved (PL, Métier) pairs appear.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from great_sdd.specs.pre_estimation_specs import LineStatus, Role


# ──────────────────────────────────────────────
# 1. Role Permissions (§2)
# ──────────────────────────────────────────────

@dataclass
class AllocationPermission:
    can_view: bool
    can_edit: bool
    can_save: bool


ALLOCATION_PERMISSIONS: dict[Role, AllocationPermission] = {
    Role.ADMIN:    AllocationPermission(can_view=True, can_edit=True, can_save=True),
    Role.PMO:      AllocationPermission(can_view=True, can_edit=True, can_save=True),
    Role.RCRC:     AllocationPermission(can_view=True, can_edit=True, can_save=True),
    Role.ENGINEER: AllocationPermission(can_view=False, can_edit=False, can_save=False),
    Role.CPO:      AllocationPermission(can_view=False, can_edit=False, can_save=False),
}


# ──────────────────────────────────────────────
# 2. Grid Visibility (§3)
# ──────────────────────────────────────────────

ALLOCATION_ELIGIBLE_STATUSES = {LineStatus.APPROVED}


# ──────────────────────────────────────────────
# 3. Cost Types
# ──────────────────────────────────────────────

class CostType(Enum):
    FTE = "FTE"
    TSA = "TSA"
    TC = "TC"


# ──────────────────────────────────────────────
# 4. Available Societes (§12)
# ──────────────────────────────────────────────

@dataclass
class Societe:
    name: str
    sites: list[str] = field(default_factory=list)
    cost_types: list[CostType] = field(default_factory=lambda: [CostType.FTE])


AVAILABLE_SOCIETES: list[Societe] = [
    Societe("Horse Spain S.L.", ["Valladolid", "Seville", "Madrid"]),
    Societe("Horse Romania S.A.", ["Bucarest", "Pitesti", "Titu"]),
    Societe("Horse Brasil S.A.", ["Curitiba"]),
    Societe("Oyak Horse", []),
    Societe("CHENNAI GESC H", [], [CostType.TSA]),
    Societe("GEHEUNG", [], [CostType.TSA]),
    Societe("Ampere/RG", [], [CostType.TSA]),
]


def get_societe_site(societe_name: str, site: str = "") -> str:
    """Return the societe-site key for rate lookups."""
    for s in AVAILABLE_SOCIETES:
        if s.name.lower() == societe_name.lower():
            if site and site in s.sites:
                return f"{s.name}-{site}"
            return s.name
    return societe_name


# ──────────────────────────────────────────────
# 5. K€ Rates (§11)
# ──────────────────────────────────────────────

# §11.1 FTE Cost Type Rates
FTE_RATES: dict[str, dict[str, float]] = {
    "Horse Spain S.L.-Valladolid": {"2024": 107, "2025": 106, "2026": 103, "2027": 101},
    "Horse Spain S.L.-Seville":    {"2024": 107, "2025": 106, "2026": 103, "2027": 101},
    "Horse Spain S.L.-Madrid":     {"2024": 107, "2025": 106, "2026": 103, "2027": 101},
    "Horse Romania S.A.-Bucarest": {"2024": 100, "2025": 79,  "2026": 76,  "2027": 74},
    "Horse Romania S.A.-Titu":     {"2024": 100, "2025": 79,  "2026": 76,  "2027": 74},
    "Horse Romania S.A.-Pitesti":  {"2024": 100, "2025": 79,  "2026": 76,  "2027": 74},
    "Horse Brasil S.A.-Curitiba":  {"2024": 85,  "2025": 87,  "2026": 80,  "2027": 78},
    "Oyak Horse":                  {"2024": 100, "2025": 75,  "2026": 68,  "2027": 69},
}

# §11.2 TSA Cost Type Rates
TSA_RATES: dict[str, dict[str, float]] = {
    "CHENNAI GESC H": {"2025": 54,  "2026": 56.7, "2027": 59.5},
    "GEHEUNG":         {"2025": 155, "2026": 162.75, "2027": 170.89},
    "Ampere/RG":       {"2025": 155, "2026": 162.75, "2027": 170.89},
}


def calculate_fte_ke(fte: float, societe_site: str, year: str) -> float:
    """K€ = FTE × Rate(societe-site, year). §11.1"""
    rates = FTE_RATES.get(societe_site, {})
    rate = rates.get(year, 0)
    return round(fte * rate, 2)


def calculate_tsa_ke(fte: float, societe: str, year: str) -> float:
    """TSA K€ = FTE × TSA Rate(societe, year). §11.2"""
    rates = TSA_RATES.get(societe, {})
    rate = rates.get(year, 0)
    return round(fte * rate, 2)


# ──────────────────────────────────────────────
# 6. Métier-Specific Behavior (§4.4)
# ──────────────────────────────────────────────

METIER_ALLOCATION_CONFIG: dict[str, dict] = {
    "H-DESIGN":    {"unit_types": ["man_day", "number"], "has_diversity_dropdown": True},
    "H-TUNING":    {"unit_types": ["man_day", "number"], "has_diversity_dropdown": False},
    "H-SOFTWARE":  {"unit_types": ["man_day", "number"], "has_diversity_dropdown": False},
    "H-PROJECT":   {"unit_types": ["man_day", "number", "bench_hours", "kilometres", "k_euros"],
                     "has_diversity_dropdown": False, "extra_routing": True},
    "H-NP":        {"unit_types": ["man_day", "number", "bench_hours", "kilometres", "k_euros"],
                     "has_diversity_dropdown": False, "extra_routing": True, "same_as": "H-PROJECT"},
    "H-TESTING":   {"unit_types": ["bench_hours", "kilometres", "k_euros"],
                     "has_diversity_dropdown": True, "testing_specific": True},
    "H-CUSTOMER":  {"unit_types": ["man_day"], "has_diversity_dropdown": True,
                     "fallback_societe": "Horse Spain S.L.-VALLADOLID"},
}


# ──────────────────────────────────────────────
# 7. H-PROJECT / H-NP Extra Routing (§4.5)
# ──────────────────────────────────────────────

STANDARD_EMISSIONS_BRASIL = {"L83L", "L83G", "P81A"}
ALLIANCE_DB_PREFIX = "DB"


def route_hproject_hnp(standard_emissions: str, organ_type: str,
                        alliance_code: str) -> str:
    """
    Extra routing for H-PROJECT/H-NP, applied after Excel rules.

    Priority:
    1. Standard Emissions ∈ {L83L, L83G, P81A} → Horse Brasil S.A.-CURITIBA
    2. Organ Type "Boite de vitesse":
       - Alliance Code starts with "DB" → Horse Spain S.L.-VALLADOLID
       - Otherwise → Horse Romania S.A.-BUCAREST
    """
    if standard_emissions.upper() in STANDARD_EMISSIONS_BRASIL:
        return "Horse Brasil S.A.-CURITIBA"

    if "boite" in organ_type.lower() and "vitesse" in organ_type.lower():
        if alliance_code.upper().startswith(ALLIANCE_DB_PREFIX):
            return "Horse Spain S.L.-VALLADOLID"
        else:
            return "Horse Romania S.A.-BUCAREST"

    return ""  # No extra routing — use Excel rule result


# ──────────────────────────────────────────────
# 8. Allocation Grid Columns (§5.2)
# ──────────────────────────────────────────────

ALLOCATION_GRID_COLUMNS = [
    {"field": "metier", "editable": False},
    {"field": "owner_n2", "editable": False},
    {"field": "pl_number", "editable": False},
    {"field": "pl_name", "editable": False},
    {"field": "societe", "editable": True},
    {"field": "cost_type", "editable": True},
    {"field": "organ_type", "editable": False},
    {"field": "energy", "editable": False},
    {"field": "alliance_code", "editable": False},
    {"field": "vehicle_code", "editable": False},
    {"field": "standard_emissions", "editable": False},
    {"field": "market", "editable": False},
    {"field": "fmm_description", "editable": False},
    {"field": "ju_description", "editable": False},
    {"field": "ju_code", "editable": False},
    {"field": "total_fte", "editable": False},
]

ALLOCATION_FILTERS = [
    {"field": "pl_number_name", "type": "free_text"},
    {"field": "metier", "type": "dropdown"},
    {"field": "owner_n2", "type": "dropdown"},
    {"field": "societe", "type": "dropdown", "options": ["All", "Unassigned"] + [s.name for s in AVAILABLE_SOCIETES]},
    {"field": "cost_type", "type": "dropdown", "options": ["All", "FTE", "TSA", "TC"]},
    {"field": "show_unresolved_only", "type": "toggle"},
]


# ──────────────────────────────────────────────
# 9. Allocation Rules (from Excel) — simplified model
# ──────────────────────────────────────────────

@dataclass
class AllocationRule:
    metier: str
    fields: dict  # field_name -> match_value (empty = wildcard)
    societe: str
    cost_type: CostType = CostType.FTE
    exception: bool = False  # §4.3: Exception = "Y" takes priority


# ──────────────────────────────────────────────
# 10. Allocation Business Rules (§13)
# ──────────────────────────────────────────────

ALLOCATION_RULES_LIST: list[dict] = [
    {"id": "ALLOC-BR-01", "rule": "Approved lines only — Only job units from status=Approved (PL, Métier) pairs appear"},
    {"id": "ALLOC-BR-02", "rule": "Rules skip assigned rows — Auto-rule engine only runs on job units with no societe"},
    {"id": "ALLOC-BR-03", "rule": "FTE columns read-only — FTE from approved estimations cannot be modified"},
    {"id": "ALLOC-BR-04", "rule": "K€ recalculated on save — Grid shows last-saved K€; recalculated on dirty rows"},
    {"id": "ALLOC-BR-05", "rule": "Dirty-row tracking — Only modified rows sent to backend on save"},
    {"id": "ALLOC-BR-06", "rule": "TSA/TC without societe blocks save — Missing societe on TSA/TC prevents saving"},
    {"id": "ALLOC-BR-07", "rule": "FTE without societe non-blocking — Highlighted but does not block save"},
    {"id": "ALLOC-BR-08", "rule": "Diversity dropdown non-blocking — Unresolved diversity does not block save"},
    {"id": "ALLOC-BR-09", "rule": "Bulk assignment overwrites — Always overwrites existing societes on checked rows"},
    {"id": "ALLOC-BR-10", "rule": "Bulk assignment: societe only — Never changes cost type"},
    {"id": "ALLOC-BR-11", "rule": "Split: percentages must sum to 100%"},
    {"id": "ALLOC-BR-12", "rule": "Split undo: full delete only — Restores original single row"},
    {"id": "ALLOC-BR-13", "rule": "TC: societe mandatory — Blocks save if missing"},
    {"id": "ALLOC-BR-14", "rule": "Filter persistence — Preserved after all in-page actions"},
    {"id": "ALLOC-BR-15", "rule": "Active cycle only"},
    {"id": "ALLOC-BR-16", "rule": "No finalization action — Final Review reads whatever is saved"},
    {"id": "ALLOC-BR-17", "rule": "JU metier routing — Bench Hours/Kilometres → H-TESTING; else → match project_line.metier"},
]


# ──────────────────────────────────────────────
# 11. TC K€ Proportional Distribution (§8.2)
# ──────────────────────────────────────────────

def distribute_tc_ke(total_ke: float, fte_yearly: dict[str, float]) -> dict[str, float]:
    """
    Distribute total K€ proportionally to yearly FTE share.
    K€_year = Total_K€ × (FTE_year / Total_FTE)
    """
    total_fte = sum(fte_yearly.values())
    if total_fte == 0:
        return {year: 0.0 for year in fte_yearly}

    return {
        year: round(total_ke * (fte / total_fte), 2)
        for year, fte in fte_yearly.items()
    }


# ──────────────────────────────────────────────
# 12. Pending Definitions (§15)
# ──────────────────────────────────────────────

ALLOCATION_PENDING = [
    {
        "id": "ALLOC-01",
        "topic": "K€ job units (Kiloeuros): include in standard flow or manual K€ input per PL?",
        "blocking": True,
        "notes": "4 open questions: (1) formula and yearly aggregation, (2) grid display, "
                 "(3) societe requirement, (4) Final Review appearance",
    },
]


# ──────────────────────────────────────────────
# 13. Split Allocation Model (§10)
# ──────────────────────────────────────────────

@dataclass
class SplitAllocation:
    """Represents a split of one JU across N societes."""
    original_ju_id: str
    splits: list[dict] = field(default_factory=list)
    # Each split: {"societe": str, "percentage": float, "fte": float, "ke": dict[str, float]}


# ──────────────────────────────────────────────
# 14. JU Metier Routing (§4.6 — ALLOC-BR-17)
# ──────────────────────────────────────────────

TESTING_UNIT_TYPES = {"Bench Hours", "Kilometres"}
TESTING_METIER = "H-TESTING"
VALID_METIERS = {"H-DESIGN", "H-TUNING", "H-SOFTWARE", "H-CUSTOMER", "H-PROJECT", "H-NP", "H-TESTING"}


def resolve_ju_metier(unit_type: str, project_line_metier: str) -> str:
    """
    Resolve the correct metier for a job unit.
    BH/KM → H-TESTING; else → same as project_line.metier.
    """
    if unit_type in TESTING_UNIT_TYPES:
        return TESTING_METIER
    return project_line_metier


def validate_ju_metier_routing(job_units: list[dict], project_lines: dict[str, dict]) -> dict:
    """
    Validate ALLOC-BR-17 for a batch of job units.

    Args:
        job_units: list of dicts with keys unit_type, metier, project_line_id
        project_lines: dict mapping project_line_id → dict with key 'metier'

    Returns:
        {"valid": bool, "errors": list[str]}
    """
    errors = []
    for ju in job_units:
        ju_metier = ju.get("metier", "")
        unit_type = ju.get("unit_type", "")
        pl_id = ju.get("project_line_id", "")
        pl_metier = project_lines.get(pl_id, {}).get("metier", "")
        expected = resolve_ju_metier(unit_type, pl_metier)
        if ju_metier != expected:
            errors.append(
                f"JU {ju.get('id', '?')}: metier={ju_metier}, expected={expected} "
                f"(unit_type={unit_type}, pl_metier={pl_metier})"
            )
    return {"valid": len(errors) == 0, "errors": errors}


def apply_split(ju_fte_yearly: dict[str, float], splits: list[dict]) -> list[dict]:
    """
    Apply a split to a job unit's yearly FTE.

    Args:
        ju_fte_yearly: {"2024": 0.5, "2025": 0.3, ...}
        splits: [{"societe": "X", "percentage": 60}, {"societe": "Y", "percentage": 40}]

    Returns:
        List of split rows with proportional FTE
    """
    total_pct = sum(s["percentage"] for s in splits)
    if abs(total_pct - 100.0) > 0.01:
        raise ValueError(f"Split percentages must sum to 100%. Got: {total_pct}%")

    results = []
    for split in splits:
        pct = split["percentage"] / 100.0
        split_fte = {year: round(fte * pct, 4) for year, fte in ju_fte_yearly.items()}
        results.append({
            "societe": split["societe"],
            "percentage": split["percentage"],
            "fte_yearly": split_fte,
        })

    return results