# GREAT SDD Kit

Specification-Driven Development para el sistema GREAT.

Las reglas de negocio del sistema GREAT están codificadas como **especificaciones ejecutables** — no como documentación, no como prompts, no como tickets de Jira. Los agentes de IA (Claude, Codex, Copilot, Cursor) leen estas specs y generan código que las cumple, validado por tests.

> **Última actualización:** 10 junio 2026 — taxonomía métier `H-*` (HIW-174, v2.0.0) +
> capa de conformance (oracle determinista, golden fixtures cross-language).
> 321 tests, 30 módulos, 6 vistas, 100 reglas de negocio.

## ¿Qué es esto?

Un kit SDD (Spec-Driven Development) que convierte documentos de negocio (PRDs, épicas, historias) en:

1. **Specs estructuradas** — Reglas de negocio con ID, severity, criterios de aceptación
2. **Módulos SDD** — Lógica pura importable como librería
3. **Pipelines** — Orquestación de módulos como blueprint de endpoints
4. **Tests ejecutables** — 321 tests que verifican las 100 reglas
5. **Conformance** — el SDD como *oracle* determinista: golden fixtures JSON que cualquier
   consumidor (Python o TypeScript) usa como contrato para probar que cumple las reglas

```plaintext
Documento (PRD/Épica/Story)
        │
        ▼
great_sdd/specs/      ← 100 reglas estructuradas (6 archivos)
        │
        ▼
great_sdd/modules/    ← 30 módulos SDD (lógica pura)
        │
        ▼
great_sdd/pipeline/   ← 6 pipelines (blueprint de endpoints)
        │
        ▼
tests/                ← 321 tests (pytest)
        │
        ▼
pytest tests/ -v      ← ¿Cumple las 100 reglas? Sí → Merge.
        │
        ▼
great_sdd/conformance/ ← oracle determinista → golden fixtures (contrato cross-language)
```

## 6 Formas de Usar el SDD Kit

| # | Uso | Cuándo | Stack |
|---|-----|--------|-------|
| **1** | **Como librería** | Necesitás lógica de negocio importable en tu código | Python puro. `from great_sdd.modules.pre_estimation import StatusTransitionValidator` |
| **2** | **Como pipeline** | Necesitás orquestar validaciones en orden (blueprint de endpoints) | SDD modules. `run_pipeline(selected_lines, role, metier)` |
| **3** | **Como agente de IA** | Querés que Claude/Copilot/Cursor cumpla reglas sin adivinar | AGENTS.md + CLAUDE.md + .cursorrules → specs |
| **4** | **Como documentación** | Querés docs versionadas y testeables (no PDFs que se pudren) | YAML + Markdown + tests como documentación ejecutable |
| **5** | **Como auditoría** | Necesitás verificar compliance en CI/CD o revisar un PR | pytest + 321 tests. Resultado en segundos |
| **6** | **Como framework extensible** | Querés aplicar SDD a otro dominio (no GREAT) | Copiás `sdd/` (base_spec, base_module, base_pipeline) y creás tus reglas |

Cada uso es independiente: podés usar solo la librería sin tocar los pipelines, o solo los tests sin el agente.

## Arquitectura

