# Changelog

All notable changes to the GREAT SDD Kit will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Management View and Transversal signatures (Allocation and Final Review done)
- Pipeline execution context improvements
- Type hints consolidation across all modules

---

## [1.3.0] — 2026-06-05

### Added
- **Conformance layer (4th layer)** — the SDD as a deterministic oracle.
  - `sdd/base_conformance.py` (domain-agnostic engine): `Probe`, `TripwireLM`
    determinism guard, `canonical_json`, `normalize_output`, `read_version`,
    `generate_fixtures`, `compute_coverage`, `compute_version_skew`, `run_conformance`.
  - `sdd/base_pipeline.py` — documented base-pipeline extension point.
  - `great_sdd/conformance/`: `generate.py` (probes for 6 views), committed golden
    `fixtures/*.json`, `rule_inventory.py`, `exclusions.py`, `coverage.py`,
    `runner.py` + reference consumer, cross-language `README.md`.
  - CI gate `.github/workflows/conformance.yml`: fixture-sync + pytest + coverage.
  - Coverage: 55/55 deterministic-surface business rules (100% of coverable);
    37 policy/UI/persistence rules and 3 LM-only capabilities documented as exclusions.

### Changed
- **`InductorSelector` refactored** from LM-driven to deterministic rule-based
  selection (keyword/substring match + documented full-standard fallback).
- Reconciled rule count to **92** (derived by `rule_inventory`) across
  README/AGENTS/SDD-OVERVIEW; test count corrected to 320; fixed stale
  `test_pre_estimation.py` reference (tests live in `test_pipeline.py`).
- `scripts/bump_version.py` now syncs `package.json` and stages `CHANGELOG.md`.

### Fixed
- Version drift across `__init__`, `pyproject.toml`, `package.json`.
- `node_modules/` was committed — now untracked and gitignored.

---

## [1.2.0] — 2026-06-04

### Added
- **Allocation signatures** (`signatures/allocation.py`): 10 signatures covering ALLOC-BR-01..17
  - `CHECK_ALLOCATION_PERMISSION`, `FILTER_APPROVED_JUS`, `MATCH_ALLOCATION_RULES`
  - `ROUTE_HPROJECT_HNP`, `CALCULATE_KE`, `HANDLE_TC_POPUP`, `HANDLE_SPLIT`
  - `BULK_ASSIGN`, `VALIDATE_ALLOCATION_SAVE`, `CHECK_DROPDOWN_DIVERSITY`
- **Final Review signatures** (`signatures/final_review.py`): 6 signatures covering FR-BR-01..10
  - `CHECK_FINAL_REVIEW_PERMISSION`, `FILTER_FINAL_REVIEW_JUS`, `AGGREGATE_FINAL_REVIEW`
  - `EXPORT_FINAL_REVIEW_CSV`, `SEND_STAGE3`, `CALCULATE_SUBTOTALS`
- **Refactored modules**: All Allocation and Final Review modules now use `SignatureModule`
- **Expanded tests**: Allocation 33→46 tests, Final Review 15→26 tests (business rule coverage)

### Changed
- `AllocationPipeline` and `FinalReviewPipeline` adapted for JSON string I/O between pipeline and modules
- `signatures/__init__.py` exports updated with Allocation and Final Review signatures

### Stats
- 78 business rules in executable specs (6 views)
- 293 tests (all passing)
- 30 modules (pure Python, no external dependencies)
- 6 pipelines (blueprints for backend endpoints)
- 26 signatures (Pre-Estimation 8, Estimation Review 6, Allocation 10, Final Review 6)

---

## [1.1.0] — 2026-06-02

### Added
- **BR-20 Custom JU permissions**: `CUSTOM_JU_ROLES` dict, `can_create_custom_ju()` helper, `CustomJUPermissionChecker` module
- 6 new tests for BR-20 permission checks

### Stats
- 78 business rules in executable specs (6 views)
- 257 tests (all passing)

---

## [1.0.0] — 2026-05-29

### Added
- **Packaging**: `pyproject.toml` with setuptools — `pip install git+https://...` support
- **`__version__`**: Runtime version accessible via `great_sdd.__version__`
- **Versioning system**: Semantic versioning with git tags, changelog, and bump script

### Changed
- **Renamed** `great_dspy/` → `great_sdd/` — no more misleading DSPy references
- **Rewrote `base.py`**: LMClient + Module, zero DSPy mentions
- **Rewrote `signature_module.py`**: Pure contract validation, no DSPy stubs
- **Rewrote `demo.py`**: Uses LMClient instead of `dspy.LM`
- **Patched 27 Python files**: All imports updated (`great_dspy` → `great_sdd`)
- **Patched 7 markdown/config files**: No more DSPy references
- **Removed** fake `sdd` pip dependency from `requirements.txt`

### Removed
- All Stanford DSPy references — the kit never used DSPy, just named itself after it
- `import dspy` from `demo.py` — replaced with `LMClient` from `great_sdd.modules.base`

### Stats
- 78 business rules in executable specs (6 views)
- 257 tests (all passing)
- 30 modules (pure Python, no external dependencies)
- 6 pipelines (blueprints for backend endpoints)

---

## Pre-1.0 (unreleased development)

The SDD Kit was developed iteratively from May 26 to May 29, 2026.

Key milestones:
- **May 26**: Initial structure — specs, modules, signatures, AGENTS.md, CLAUDE.md
- **May 27**: Transversal features, allocation, final review, management view specs + tests (257 total)
- **May 28**: Bulk inductor deletion rules (DEL-BR-01..10), README rewrite, submodule integration guide
- **May 29**: Rename to `great_sdd`, packaging, versioning
