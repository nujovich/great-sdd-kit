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

## [2.2.1] — 2026-06-16

### Changed (HIW-178 — Management View aligned with PRD)
- RCRC granted read-only access to the Management View. `MANAGEMENT_ACCESS[RCRC] = True`
  and `MGMT-BR-01` reworded to "PMO, Admin and RCRC only — Engineer and CPO cannot access".
- Conformance fixtures regenerated; project version bumped to 2.2.1 (`pyproject.toml`,
  `package.json`). Canonical rule count unchanged at 100.

---

## [2.2.0] — 2026-06-15

### Added (HIW-176 — Allocation PRD alignment)
- 8 new Allocation rules `ALLOC-BR-18`..`ALLOC-BR-25` (page subtitle, unified flat grid,
  TC popup trigger/running total, split minimum of 2 societes, split FTE invariant,
  split live preview, bulk selection scope). Allocation rules: 17 → 25; total 92 → 100.
- `fte_yearly` / `ke_yearly` per-active-year columns in the Allocation grid spec.

### Changed
- `ALLOC-BR-08`: diversity dropdown removed from the Allocation view.
- `ALLOC-BR-14`: filter persistence clarified — reset only on page navigation.

---

## [2.1.0] — 2026-06-11

### Added
- Add §12.2 legacy-cycle copy merge rules (`merge_legacy_estimation`) + pytest.

---

## [2.0.0] — 2026-06-10

### ⚠ BREAKING CHANGES (HIW-174 — Pre-Estimation PRD alignment)
- Renamed line status `Rejected`/`rejected` → `Modification Requested`/`modification_requested`
  (`LineStatus.MODIFICATION_REQUESTED`), updating `STATUS_TRANSITIONS` and `EDITABLE_STATUSES`.
- Migrated métier taxonomy from generic names to `H-*`: `METIERS` and `WORKLOAD_STANDARDS` keys
  (Backend→H-DESIGN, Frontend→H-SOFTWARE, Data→H-TUNING, DevOps→H-PROJECT, QA→H-TESTING, Mobile→H-CUSTOMER).
- `CUSTOM_JU_ROLES["PMO"]` is now `False` — PMO can no longer create Custom JUs (BR-20).

### Changed
- `EXCLUDED_METIERS_FROM_FILTER` now includes `H-TESTING` (alongside `H-NP`, `H-PROJECT`).

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
