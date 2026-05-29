# Changelog

All notable changes to the GREAT SDD Kit will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Estimation Review, Allocation, Final Review, Management View modules (only Pre-Estimation fully implemented)
- Pipeline execution context improvements
- Type hints consolidation across all modules

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
