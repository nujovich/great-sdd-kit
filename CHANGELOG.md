# Changelog

All notable changes to the GREAT SDD Kit will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Test coverage for `merge_legacy_estimation` rule-2 zero-variable guard [HIW-174]
- Design spec + implementation plan: full-API collection coverage from vendored OpenAPI
  (HIW-175 sub-project 1 — 43 endpoints, 6 view folders, deterministic example synthesis)

### Changed
- Estimation Review spec aligned with HIW-175 PRD decisions:
  - `GRID_DEFAULT_GROUPING = "pl_number"` (group by PL, not by status)
  - `can_export_csv` → `can_export_selected` + `can_export_all_filtered` (two explicit export modes)
  - ERev-BR-04/05 replaced with grid-grouping and CSV-export-mode rules

### Removed
- Send-to-HVT action and all related specs/modules/tests (manual send removed per HIW-175 product decision)
- `CheckSendEligibility` and `GenerateHVTPayload` signatures/modules
- ERev-01 pending definition (send trigger resolved: removed)

---

## [2.1.0] — 2026-06-11

### Added
- **`merge_legacy_estimation`** module: §12.2 legacy-cycle copy merge rules [HIW-174]
  — copies historical estimation data when a project restarts a legacy cycle
- **Endpoint conformance sub-layer** (`great_sdd/conformance/endpoints/`):
  - `EndpointProbe` primitive + endpoint fixture runner
  - Deterministic oracle for `GET /project-lines` with seed + committed golden fixture
  - Endpoint coverage reported separately in the `coverage` gate
- **Collection export** (`great_sdd/conformance/collection.py`):
  - Native Bruno `.bru` builder (conformance scenarios → importable collection)
  - Postman v2.1 builder: JSON Schema docs in request/response + per-case examples
  - `collection generate` CLI command + committed artifacts
  - `collection export` CLI command — deterministic `.zip` bundle
  - HTTP binding declared for `GET /project-lines` (method, path, query params, JSON Schema)

### Fixed
- 3.8 import-compat in conformance layer (regression from 2.0.0 migration)
- Bruno block builder: embedded JSON braces no longer close the outer block prematurely
- Postman examples: disabled optional params, no `Authorization` header on 401 cases,
  text preview for empty bodies, status text labels

### Stats
- 92 business rules (6 views)
- 321 tests (all passing)
- 1 endpoint oracle (`GET /project-lines`)

---

## [2.0.0] — 2026-06-10

### ⚠ BREAKING CHANGES (HIW-174 — Pre-Estimation PRD alignment)
- Renamed line status `Rejected`/`rejected` → `Modification Requested`/`modification_requested`
  (`LineStatus.MODIFICATION_REQUESTED`), updating `STATUS_TRANSITIONS`, `EDITABLE_STATUSES`,
  email labels, and all signature prose
- Migrated métier taxonomy from generic names to `H-*` keys in `METIERS` and `WORKLOAD_STANDARDS`:
  Backend→`H-DESIGN`, Frontend→`H-SOFTWARE`, Data→`H-TUNING`,
  DevOps→`H-PROJECT`, QA→`H-TESTING`, Mobile→`H-CUSTOMER`
- `CUSTOM_JU_ROLES["PMO"]` is now `False` — PMO can no longer create Custom JUs (BR-20)

### Changed
- `EXCLUDED_METIERS_FROM_FILTER` now includes `H-TESTING` (alongside `H-NP`, `H-PROJECT`)

### Stats
- 92 business rules (6 views)
- 320 tests (all passing)

---

## [1.3.0] — 2026-06-05

### Added
- **Conformance layer** (`great_sdd/conformance/`): 4th layer — the SDD as a deterministic oracle
  - `conformance_engine.py`: fixtures, coverage, version-skew detection, Tripwire LM
  - `rule_inventory.py`: canonical rule census (92 total, 55 coverable, 37 documented exclusions)
  - Conformance probes for all 6 views with committed golden fixtures (`fixtures/`)
  - CLI: `generate --check` (CI drift gate), `coverage --from-fixtures --threshold`
  - Reference Python consumer + cross-language contract documented
- **CI gate**: conformance fixture sync, pytest, and coverage threshold in pipeline
- **`BasePipeline`** (`sdd/base_pipeline.py`): documented base class for pipeline extension
- **Deterministic `InductorSelector`**: rule-based, no LM dependency
- Golden fixtures stamped as `sdd_version 1.3.0`

### Changed
- Rule count reconciled to 92 (derived programmatically via `rule_inventory.py` — not hardcoded)
- Test count updated to 320 across all views

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
