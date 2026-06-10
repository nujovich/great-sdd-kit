"""
GREAT System — Specification-Driven Development Spec Registry.

This file IS the "Specification" in SDD. Every business rule, state transition,
role permission, and validation constraint is encoded here as data structures,
not in prompts or code comments. DSPy modules read from this registry.

When a business rule changes, you change it HERE — not in a prompt string.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────
# 1. Status Machine
# ──────────────────────────────────────────────

class LineStatus(Enum):
    TODO = "to_do"
    DRAFT = "draft"
    ESTIMATED = "estimated"
    SENT = "sent"
    MODIFICATION_REQUESTED = "modification_requested"
    APPROVED = "approved"


# Allowed transitions: (from_status) → [to_statuses]
STATUS_TRANSITIONS: dict[LineStatus, list[LineStatus]] = {
    LineStatus.TODO:      [LineStatus.DRAFT],
    LineStatus.DRAFT:     [LineStatus.DRAFT, LineStatus.ESTIMATED],
    LineStatus.ESTIMATED: [LineStatus.SENT, LineStatus.MODIFICATION_REQUESTED],
    LineStatus.SENT:      [LineStatus.APPROVED, LineStatus.MODIFICATION_REQUESTED],
    LineStatus.MODIFICATION_REQUESTED:  [LineStatus.DRAFT, LineStatus.ESTIMATED],
    LineStatus.APPROVED:  [],  # Terminal state — no exits
}

# Status semantic groups
LOCKED_STATUSES = {LineStatus.ESTIMATED, LineStatus.SENT, LineStatus.APPROVED}
EDITABLE_STATUSES = {LineStatus.TODO, LineStatus.DRAFT, LineStatus.MODIFICATION_REQUESTED}
TERMINAL_STATUSES = {LineStatus.APPROVED}


# ──────────────────────────────────────────────
# 2. Roles & Permissions
# ──────────────────────────────────────────────

class Role(Enum):
    ADMIN = "Admin"
    ENGINEER = "Engineer"
    PMO = "PMO"
    RCRC = "RCRC"
    CPO = "CPO"


@dataclass
class RolePermission:
    can_view: bool
    can_edit: bool
    scope: str  # "all" | "assigned_only" | "none"
    can_send_to_hvt: bool
    can_reject: bool


ROLE_PERMISSIONS: dict[Role, RolePermission] = {
    Role.ADMIN:    RolePermission(can_view=True, can_edit=True, scope="all",     can_send_to_hvt=True,  can_reject=False),
    Role.ENGINEER: RolePermission(can_view=True, can_edit=True, scope="assigned_only", can_send_to_hvt=False, can_reject=False),
    Role.PMO:      RolePermission(can_view=True, can_edit=False, scope="all",    can_send_to_hvt=True,  can_reject=False),
    Role.RCRC:     RolePermission(can_view=True, can_edit=False, scope="all",    can_send_to_hvt=False, can_reject=False),
    Role.CPO:      RolePermission(can_view=False, can_edit=False, scope="none",  can_send_to_hvt=False, can_reject=True),
}

# Métiers (Owner N2)
METIERS = ["Backend", "Frontend", "Data", "DevOps", "QA", "Mobile"]

# Métiers excluded from filter (H-NP and H-PROJECT)
EXCLUDED_METIERS_FROM_FILTER = ["H-NP", "H-PROJECT"]


# ──────────────────────────────────────────────
# 3. Compatibility Rules (Multi-line Selection)
# ──────────────────────────────────────────────

COMPATIBILITY_FIELDS = [
    "organ_type",
    "energy_fuel_type",
    "project_ranking",
    "injection_system",
]


def are_lines_compatible(lines: list[dict]) -> bool:
    """
    All selected lines must share identical values on all 4 compatibility fields.
    null vs null = compatible. null vs value = incompatible.
    """
    if len(lines) < 2:
        return True

    def _val(line, field):
        v = line.get(field)
        return v if v is not None else "__NULL__"

    for field in COMPATIBILITY_FIELDS:
        vals = {_val(line, field) for line in lines}
        if len(vals) > 1:
            # Check if the conflict is null vs value
            has_null = any(line.get(field) is None for line in lines)
            has_value = any(line.get(field) is not None for line in lines)
            if has_null and has_value:
                return False  # null vs value = incompatible
            return False
    return True


# ──────────────────────────────────────────────
# 4. Business Rules (as declarative data)
# ──────────────────────────────────────────────

BUSINESS_RULES: list[dict] = [
    {"id": "BR-01", "rule": "No deletion — estimations are never deleted by any user under any circumstance"},
    {"id": "BR-02", "rule": "Draft gate — 'Save as Definitive' requires 'Save as Draft' first in the current session"},
    {"id": "BR-03", "rule": "Estimated = locked — status=Estimated makes the estimation read-only until CPO acts"},
    {"id": "BR-04", "rule": "Approved = terminal — status=Approved is permanently locked; no GREAT action can change it"},
    {"id": "BR-05", "rule": "Engineer approval inferred — status=Estimated implies engineer approval"},
    {"id": "BR-06", "rule": "Multi-select compatibility — all selected lines must share Organ Type + Energy + Project Ranking + Injection System"},
    {"id": "BR-07", "rule": "Null injection system — null vs null = compatible; null vs value = incompatible"},
    {"id": "BR-08", "rule": "SP date mandatory — saving is blocked if the project line has no SP date"},
    {"id": "BR-09", "rule": "Occurrence lock default — occurrence_locked is always false by default"},
    {"id": "BR-10", "rule": "Assignment read-only — line-to-engineer assignments come from HVT and cannot be modified in GREAT"},
    {"id": "BR-11", "rule": "Custom JUs unblocked — if no workload standard is found, estimation via Custom JUs is still allowed"},
    {"id": "BR-12", "rule": "Inductor without cran — skipped silently; does not block estimation or saving"},
    {"id": "BR-13", "rule": "Zero occurrence — allowed; contributes zero to the estimation output"},
    {"id": "BR-14", "rule": "Comments scoped to (line, métier) — a comment applies to one line+métier combination only"},
    {"id": "BR-15", "rule": "Draft is always the first step — 'Save as Definitive' disabled until 'Save as Draft' clicked in current session"},
    {"id": "BR-16", "rule": "Sent = locked — awaiting CPO response; cannot be cancelled or edited from GREAT"},
    {"id": "BR-17", "rule": "Re-save overwrites — each 'Save as Draft' overwrites the previous Draft in the database"},
    {"id": "BR-18", "rule": "Prototype data separate — prototype quantities are stored separately from engineering estimation; do not affect FTE/BH/KM"},
    {"id": "BR-19", "rule": "Prototype categories pending — category names and count are pending definition (PRE-01)"},
    {"id": "BR-20", "rule": "Custom JU permissions — Engineer, PMO, and Admin can create Custom JUs; RCRC and CPO cannot"},
]

# ─── Custom JU Permissions ──────────────────────────────────────
# Roles that are allowed to create Custom Job Units (BR-20)

CUSTOM_JU_ROLES: dict[str, bool] = {
    "Admin":    True,
    "Engineer": True,
    "PMO":      True,
    "RCRC":     False,
    "CPO":      False,
}


def can_create_custom_ju(role: str) -> bool:
    """Return True if the role can create Custom JUs (BR-20)."""
    return CUSTOM_JU_ROLES.get(role, False)


# ──────────────────────────────────────────────
# 5. Prototype Estimation
# ──────────────────────────────────────────────
# Sección 5.2 del documento funcional:
# "The engineer also fills the information necessary for the prototype estimation.
#  This form allows the estimator to input prototype-related quantities for the project line.
#  The form contains numeric inputs (number of prototypes by category) and a free-text comment field.
#  This data is stored separately from the engineering estimation and surfaces in the Final Review
#  as a distinct line item. It does not affect FTE, BH, or KM calculations."

@dataclass
class PrototypeCategory:
    """A category of prototype (e.g., 'Greenfield', 'Refactor', 'Integration', 'Maintenance').
    Categories are administered from the Admin page (AdminPage → Categorías tab).
    Pending: exact category names and count (📋 PRE-01)."""
    id: str
    name: str
    description: str = ""


@dataclass
class PrototypeEstimation:
    """Prototype estimation data for a single project line.
    Stored separately from engineering estimation (inductors/JUs).
    Does not affect FTE, BH, or KM calculations.
    Surfaces in Final Review as a distinct line item."""
    line_id: str
    categories: dict[str, float] = field(default_factory=dict)  # category_id → quantity
    comment: str = ""
    saved: bool = False

    def total_units(self) -> float:
        return sum(self.categories.values())

    def is_empty(self) -> bool:
        return all(q == 0 for q in self.categories.values())


# Default prototype categories (pending formal definition PRE-01)
DEFAULT_PROTOTYPE_CATEGORIES: list[PrototypeCategory] = [
    PrototypeCategory("proto-cat-1", "Greenfield", "Producto nuevo desde cero"),
    PrototypeCategory("proto-cat-2", "Refactor", "Reescritura de módulo existente"),
    PrototypeCategory("proto-cat-3", "Integration", "Conexión con sistemas externos"),
    PrototypeCategory("proto-cat-4", "Maintenance", "Bugfixes y mejoras menores"),
]


# ──────────────────────────────────────────────
# 5b. Parent-Child Line Relationships
# ──────────────────────────────────────────────
# Sección 5.2 del documento funcional:
# "Parent-Child Line Relationships — Pre-Estimation View will display these relationships
#  alongside the project line data. If a related line's HVT attributes are modified,
#  the system will show a warning to alert the estimator."

@dataclass
class LineRelationship:
    """Represents a parent-child relationship between project lines."""
    parent_line_id: str
    child_line_id: str
    relationship_type: str = "parent_child"  # parent_child | sibling


def get_related_line_ids(line_id: str, relationships: list[LineRelationship]) -> list[str]:
    """Get all line IDs related to a given line (both directions)."""
    related = []
    for rel in relationships:
        if rel.parent_line_id == line_id:
            related.append(rel.child_line_id)
        elif rel.child_line_id == line_id:
            related.append(rel.parent_line_id)
    return related


def check_hvt_attribute_changed(line: dict, original_attributes: dict) -> dict | None:
    """Check if HVT attributes on a related line have changed.
    Returns a warning dict if changed, None if unchanged.

    HVT attributes monitored for changes:
    - organ_type, energy_fuel_type, project_ranking, injection_system
    - start_of_project (SP), alliance_code, vehicle_code
    - standard_emissions, client, market"""
    HVT_MONITORED_FIELDS = [
        "organ_type", "energy_fuel_type", "project_ranking", "injection_system",
        "sp_date", "alliance_code", "vehicle_code", "standard_emissions",
        "client", "market"
    ]
    changes = {}
    for field_name in HVT_MONITORED_FIELDS:
        old_val = original_attributes.get(field_name)
        new_val = line.get(field_name)
        if old_val != new_val:
            changes[field_name] = {"old": old_val, "new": new_val}
    if changes:
        return {
            "changed": True,
            "line_id": line.get("id"),
            "fields": changes,
            "message": f"HVT attributes changed on related line {line.get('id')}: "
                       f"{', '.join(changes.keys())}"
        }
    return None

# ──────────────────────────────────────────────
# 6. Inductor & Cran Model
# ──────────────────────────────────────────────

@dataclass
class Cran:
    name: str
    variable_coeff: float
    fixed_coeff: float


@dataclass
class JobUnit:
    short_name: str
    description: str
    variable: float
    fixed: float
    unit_type: str  # "man_day" | "bench_hours" | "kilometres" | "k_euros"
    cran: str
    fmm: str
    smm: str
    dmm: str
    generic_profile: str
    occurrence: float = 0.0
    occurrence_locked: bool = False


@dataclass
class Inductor:
    name: str
    crans: list[Cran] = field(default_factory=list)
    selected_cran: Optional[str] = None
    job_units: list[JobUnit] = field(default_factory=list)
    group_name: Optional[str] = None


# Inductor definitions per métier and compatibility combo
WORKLOAD_STANDARDS: dict[str, list[Inductor]] = {
    "Backend": [
        Inductor(
            name="API endpoints",
            crans=[
                Cran("Simple", 2.0, 0.5),
                Cran("Medium", 4.0, 1.0),
                Cran("Complex", 8.0, 2.0),
            ],
            job_units=[
                JobUnit("API-DEV", "API Development", 2.0, 0.5, "man_day", "Simple", "FMM001", "SMM001", "DMM001", "Backend Dev"),
                JobUnit("API-TEST", "API Testing", 1.0, 0.25, "man_day", "Simple", "FMM001", "SMM001", "DMM001", "Backend QA"),
            ],
        ),
        Inductor(
            name="DB tables",
            crans=[
                Cran("Simple", 1.0, 0.0),
                Cran("Medium", 2.0, 0.5),
                Cran("Complex", 4.0, 1.0),
            ],
            job_units=[
                JobUnit("DB-DESIGN", "Database Design", 1.0, 0.0, "man_day", "Simple", "FMM002", "SMM002", "DMM002", "Backend Dev"),
                JobUnit("DB-MIG", "DB Migration Scripts", 1.0, 0.5, "man_day", "Simple", "FMM002", "SMM002", "DMM002", "Backend Dev"),
            ],
        ),
        Inductor(
            name="Integraciones externas",
            crans=[
                Cran("REST", 3.0, 1.0),
                Cran("SOAP", 5.0, 2.0),
                Cran("GraphQL", 4.0, 1.5),
            ],
            job_units=[
                JobUnit("INT-DEV", "Integration Development", 3.0, 1.0, "man_day", "REST", "FMM003", "SMM003", "DMM003", "Backend Dev"),
                JobUnit("INT-CERT", "Integration Certification", 1.0, 0.5, "man_day", "REST", "FMM003", "SMM003", "DMM003", "Backend QA"),
            ],
        ),
    ],
    "Frontend": [
        Inductor(
            name="Pantallas UI",
            crans=[
                Cran("Simple", 1.5, 0.5),
                Cran("Medium", 3.0, 1.0),
                Cran("Complex", 6.0, 2.0),
            ],
            job_units=[
                JobUnit("UI-DEV", "UI Development", 1.5, 0.5, "man_day", "Simple", "FMM004", "SMM004", "DMM004", "Frontend Dev"),
                JobUnit("UI-COMP", "UI Component", 0.5, 0.25, "man_day", "Simple", "FMM004", "SMM004", "DMM004", "Frontend Dev"),
            ],
        ),
        Inductor(
            name="Componentes reutilizables",
            crans=[
                Cran("Atom", 1.0, 0.0),
                Cran("Molecule", 2.0, 0.5),
                Cran("Organism", 4.0, 1.0),
            ],
            job_units=[
                JobUnit("CMP-DEV", "Component Development", 1.0, 0.0, "man_day", "Atom", "FMM005", "SMM005", "DMM005", "Frontend Dev"),
            ],
        ),
    ],
    "Data": [
        Inductor(
            name="Pipelines ETL",
            crans=[
                Cran("Simple", 3.0, 1.0),
                Cran("Medium", 6.0, 2.0),
                Cran("Complex", 12.0, 4.0),
            ],
            job_units=[
                JobUnit("ETL-DEV", "ETL Pipeline Development", 3.0, 1.0, "man_day", "Simple", "FMM006", "SMM006", "DMM006", "Data Engineer"),
                JobUnit("ETL-TEST", "ETL Testing", 1.0, 0.5, "man_day", "Simple", "FMM006", "SMM006", "DMM006", "Data QA"),
            ],
        ),
        Inductor(
            name="Reportes / dashboards",
            crans=[
                Cran("Simple", 2.0, 0.5),
                Cran("Medium", 4.0, 1.0),
                Cran("Complex", 8.0, 3.0),
            ],
            job_units=[
                JobUnit("RPT-DEV", "Report Development", 2.0, 0.5, "man_day", "Simple", "FMM007", "SMM007", "DMM007", "Data Analyst"),
            ],
        ),
        Inductor(
            name="Migraciones de datos",
            crans=[
                Cran("Small", 2.0, 0.5),
                Cran("Medium", 5.0, 2.0),
                Cran("Large", 10.0, 5.0),
            ],
            job_units=[
                JobUnit("MIG-DATA", "Data Migration", 2.0, 0.5, "man_day", "Small", "FMM008", "SMM008", "DMM008", "Data Engineer"),
            ],
        ),
    ],
    "DevOps": [
        Inductor(
            name="Despliegues infra",
            crans=[
                Cran("Small", 1.0, 0.5),
                Cran("Medium", 3.0, 1.0),
                Cran("Large", 6.0, 2.0),
            ],
            job_units=[
                JobUnit("INFRA-DEPLOY", "Infrastructure Deployment", 1.0, 0.5, "man_day", "Small", "FMM009", "SMM009", "DMM009", "DevOps Engineer"),
                JobUnit("INFRA-MON", "Monitoring Setup", 1.0, 0.5, "man_day", "Small", "FMM009", "SMM009", "DMM009", "DevOps Engineer"),
            ],
        ),
    ],
    "QA": [
        Inductor(
            name="Test cases E2E",
            crans=[
                Cran("Smoke", 0.5, 0.0),
                Cran("Functional", 1.5, 0.5),
                Cran("Regression", 3.0, 1.0),
            ],
            job_units=[
                JobUnit("TC-DESIGN", "Test Case Design", 0.5, 0.0, "man_day", "Smoke", "FMM010", "SMM010", "DMM010", "QA Engineer"),
                JobUnit("TC-EXEC", "Test Execution", 1.0, 0.5, "man_day", "Smoke", "FMM010", "SMM010", "DMM010", "QA Engineer"),
            ],
        ),
    ],
    "Mobile": [
        Inductor(
            name="Vistas mobile",
            crans=[
                Cran("Simple", 1.5, 0.5),
                Cran("Medium", 3.0, 1.5),
                Cran("Complex", 7.0, 2.5),
            ],
            job_units=[
                JobUnit("MOB-DEV", "Mobile Screen Development", 1.5, 0.5, "man_day", "Simple", "FMM011", "SMM011", "DMM011", "Mobile Dev"),
                JobUnit("MOB-TEST", "Mobile Testing", 1.0, 0.5, "man_day", "Simple", "FMM011", "SMM011", "DMM011", "Mobile QA"),
            ],
        ),
    ],
}

# ──────────────────────────────────────────────
# 6. Estimation Calculation
# ──────────────────────────────────────────────

MAN_DAY_FTE_DIVISOR = 209  # Working days per year


def calculate_ju_total(variable: float, occurrence: float, fixed: float) -> float:
    """Total = (Variable × Occurrence) + Fixed"""
    return (variable * occurrence) + fixed


def calculate_fte(man_days: float) -> float:
    """FTE = Total / 209"""
    return man_days / MAN_DAY_FTE_DIVISOR


def distribute_monthly(total: float, sp_date: str, num_months: int = 12) -> list[float]:
    """
    Distribute total across months starting from SP date.
    SP date is always set to 1st of the start month.
    """
    if num_months <= 0:
        return []
    monthly = total / num_months
    return [monthly] * num_months


def aggregate_yearly(monthly_values: list[float], start_year: int) -> dict[str, dict]:
    """Sum monthly values by calendar year."""
    yearly = {}
    for i, val in enumerate(monthly_values):
        year = str(start_year + (i // 12))
        if year not in yearly:
            yearly[year] = {"fte": 0.0, "bh": 0.0, "km": 0.0, "total": 0.0}
        yearly[year]["total"] += val
    return yearly