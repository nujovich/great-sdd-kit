"""
GREAT Allocation — SDD-style Signatures.

Each Signature defines the input/output contract for one step of the
Allocation pipeline. Modules in modules/allocation.py honor these contracts.

Signatures map to business rules:
  CHECK_ALLOCATION_PERMISSION  → ALLOC-BR-01 (Approved lines only)
  FILTER_APPROVED_JUS          → ALLOC-BR-01
  MATCH_ALLOCATION_RULES       → ALLOC-BR-02 (Rules skip assigned rows)
  ROUTE_HPROJECT_HNP           → ALLOC-BR-17 (JU metier routing)
  CALCULATE_KE                 → ALLOC-BR-03/04 (FTE read-only, K€ recalc)
  HANDLE_TC_POPUP              → ALLOC-BR-13 (TC societe mandatory)
  HANDLE_SPLIT                 → ALLOC-BR-11 (Split 100%)
  BULK_ASSIGN                  → ALLOC-BR-09/10 (Bulk overwrite, societe only)
  VALIDATE_ALLOCATION_SAVE     → ALLOC-BR-06/07 (TSA/TC blocks, FTE warns)
  CHECK_DROPDOWN_DIVERSITY     → ALLOC-BR-08 (Diversity non-blocking)
"""
from __future__ import annotations

from great_sdd.signatures.pre_estimation import Signature, Field


CHECK_ALLOCATION_PERMISSION = Signature(
    name="CheckAllocationPermission",
    description="Check if a role can view/edit/save in Allocation view. "
                "Admin/PMO/RCRC: full access. Engineer/CPO: no access.",
    inputs=[
        Field("role", "User role: Admin, Engineer, PMO, RCRC, or CPO"),
    ],
    outputs=[
        Field("can_view", "boolean: can view Allocation", field_type="boolean", is_output=True),
        Field("can_edit", "boolean: can edit societe/cost_type", field_type="boolean", is_output=True),
        Field("can_save", "boolean: can save changes", field_type="boolean", is_output=True),
        Field("reason", "explanation of permission decision", is_output=True),
    ],
)

FILTER_APPROVED_JUS = Signature(
    name="FilterApprovedJUs",
    description="Filter job units to only Approved (PL, Métier) pairs. "
                "Only status=Approved JUs appear in Allocation (ALLOC-BR-01).",
    inputs=[
        Field("job_units_json", "JSON array of all job units with status field"),
    ],
    outputs=[
        Field("approved_jus_json", "JSON array of JUs with status=approved", is_output=True),
        Field("excluded_count", "number of JUs excluded by filter", field_type="string", is_output=True),
    ],
)

MATCH_ALLOCATION_RULES = Signature(
    name="MatchAllocationRules",
    description="Match job units to societes using allocation rules. "
                "Skips JUs that already have a societe (ALLOC-BR-02). "
                "Exception rules take unconditional priority. "
                "Most-specific non-exception rule wins. Empty field = wildcard.",
    inputs=[
        Field("job_units_json", "JSON array of JUs to auto-assign"),
        Field("rules_json", "JSON array of allocation rules with fields, societe, cost_type, exception"),
    ],
    outputs=[
        Field("assigned_jus_json", "JSON array of JUs with societe/cost_type assigned", is_output=True),
        Field("unassigned_count", "JUs with no matching rule", field_type="string", is_output=True),
    ],
)

ROUTE_HPROJECT_HNP = Signature(
    name="RouteHProjectHNP",
    description="Apply H-PROJECT/H-NP extra routing after Excel rules. "
                "Standard Emissions in {L83L, L83G, P81A} → Horse Brasil. "
                "Organ Type 'Boite de vitesse' + Alliance starts with 'DB' → Horse Spain. "
                "Organ Type 'Boite de vitesse' otherwise → Horse Romania.",
    inputs=[
        Field("job_units_json", "JSON array of JUs with metier, standard_emissions, organ_type, alliance_code"),
    ],
    outputs=[
        Field("routed_jus_json", "JSON array of JUs with routing applied", is_output=True),
        Field("routed_count", "number of JUs that received extra routing", field_type="string", is_output=True),
    ],
)