```plaintext
great-sdd-kit/
├── AGENTS.md                        ← Instrucciones para agentes de IA (ENTRY POINT)
├── CLAUDE.md                        ← Entry point para Claude Code
├── .cursorrules                     ← Entry point para Cursor IDE
├── .github/copilot-instructions.md  ← Entry point para GitHub Copilot
├── SDD-OVERVIEW.md                  ← Overview del enfoque SDD
├── INTEGRATION.md                   ← Guía de integración paso a paso
│
├── sdd/                             ← SDD Core Framework (reutilizable para otros dominios)
│   ├── __init__.py
│   ├── base_spec.py                 ← Base class para definir specs
│   ├── base_module.py               ← Base class para módulos
│   └── base_pipeline.py             ← Base class para pipelines
│
├── great_sdd/                      ← Dominio: Sistema GREAT
│   ├── __init__.py
│   ├── demo.py                      ← Demo runner
│   ├── specs/                       ← 6 archivos, 100 reglas de negocio
│   │   ├── pre_estimation_specs.py      ← 17 reglas (vista Pre-Estimation)
│   │   ├── estimation_review_specs.py   ← 10 reglas (vista Estimation Review)
│   │   ├── allocation_specs.py          ← 25 reglas (vista Allocation)
│   │   ├── final_review_specs.py        ← 10 reglas (vista Final Review)
│   │   ├── management_view_specs.py     ← 8 reglas (vista Management)
│   │   └── transversal_specs.py         ← 13 reglas (ciclos, versiones, emails)
│   │
│   ├── signatures/                  ← SDD Signatures (contratos input/output)
│   │   ├── pre_estimation.py            ← 8 signatures
│   │   └── estimation_review.py         ← Signatures para Estimation Review
│   │
│   ├── modules/                     ← 30 módulos con lógica pura
│   │   ├── base.py                      ← LM client abstracto (OpenAI-compatible)
│   │   ├── pre_estimation.py            ← 8 módulos (SelectionValidator, PermissionChecker, etc.)
│   │   ├── estimation_review.py         ← Módulos de Estimation Review
│   │   ├── allocation.py               ← Módulos de Allocation
│   │   ├── final_review.py             ← Módulos de Final Review
│   │   ├── management_view.py          ← Módulos de Management View
│   │   └── transversal.py              ← Módulos transversales
│   │
│   └── pipeline/                    ← 6 pipelines (uno por vista)
│       ├── pre_estimation_pipeline.py      ← Pipeline de 7 etapas
│       ├── estimation_review_pipeline.py   ← Pipeline de Estimation Review
│       ├── allocation_pipeline.py          ← Pipeline de Allocation
│       ├── final_review_pipeline.py        ← Pipeline de Final Review
│       ├── management_view_pipeline.py     ← Pipeline de Management View
│       └── transversal_pipeline.py         ← Pipeline transversal
│
└── tests/                           ← 321 tests que verifican las 100 reglas
    ├── sample_data.py                  ← Datos de prueba
    ├── test_pipeline.py                ← Tests de pipeline core
    ├── test_pre_estimation.py          ← Tests de Pre-Estimation
    ├── test_estimation_review.py       ← Tests de Estimation Review
    ├── test_allocation.py              ← Tests de Allocation
    ├── test_final_review.py            ← Tests de Final Review
    ├── test_management_view.py         ← Tests de Management View
    └── test_transversal.py             ← Tests de Transversal
```

## Las 6 Vistas del Sistema GREAT

| Vista | Archivo de Specs | Reglas | Módulos | Pipeline | Tests |
|-------|-----------------|--------|---------|----------|-------|
| **Pre-Estimation** | `pre_estimation_specs.py` | 17 | 7 | 7 etapas | 68 |
| **Estimation Review** | `estimation_review_specs.py` | 10 | — | — | — |
| **Allocation** | `allocation_specs.py` | 16 | — | — | — |
| **Final Review** | `final_review_specs.py` | 10 | — | — | — |
| **Management View** | `management_view_specs.py` | 8 | — | — | — |
| **Transversal** | `transversal_specs.py` | 13 | — | — | — |
| **Signature** `signature_module.py` | — | — | 1 | — | — |
| **Bulk Deletion** `bulk_inductor_deleter.py` | — | 10 | 1 | — | — |
| **TOTAL** | | **~84** | **~7** | **6** | **257** |

## Pipeline: Pre-Estimation (ejemplo)

El pipeline más avanzado es Pre-Estimation con 7 etapas:

| Stage | Módulo | Reglas | Usa LLM |
|-------|--------|--------|---------|
| 1. Selection Validation | `SelectionValidator` | §5 Compatibilidad, null handling | Solo explicación |
| 2. Permission Check | `PermissionChecker` | §2 Roles, BR-10 assignments | No |
| 3-4. Inductors | `InductorSelector` | §6-8 Workload standard, crans | Sí |
| 5. Calculation | `EstimationCalculator` | §9 Fórmulas FTE/BH/KM | No |
| 6. Save Validation | `SaveValidator` | §10 Draft gate, BR-08 SP date | No |
| 7. Distribution | `MonthDistributor` | §9.4-9.5 Monthly/yearly | No |
| 8. Summary | `SummaryGenerator` | §10.3 Pre-save panel | Sí |

Total: 17 reglas cubiertas por este pipeline.

## Reglas de Negocio (78 total)

### Pre-Estimation (BR-01 a BR-17)

