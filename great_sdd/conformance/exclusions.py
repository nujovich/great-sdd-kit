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
# (policy / UI / data-lifecycle). Each key MUST be a real business-rule id.
NO_FUNCTION_SURFACE_RULES: dict[str, str] = {
    "BR-01": "No-deletion policy — enforced at persistence/UI layer; no callable.",
    "BR-09": "occurrence_locked defaults false — data default, not a function.",
    "BR-10": "Assignment read-only — sourced from HVT; UI/persistence policy.",
    "BR-14": "Comment scoped to (line, metier) — storage shape, no callable.",
    "BR-18": "Prototype data stored separately — persistence policy.",
    "BR-19": "Prototype categories pending definition (PRE-01).",
}