CALCULATE_KE = Signature(
    name="CalculateKE",
    description="Calculate K€ from FTE per year using rate tables. "
                "FTE cost type: K€ = FTE × FTE_RATE(societe, year). "
                "TSA cost type: K€ = FTE × TSA_RATE(societe, year). "
                "TC cost type: handled via popup, not here (ALLOC-BR-03/04).",
    inputs=[
        Field("job_units_json", "JSON array of JUs with societe, cost_type, fte_yearly"),
    ],
    outputs=[
        Field("calculated_jus_json", "JSON array of JUs with ke_yearly and total_ke", is_output=True),
    ],
)

HANDLE_TC_POPUP = Signature(
    name="HandleTCPopup",
    description="Handle TC cost type K€ input popup. "
                "Distribute total K€ proportionally to FTE share per year. "
                "Supports per-year overrides. TC requires societe (ALLOC-BR-13).",
    inputs=[
        Field("job_unit_json", "JSON: single JU with fte_yearly"),
        Field("total_ke", "Total K€ entered by RCRC"),
        Field("overrides_json", "Optional per-year overrides {\"2024\": 30.0}", optional=True),
    ],
    outputs=[
        Field("ke_yearly_json", "JSON: per-year K€ distribution", is_output=True),
        Field("total_ke", "Sum of distributed K€", is_output=True),
        Field("cost_type", "Always 'TC'", is_output=True),
    ],
)

HANDLE_SPLIT = Signature(
    name="HandleSplit",
    description="Split a JU's FTE across N societes. "
                "Percentages must sum to 100% (ALLOC-BR-11). "
                "Split undo: full delete only, restores original single row (ALLOC-BR-12).",
    inputs=[
        Field("ju_json", "JSON: original job unit with fte_yearly"),
        Field("splits_json", "JSON array of {societe, percentage}"),
    ],
    outputs=[
        Field("child_jus_json", "JSON array of child JUs with proportional FTE", is_output=True),
        Field("error", "Error message if percentages don't sum to 100%", is_output=True),
    ],
)

BULK_ASSIGN = Signature(
    name="BulkAssign",
    description="Apply one societe to multiple rows. "
                "Always overwrites existing societes (ALLOC-BR-09). "
                "Never changes cost type (ALLOC-BR-10).",
    inputs=[
        Field("rows_json", "JSON array of rows to update"),
        Field("societe", "Target societe name"),
    ],
    outputs=[
        Field("updated_rows_json", "JSON array of rows with new societe", is_output=True),
        Field("assigned_count", "number of rows updated", field_type="string", is_output=True),
    ],
)

VALIDATE_ALLOCATION_SAVE = Signature(
    name="ValidateAllocationSave",
    description="Validate pre-save conditions. "
                "TSA/TC without societe blocks save (ALLOC-BR-06). "
                "FTE without societe = non-blocking warning (ALLOC-BR-07). "
                "Diversity dropdown unresolved = non-blocking (ALLOC-BR-08).",
    inputs=[
        Field("job_units_json", "JSON array of JUs to validate"),
    ],
    outputs=[
        Field("can_save", "boolean: no blocking errors", field_type="boolean", is_output=True),
        Field("errors_json", "JSON array of blocking error messages", is_output=True),
        Field("warnings_json", "JSON array of non-blocking warnings", is_output=True),
    ],
)

CHECK_DROPDOWN_DIVERSITY = Signature(
    name="CheckDropdownDiversity",
    description="Flag JUs that require diversity selection (H-DESIGN, H-TESTING, H-CUSTOMER). "
                "Unresolved diversity does not block save (ALLOC-BR-08).",
    inputs=[
        Field("job_units_json", "JSON array of JUs with metier and ju_code"),
    ],
    outputs=[
        Field("flagged_jus_json", "JSON array with _needs_diversity flags", is_output=True),
        Field("unresolved_count", "JUs needing diversity selection", field_type="string", is_output=True),
    ],
)