- **BR-01**: No deletion — Las estimaciones nunca se borran
- **BR-02**: Draft gate — No existe "Save as Definitive" sin "Save as Draft" antes
- **BR-03**: Estimated = locked — status=Estimated es read-only hasta que CPO actúe
- **BR-04**: Approved = terminal — Approved no cambia por ninguna acción en GREAT
- **BR-05**: Engineer approval inferred — Se infiere del rol, no del action log
- **BR-06**: Multi-select compatibility — 4 campos deben coincidencia para selección múltiple
- **BR-07**: Null injection system — null vs null = compatible; null vs value = no
- **BR-08**: SP date mandatory — No se guarda sin fecha SP
- **BR-09**: Occurrence lock default — Default es locked
- **BR-10**: Assignment read-only — Asignación no se puede cambiar desde UI de estimación
- **BR-11**: Custom JUs unblocked — JUs personalizados no bloquean
- **BR-12**: Inductor without cran — Inductor puede existir sin cran asignado
- **BR-13**: Zero occurrence — Ocurrencia cero es válida
- **BR-14**: Comments scoped to (line, métier) — Comentarios por combo línea/métier
- **BR-15**: Draft is first step — Draft es el primer estado obligatorio
- **BR-16**: Sent = locked — Enviado es irreversible
- **BR-17**: Re-save overwrites — Re-guardar sobreescribe

### Estimation Review (10 reglas)

Reglas del flujo HVT, columnas de aprobación, y envío a validación.

### Allocation (16 reglas)

Reglas de tasas K€, societes, split allocation, TSA/TC, y auto-reglas.

### Final Review (10 reglas)

Reglas de Stage 3 HVT, agregación, y cierre de estimación.

### Management View (8 reglas)

Reglas de dashboard: pie chart, timeline, filtros, y export.

### Transversal (13 reglas)

Reglas de ciclos, versiones, emails, y workload.

## Uso

### Como librería (módulos)

```python
from great_sdd.modules.pre_estimation import StatusTransitionValidator

v = StatusTransitionValidator()
result = v.forward("approved", "draft")
assert result["is_valid"] is False  # Approved es terminal

from great_sdd.specs.allocation_specs import calculate_fte_ke
ke = calculate_fte_ke(fte=1.0, societe_site="Horse Spain S.L.-Valladolid", year="2024")
assert ke == 107.0
```

### Como pipeline

```python
from great_sdd.pipeline.pre_estimation_pipeline import run_pipeline

ctx = run_pipeline(
    selected_lines=[line_1, line_2],
    role="Engineer",
    current_user="Ana Martinez",
    metier="Backend",
)
print(f"Can save draft: {ctx.can_save_draft}")
print(f"Total FTE: {ctx.total_fte}")
```

### Como agente de IA

```bash
# Claude Code / Cursor / Copilot leen automáticamente:
# CLAUDE.md → AGENTS.md → specs/ → modules/ → pipeline/ → tests/
```

Ver `INTEGRATION.md` para la guía completa de integración con agentes.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v              # Todos (321 tests)
python -m pytest tests/test_pre_estimation.py -v  # Solo Pre-Estimation (68 tests)
python -m pytest tests/test_pipeline.py -v        # Pipeline core
```

Cada test verifica una o más reglas de negocio. Si tu código pasa los 321 tests, cumple las 100 reglas.

## Integración en tu proyecto

El SDD Kit se instala como dependencia npm (funciona para proyectos Node y Python):

```bash
# 1. Agregar como dependencia npm
npm install git+https://github.com/nujovich/great-sdd-kit.git

# 2. El código queda en node_modules/great-sdd-kit/
#    - Reglas: node_modules/great-sdd-kit/great_sdd/specs/
#    - Módulos: node_modules/great-sdd-kit/great_sdd/modules/
#    - Tests: node_modules/great-sdd-kit/tests/

# 3. Configurar agentes de IA en tu proyecto
echo "Lee node_modules/great-sdd-kit/AGENTS.md antes de generar código" >> CLAUDE.md
echo "Carga node_modules/great-sdd-kit/AGENTS.md" >> .cursorrules

