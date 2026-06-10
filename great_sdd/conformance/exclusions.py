"""Documented conformance exclusions — surfaced in every coverage report.

NEVER silently drop a rule. If a rule is excluded from conformance coverage, it is
HERE with a written reason. Two buckets:

  NON_DETERMINISTIC_RULES   — capabilities whose ONLY output is LM-generated.
  NO_FUNCTION_SURFACE_RULES — deterministic business rules with no pure-function
                              to execute (policy / UI / data-lifecycle).
"""

# Capabilities whose ONLY output is LM-generated (no deterministic contract).
# Keyed by capability tag (signature[:aspect]), not always a business-rule id.
NON_DETERMINISTIC_RULES: dict[str, str] = {
    "GENERATE_PRE_SAVE_SUMMARY": "Summary prose is produced by the LM; the numeric "
        "data it summarizes is covered by EstimationCalculator/MonthDistributor.",
    "VALIDATE_LINE_SELECTION:explanation": "incompatibility_reason prose is LM-only; "
        "the is_compatible DECISION is covered via are_lines_compatible (BR-06/BR-07).",
    "SELECT_INDUCTOR_CRAN:semantic-ranking": "Free-text best-fit ranking from arbitrary "
        "natural language is LM-only. The deterministic refactor covers keyword/substring "
        "selection + documented full-standard fallback, not semantic ranking.",
}

# Deterministic business rules with no pure-function surface to execute
# (policy / UI / data-lifecycle / timestamped persistence). Each key MUST be a
# real business-rule id. Covered + these = the full 92 (see test_conformance).
NO_FUNCTION_SURFACE_RULES: dict[str, str] = {
    # Pre-Estimation
    "BR-01": "No-deletion policy — enforced at persistence/UI layer; no callable.",
    "BR-09": "occurrence_locked defaults false — data default, not a function.",
    "BR-10": "Assignment read-only — sourced from HVT; UI/persistence policy.",
    "BR-14": "Comment scoped to (line, metier) — storage shape, no callable.",
    "BR-18": "Prototype data stored separately — persistence policy.",
    "BR-19": "Prototype categories pending definition (PRE-01).",
    # Estimation Review
    "ERev-BR-01": "Read-only page — UI policy; no edit function exists.",
    "ERev-BR-05": "Send scope = current filtered view — UI/view-state policy.",
    "ERev-BR-06": "Engineer row scoping — UI/query scoping, not an ER callable.",
    "ERev-BR-07": "Rejection comments hidden — UI rendering policy.",
    "ERev-BR-09": "Active cycle only — cycle scoping/query policy.",
    # Allocation
    "ALLOC-BR-03": "FTE columns read-only — UI policy.",
    "ALLOC-BR-05": "Dirty-row tracking — backend persistence detail.",
    "ALLOC-BR-12": "Split undo = full delete — UI interaction policy.",
    "ALLOC-BR-14": "Filter persistence — UI/view-state policy.",
    "ALLOC-BR-15": "Active cycle only — cycle scoping/query policy.",
    "ALLOC-BR-16": "No finalization action — absence of behavior; nothing to probe.",
    # Final Review
    "FR-BR-01": "Read-only page — UI policy.",
    "FR-BR-02": "No approval columns — UI rendering policy.",
    "FR-BR-05": "No prototype data shown — UI rendering policy.",
    "FR-BR-09": "Active cycle only — cycle scoping/query policy.",
    # Management View
    "MGMT-BR-05": "Single filter drives both charts — UI wiring policy.",
    "MGMT-BR-06": "Active cycle only — cycle scoping/query policy.",
    "MGMT-BR-07": "Refresh on page load — UI lifecycle policy.",
    "MGMT-BR-08": "Read-only — absence of side effects; nothing to probe.",
    # Transversal — Cycles
    "CYCLE-BR-03": "Cycles never deleted — persistence policy.",
    # Transversal — Workload Standard
    "WL-BR-03": "Preprocessing on upload — pipeline/IO side effect.",
    "WL-BR-04": "Versioned uploads — timestamped persistence (not byte-stable).",
    "WL-BR-05": "Saved coefficients immutable — persistence invariant.",
    "WL-BR-06": "Validation before commit — covered structurally by WL-BR-02 probe; commit is IO.",
    # Transversal — Bulk Deletion (UI interactions)
    "DEL-BR-03": "Select-all shortcut — UI interaction.",
    "DEL-BR-04": "Confirm modal before delete — UI interaction.",
    "DEL-BR-06": "Deletion permanent — persistence invariant.",
    "DEL-BR-08": "Filter preserves selection — UI/view-state policy.",
    # Transversal — Email
    "EMAIL-BR-01": "Weekly cadence not configurable — scheduler policy.",
    "EMAIL-BR-02": "No per-user opt-out — policy.",
    "EMAIL-BR-04": "Log retention for active cycle — persistence policy.",
}