# 4. Correr tests
pytest node_modules/great-sdd-kit/tests/ -v
```

Ver `INTEGRATION.md` para la guía detallada con troubleshooting.

## Cómo actualizar el SDD Kit en tu proyecto

Cuando el SDD Kit se actualiza en el repo principal (nuevas reglas, fixes, nuevos módulos):

```bash
npm update great-sdd-kit
```

Luego verificá que tu código sigue cumpliendo las reglas:

```bash
pytest node_modules/great-sdd-kit/tests/ -q
```

**Qué hacer si un test falla después de actualizar:**

1. Leyendo el nombre del test que falla, identificá qué regla cambió
2. Revisá el spec correspondiente en `node_modules/great-sdd-kit/great_sdd/specs/`
3. Actualizá tu código para cumplir la nueva regla
4. Corré `pytest node_modules/great-sdd-kit/tests/ -v` hasta que todo pase
5. Commit

**Versionado:** El SDD Kit usa Semantic Versioning (`v1.0.0`, `v1.1.0`, etc.). Para pinchar una versión específica:

```bash
npm install git+https://github.com/nujovich/great-sdd-kit.git#v1.0.0
```

## SDD Core Framework (reutilizable)

El directorio `sdd/` contiene el framework base para aplicar SDD a cualquier dominio:

```plaintext
sdd/
├── base_spec.py      ← Base class para definir specs (ID, severity, criteria)
├── base_module.py    ← Base class para módulos (forward, validate)
└── base_pipeline.py  ← Base class para pipelines (stages, context)
```

Para extender a otro dominio:

1. Copia `sdd/` a tu proyecto
2. Crea `domains/tu_dominio/specs/` con tus reglas
3. Crea `domains/tu_dominio/modules/` con tu lógica
4. Crea `domains/tu_dominio/pipeline/` con tu orquestación
5. Crea `tests/` que verifiquen tus reglas
6. Los módulos base se heredan de `sdd/`


## Conformance (4ª capa)

La cuarta capa convierte al SDD en un **oracle determinista**: una implementación de
referencia contra la cual cualquier consumidor (backend Python o frontend TypeScript)
verifica que su código cumple las reglas de negocio — hermético, sin LLM, sin red, y en CI.

### Cómo funciona

1. **Oracle / generador** (`sdd/base_conformance.py` + `great_sdd/conformance/generate.py`)
   recorre las reglas deterministas, ejecuta casos representativos contra las funciones
   puras y emite **golden fixtures** JSON neutros.
2. **Golden fixtures committeados** (`great_sdd/conformance/fixtures/<vista>.json`) —
   **son el contrato**. El oracle vivo NO es dependencia de runtime del consumidor: solo
   regenera estos archivos. Formato byte-estable (claves ordenadas, sin timestamps):
   misma entrada → mismo archivo byte a byte.
3. **Coverage reporter** (`coverage.py`) calcula % de reglas cubiertas y detecta
   **version skew** (compara el `sdd_version` de los fixtures del consumidor contra el
   oracle). Exit ≠ 0 si baja del umbral o hay skew.
4. **Runner del consumidor** (`runner.py`) carga los fixtures pinneados, corre una
   `consumer_fn` y compara con *exact match*, emitiendo los `rule_ids` ejercitados.

> **Restricción dura — TODO DETERMINISTA.** Los fixtures se generan con un **Tripwire LM**
> inyectado en cada módulo: si una regla cubierta intenta llamar al LM, la generación
> **aborta ruidosamente** (`NonDeterministicError`). Como parte de esto se refactorizó
> `InductorSelector` de LM-driven a un algoritmo determinista basado en reglas
> (match keyword/substring contra `WORKLOAD_STANDARDS` + fallback documentado).

### Uso

```bash
python -m great_sdd.conformance.generate            # (re)generar fixtures
python -m great_sdd.conformance.generate --check     # CI: exit 1 si hay drift
python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70
python -m great_sdd.conformance.runner --emit-report report.json   # consumidor de referencia
python -m great_sdd.conformance.collection generate                 # collections Bruno/Postman desde endpoint fixtures
python -m great_sdd.conformance.collection export --out api.zip      # bundle .zip portable
```

Contrato cross-language (cómo un frontend TS consume los MISMOS fixtures JSON):
ver [`great_sdd/conformance/README.md`](great_sdd/conformance/README.md).

### Cobertura

De las **100 reglas de negocio**, **57 tienen superficie determinista y están
cubiertas por probes reales** (100% de lo cubrible). Las restantes quedan **documentadas
como exclusiones** — nada se descarta en silencio; cada exclusión aparece en el reporte de
coverage y en `great_sdd/conformance/fixtures/_inventory.json`.

<!-- BEGIN QUARANTINE (autogenerado desde great_sdd/conformance/exclusions.py) -->
> ### ⚠️ Reglas en cuarentena (excluidas de la cobertura de conformance)
>
> Estas reglas **NO** están cubiertas por fixtures deterministas. Se listan acá, con su
> descripción y la razón, para que la exclusión sea explícita y auditable.

#### 🔴 LM-only (3) — `NON_DETERMINISTIC_RULES`

Capacidades cuyo *único* output lo produce el LM. No son IDs de regla: la **decisión**
determinista subyacente (p.ej. `is_compatible`) sí está cubierta; lo quarantinado es el
texto/ranking generado por el modelo.

| Capacidad | Razón de la cuarentena |
|-----------|------------------------|
| `GENERATE_PRE_SAVE_SUMMARY` | Summary prose is produced by the LM; the numeric data it summarizes is covered by EstimationCalculator/MonthDistributor. |
| `VALIDATE_LINE_SELECTION:explanation` | incompatibility_reason prose is LM-only; the is_compatible DECISION is covered via are_lines_compatible (BR-06/BR-07). |
| `SELECT_INDUCTOR_CRAN:semantic-ranking` | Free-text best-fit ranking from arbitrary natural language is LM-only. The deterministic refactor covers keyword/substring selection + documented full-standard fallback, not semantic ranking. |

#### ⚪ Sin superficie de función (43) — `NO_FUNCTION_SURFACE_RULES`

Reglas deterministas pero de política / UI / persistencia, sin función pura ejecutable
contra la cual generar un fixture.

| Regla | Descripción | Razón de la cuarentena |
|-------|-------------|------------------------|
| `BR-01` | No deletion — estimations are never deleted by any user under any circumstance | No-deletion policy — enforced at persistence/UI layer; no callable. |
| `BR-09` | Occurrence lock default — occurrence_locked is always false by default | occurrence_locked defaults false — data default, not a function. |
| `BR-10` | Assignment read-only — line-to-engineer assignments come from HVT and cannot be modified in GREAT | Assignment read-only — sourced from HVT; UI/persistence policy. |
| `BR-14` | Comments scoped to (line, métier) — a comment applies to one line+métier combination only | Comment scoped to (line, metier) — storage shape, no callable. |
| `BR-18` | Prototype data separate — prototype quantities are stored separately from engineering estimation; do not affect FTE/BH/KM | Prototype data stored separately — persistence policy. |
| `BR-19` | Prototype categories pending — category names and count are pending definition (PRE-01) | Prototype categories pending definition (PRE-01). |
| `ERev-BR-01` | Read-only page — no data can be edited from Estimation Review | Read-only page — UI policy; no edit function exists. |
| `ERev-BR-05` | Send scope — 'Send all eligible' operates on the current filtered view only | Send scope = current filtered view — UI/view-state policy. |
| `ERev-BR-06` | Engineer scoping — Engineers see only their own (PL, Métier) rows | Engineer row scoping — UI/query scoping, not an ER callable. |
| `ERev-BR-07` | Comments read-only — Rejection comments are not shown in this grid | Rejection comments hidden — UI rendering policy. |
| `ERev-BR-09` | Active cycle only — Grid shows data for the active estimation cycle only | Active cycle only — cycle scoping/query policy. |
| `ALLOC-BR-03` | FTE columns read-only — FTE from approved estimations cannot be modified | FTE columns read-only — UI policy. |
| `ALLOC-BR-05` | Dirty-row tracking — Only modified rows sent to backend on save | Dirty-row tracking — backend persistence detail. |
| `ALLOC-BR-12` | Split undo: full delete only — Restores original single row | Split undo = full delete — UI interaction policy. |
| `ALLOC-BR-14` | Filter persistence — Preserved after all in-page actions | Filter persistence — UI/view-state policy. |
| `ALLOC-BR-15` | Active cycle only | Active cycle only — cycle scoping/query policy. |
| `ALLOC-BR-16` | No finalization action — Final Review reads whatever is saved | No finalization action — absence of behavior; nothing to probe. |
| `ALLOC-BR-18` | Page subtitle text — 'Assignment of approved job units to societes and cost types.' | Page subtitle text — UI string constant; no callable. |
| `ALLOC-BR-19` | Unified grid — Single flat grid; no tabs per PL/métier, no row expansion | Unified grid layout — UI/view policy; no callable. |
| `ALLOC-BR-20` | TC popup trigger — Selecting Cost Type=TC opens a K€ distribution popup immediately | TC popup trigger — UI interaction on cost_type change; no callable. |
| `ALLOC-BR-21` | TC popup running total — Popup shows running total K€ as user edits yearly values | TC popup running total — UI real-time display; no callable. |
| `ALLOC-BR-24` | Split live preview — FTE and K€ per child row update in real-time as percentages change | Split live preview — real-time UI rendering; no callable. |
| `ALLOC-BR-25` | Bulk selection scope — Row selection and 'Check all' operate on the current filtered view only | Bulk selection scope — UI/view-state policy; no callable. |
| `FR-BR-01` | Read-only page — No data can be edited from Final Review | Read-only page — UI policy. |
| `FR-BR-02` | No approval columns — Approval workflow complete before this page | No approval columns — UI rendering policy. |
| `FR-BR-05` | No prototype data — Prototype costs do not appear in Final Review | No prototype data shown — UI rendering policy. |
| `FR-BR-09` | Active cycle only | Active cycle only — cycle scoping/query policy. |
| `MGMT-BR-05` | Single filter for both charts — Métier applies to both simultaneously | Single filter drives both charts — UI wiring policy. |
| `MGMT-BR-06` | Active cycle only — No historical cycle data | Active cycle only — cycle scoping/query policy. |
| `MGMT-BR-07` | On page load refresh — No auto-polling or live updates | Refresh on page load — UI lifecycle policy. |
| `MGMT-BR-08` | Read-only — No data entry, no side effects | Read-only — absence of side effects; nothing to probe. |
| `CYCLE-BR-03` | No deletion — Cycles and their data are never deleted | Cycles never deleted — persistence policy. |
| `WL-BR-03` | Preprocessing on upload — Existing pipeline validates and converts | Preprocessing on upload — pipeline/IO side effect. |
| `WL-BR-04` | Versioned — Each upload is a new version; old versions retained | Versioned uploads — timestamped persistence (not byte-stable). |
| `WL-BR-05` | Isolation — Saved JU coefficients are immutable after save | Saved coefficients immutable — persistence invariant. |
| `WL-BR-06` | Validation before commit — Structural errors reported before persistence | Validation before commit — covered structurally by WL-BR-02 probe; commit is IO. |
| `DEL-BR-03` | Select all shortcut — Header checkbox selects/deselects all visible rows | Select-all shortcut — UI interaction. |
| `DEL-BR-04` | Confirm before delete — Modal confirmation required before批量删除 executes | Confirm modal before delete — UI interaction. |
| `DEL-BR-06` | Deletion is permanent — Deleted inductors are not recoverable from the UI | Deletion permanent — persistence invariant. |
| `DEL-BR-08` | Filter preserves selection — Changing filters preserves current selection state | Filter preserves selection — UI/view-state policy. |
| `EMAIL-BR-01` | Weekly alerts run on a fixed weekly cadence — not configurable | Weekly cadence not configurable — scheduler policy. |
| `EMAIL-BR-02` | No per-user opt-out in current scope | No per-user opt-out — policy. |
| `EMAIL-BR-04` | Email logs retained for the duration of the active cycle | Log retention for active cycle — persistence policy. |
<!-- END QUARANTINE -->

## Stack

| Componente | Tecnología |
|-----------|-----------|
| **Framework SDD** | SDD Kit propio — specs ejecutables + modules + tests |
| **Lenguaje** | Python 3.11+ (backend), TypeScript (frontend del proyecto consumidor) |
| **Tests** | pytest (321 tests) |
| **Agentes IA** | Claude Code, GitHub Copilot, Cursor, Codex |
| **Integración** | CLAUDE.md, .cursorrules, AGENTS.md, copilot-instructions |
| **Distribución** | npm (git+https) — `npm install git+https://...` |
| **Licencia** | MIT |

## Repositorio

[https://github.com/nujovich/great-sdd-kit](https://github.com/nujovich/great-sdd-kit)

## Referencias

- [GitHub Spec Kit](https://github.com/github/spec-kit) — Spec-driven development con agentes
- Piskala, D.B. (2026) — *Spec-Driven Development: From Code to Contract* (AIWare 2026)
- Taghavi, P. & Bhavani, S. (2026) — *Spec Kit Agents: Context-Grounded Agentic Workflows*
- Marri, S.R. (2026) — *Constitutional Spec-Driven Development* (security-by-construction)
