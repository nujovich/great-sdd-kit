# GREAT System — Developer Implementation Guide

## Qué es este repo

Este repositorio contiene **las reglas de negocio del sistema GREAT ejecutándose como tests**.

No es una app. Es el **contrato verificable** contra el que cualquier implementación (backend, API, UI) debe validarse. Si tu código pasa los 216 tests, cumple las 74 reglas de negocio. Si no, hay una violación de spec.

```
216 tests = 74 reglas de negocio verificadas
```

---

## Cómo usar esto para desarrollar

### 1. La regla de oro

**Nunca implementes una regla de negocio en el backend sin verla reflejada en `specs/` primero.**

Si el PO dice "ahora CPO también edita en Pre-Estimation", el cambio empieza en:

```python
# specs/pre_estimation_specs.py
ROLE_PERMISSIONS[Role.CPO] = RolePermission(can_view=True, can_edit=True, scope="all")
```

Luego corres `pytest` para ver qué tests se rompen (y arreglarlos). Eso te dice qué backend y UI tienes que tocar.

### 2. Flujo de desarrollo para una feature

```
1. PO cambia regla → 2. Editas specs/*.py → 3. pytest (fallan X tests)
→ 4. Arreglas módulos en modules/*.py → 5. pytest (pasan todos)
→ 6. Implementas API endpoint que llama al pipeline
→ 7. Conectas UI al endpoint
```

Sin sorpresas. Sin "esto funciona en local pero no en prod".

---

## Mapa del repositorio

```
great_dspy/
├── specs/                    ← REGLAS DE NEGOCIO (lo que NO cambia)
│   ├── pre_estimation_specs.py     # 17 BR, state machine, 6 métiers, fórmulas
│   ├── estimation_review_specs.py  # 10 BR, HVT flow, approval columns
│   ├── allocation_specs.py         # 16 BR, K€ rates, societes, split
│   ├── final_review_specs.py       # 10 BR, Stage 3, aggregation
│   ├── management_view_specs.py    # 8 BR, pie chart, timeline
│   └── transversal_specs.py        # 13 BR, cycles, workload, tables, email
│
├── modules/                  ← LÓGICA PURA (importable desde cualquier backend)
│   ├── base.py                     # LM client base
│   ├── pre_estimation.py           # 8 módulos (SelectionValidator, etc.)
│   ├── estimation_review.py        # 6 módulos (SendEligibilityChecker, etc.)
│   ├── allocation.py               # 9 módulos (KECalculator, TCPopupHandler, etc.)
│   ├── final_review.py             # 4 módulos (AggregationEngine, Stage3Sender)
│   ├── management_view.py          # 3 módulos (PieChartBuilder, TimelineBuilder)
│   └── transversal.py              # 4 módulos (CycleManager, EmailAlertService)
│
├── pipeline/                 ← ORQUESTACIÓN (llama a módulos en orden)
│   ├── pre_estimation_pipeline.py
│   ├── estimation_review_pipeline.py
│   ├── allocation_pipeline.py
│   ├── final_review_pipeline.py
│   ├── management_view_pipeline.py
│   └── transversal_pipeline.py
│
├── signatures/               ← CONTRATOS (input/output DSPy-style)
│
├── tests/                    ← 216 tests que VERIFICAN las reglas
│   ├── test_pipeline.py            # 68 tests
│   ├── test_estimation_review.py   # 62 tests
│   ├── test_allocation.py          # 27 tests
│   ├── test_final_review.py        # 17 tests
│   ├── test_management_view.py     # 14 tests
│   └── test_transversal.py         # 31 tests
│
└── SDD-OVERVIEW.md           ← Este archivo
```

---

## Las 6 vistas — Blueprint para implementación

Cada vista tiene un pipeline documentado. Para implementar una vista:

1. Crear los endpoints de API necesarios
2. Cada endpoint llama a una etapa del pipeline
3. El pipeline valida contra las specs ANTES de escribir en DB
4. Los tests del pipeline son tus tests de integración

### Pre-Estimation

```
Pipeline: SelectionValidator → PermissionChecker → InductorSelector
          → EstimationCalculator → SaveValidator → MonthDistributor → SummaryGenerator

API endpoints necesarios:
  GET  /api/pre-estimation/lines          → devuelve líneas filtradas por rol
  POST /api/pre-estimation/select-lines   → valida compatibilidad (§5)
  POST /api/pre-estimation/save-draft     → valida + persiste Draft (§10.1)
  POST /api/pre-estimation/save-definitive → valida Draft gate + persiste (§10.2)

DB tables mínimas:
  project_lines, estimations, job_units, inductors, status_history

Reglas clave que el backend NO puede violar:
  - BR-02: No existe "Save as Definitive" sin "Save as Draft" antes
  - BR-03: status=Estimated = read-only (ni el engineer puede editarlo)
  - BR-06: Multi-line selection validada por 4 campos
  - BR-08: SP date obligatorio para guardar
```

### Estimation Review

```
Pipeline: PermissionChecker → ApprovalColumnDeriver → SendEligibilityChecker
          → HVTPayloadGenerator → CSVExporter → HVTCallbackProcessor

API endpoints:
  GET  /api/estimation-review/rows       → grid con derived columns
  POST /api/estimation-review/send-to-hvt → solo Estimated elegibles (§6)
  POST /api/estimation-review/hvt-callback → Sent→Approved/Rejected (§7)
  GET  /api/estimation-review/export-csv  → CSV con yearly columns

Reglas clave:
  - ERev-BR-01: Read-only page (no hay PUT/PATCH en esta vista)
  - ERev-BR-02: Sent = irreversible (no hay "unsend")
  - ERev-BR-04: Solo Estimated se envía (Draft/To do silenciosamente ignorados)
  - Approval columns son DERIVADAS de status, nunca editables
```

### Allocation

```
Pipeline: PermissionChecker → EligibilityFilter → RuleMatcher → HProjectRouter
          → DiversityHandler → KECalculator → SaveValidator

API endpoints:
  GET  /api/allocation/job-units         → solo Approved lines (§3)
  POST /api/allocation/assign-rules      → auto-asignar societes (§4)
  POST /api/allocation/set-tc-ke         → TC popup K€ distribution (§8)
  POST /api/allocation/split             → split JU across N societes (§10)
  POST /api/allocation/bulk-assign       → bulk societe assignment (§9)
  POST /api/allocation/save              → dirty-row tracking + K€ recalculation

Reglas clave:
  - ALLOC-BR-01: Solo Approved (PL, Métier) aparecen
  - ALLOC-BR-02: Auto-rules NO sobrescriben asignaciones manuales
  - ALLOC-BR-06: TSA/TC sin societe BLOQUEA el save
  - ALLOC-BR-11: Split percentages = 100% obligatorio
  - ALLOC-BR-13: TC rows: societe mandatory
```

### Final Review

```
Pipeline: PermissionChecker → EligibilityFilter → AggregationEngine
          → CSVExporter → Stage3Sender

API endpoints:
  GET  /api/final-review/pl/{id}         → tab por project line con 5 niveles
  GET  /api/final-review/pl/{id}/export  → Excel export per PL (§6)
  GET  /api/final-review/export-all      → CSV global export (§7)
  POST /api/final-review/send-stage3     → envía a HVT con warning (§8)

Reglas clave:
  - FR-BR-01: Read-only (no hay edits)
  - FR-BR-03: Solo Approved aparecen
  - FR-BR-04: Todos los roles ven todas las líneas
  - FR-BR-06: Stage 3 NO bloquea por asignación incompleta (solo warning)
  - FR-BR-07: Stage 3 re-sendable múltiples veces
```

### Management View

```
Pipeline: AccessChecker → MetierFilter → PieChartBuilder → TimelineBuilder

API endpoints:
  GET  /api/management/status-distribution → pie chart data (§6)
  GET  /api/management/status-timeline     → timeline chart data (§7)
  GET  /api/management/summary             → métier filter aplicado a ambos

Reglas clave:
  - MGMT-BR-01: Solo PMO/Admin acceden
  - MGMT-BR-02: Cuenta (PL, Métier) PAIRS, no PL únicos
  - MGMT-BR-04: H-NP y H-PROJECT excluidos del filtro
  - MGMT-BR-07: Sin auto-refresh — datos al cargar página
```

### Transversal

```
Módulos independientes (no comparten pipeline):

CycleManager:
  POST /api/cycles  → crea + auto-desactiva el anterior
  GET  /api/cycles  → lista ciclos (activo + históricos)

WorkloadStandardManager:
  POST /api/workload/upload  → sube .xlsx, valida, versiona
  GET  /api/workload/versions → historial de versiones

EmailAlertService:
  POST /api/email/engineer-weekly
  POST /api/email/rcrc-weekly
  POST /api/email/rejection-notification
```

---

## Integración con HVT

El flujo HVT cruza 3 vistas:

```
Pre-Estimation: Engineer crea y guarda estimación
      ↓ status = Estimated
Estimation Review: PMO envía a HVT
      ↓ status = Sent
        HVT: CPO aprueba o rechaza
      ↓ callback
Estimation Review: Procesa callback → Approved o Rejected
      ↓ status = Approved
Allocation: RCRC asigna societes y K€
      ↓
Final Review: PMO revisa y envía Stage 3
```

**Pendientes que bloquean:**
- ERev-01: Confirmar trigger manual vs automático de "Send to HVT"
- ERev-02: Acordar payload exacto con equipo HVT
- FINAL-01: Acordar payload de Stage 3 con equipo HVT

---

## Cómo exportar módulos a tu backend

Cada módulo es **Python puro sin dependencias externas** (no requiere Django, FastAPI, etc.).

```python
# Ejemplo: usar SaveValidator en un endpoint FastAPI
from great_dspy.modules.pre_estimation import SaveValidator

@app.post("/api/pre-estimation/save-draft")
def save_draft(line: dict):
    validator = SaveValidator()
    result = validator.forward(line, "draft")
    if not result["can_save"]:
        return {"status": 422, "errors": result["validation_errors"]}
    # ... persistir en DB
    return {"status": "draft_saved"}
```

```python
# Ejemplo: validar transición de estado en cualquier endpoint
from great_dspy.modules.pre_estimation import StatusTransitionValidator

validator = StatusTransitionValidator()
result = validator.forward("to_do", "estimated")
assert result["is_valid"] is False  # Draft gate!
```

```python
# Ejemplo: calcular K€ en Allocation
from great_dspy.specs.allocation_specs import calculate_fte_ke

ke = calculate_fte_ke(fte=1.0, societe_site="Horse Spain S.L.-Valladolid", year="2024")
# → 107.0
```

```python
# Ejemplo: validar split percentages
from great_dspy.specs.allocation_specs import apply_split

try:
    splits = apply_split({"2024": 1.0}, [
        {"societe": "A", "percentage": 60},
        {"societe": "B", "percentage": 40},
    ])
except ValueError as e:
    return {"error": str(e)}  # "must sum to 100%"
```

---

## Tabla de reglas completa

### Pre-Estimation (17)

| ID | Regla | ¿Dónde se aplica? |
|----|-------|-------------------|
| BR-01 | No deletion — nunca se borra una estimación | DB layer, API DELETE |
| BR-02 | Draft gate — Definitive requiere Draft primero | SaveValidator |
| BR-03 | Estimated = locked — read-only | StatusTransitionValidator |
| BR-04 | Approved = terminal | StatusTransitionValidator |
| BR-05 | Engineer approval inferido de status=Estimated | ApprovalColumnDeriver |
| BR-06 | Multi-select compatibility (4 campos) | SelectionValidator |
| BR-07 | null vs null compatible; null vs value no | are_lines_compatible() |
| BR-08 | SP date mandatory bloquea save | SaveValidator |
| BR-09 | occurrence_locked default = false | UI default |
| BR-10 | Assignments read-only desde HVT | PermissionChecker |
| BR-11 | Custom JUs permitidos sin workload standard | SaveValidator |
| BR-12 | Inductor sin cran = skip silencioso | EstimationCalculator |
| BR-13 | Zero occurrence permitido (output = 0) | EstimationCalculator |
| BR-14 | Comments scoped a (line, métier) | CommentSection |
| BR-15 | Draft es siempre el primer paso | StatusTransitionValidator |
| BR-16 | Sent = locked | StatusTransitionValidator |
| BR-17 | Re-save overwrites Draft anterior | DB layer |

### Estimation Review (10)

| ID | Regla | ¿Dónde se aplica? |
|----|-------|-------------------|
| ERev-BR-01 | Read-only page | PermissionChecker |
| ERev-BR-02 | Sent = irreversible | SendEligibilityChecker |
| ERev-BR-03 | Approved = terminal | StatusTransitionValidator |
| ERev-BR-04 | Solo Estimated elegible para send | SendEligibilityChecker |
| ERev-BR-05 | Send opera sobre filtered view actual | Send scope logic |
| ERev-BR-06 | Engineers ven solo sus rows | Scope filter |
| ERev-BR-07 | Comments no visibles en grid | ApprovalColumnDeriver |
| ERev-BR-08 | No approval gestures manuales | UI design |
| ERev-BR-09 | Active cycle only | Cycle scope |
| ERev-BR-10 | CPO column solo vía HVT callback | HVTCallbackProcessor |

### Allocation (16)

| ID | Regla | ¿Dónde se aplica? |
|----|-------|-------------------|
| ALLOC-BR-01 | Approved lines only | EligibilityFilter |
| ALLOC-BR-02 | Rules skip assigned rows | RuleMatcher |
| ALLOC-BR-03 | FTE columns read-only | KECalculator |
| ALLOC-BR-04 | K€ recalculated on save | KECalculator + save trigger |
| ALLOC-BR-05 | Dirty-row tracking | Save logic |
| ALLOC-BR-06 | TSA/TC sin societe BLOCKEA save | SaveValidator |
| ALLOC-BR-07 | FTE sin societe = warning no blocking | SaveValidator |
| ALLOC-BR-08 | Diversity dropdown no blocking | DiversityHandler |
| ALLOC-BR-09 | Bulk assignment OVERWRITES siempre | BulkAssigner |
| ALLOC-BR-10 | Bulk assignment: societe only, no cost type | BulkAssigner |
| ALLOC-BR-11 | Split: percentages sum 100% | apply_split() |
| ALLOC-BR-12 | Split undo: full delete only | SplitAllocationHandler |
| ALLOC-BR-13 | TC: societe mandatory | SaveValidator |
| ALLOC-BR-14 | Filter persistence in-page | TableStateManager |
| ALLOC-BR-15 | Active cycle only | Cycle scope |
| ALLOC-BR-16 | No finalization step | Pipeline design |

### Final Review (10)

| ID | Regla | ¿Dónde se aplica? |
|----|-------|-------------------|
| FR-BR-01 | Read-only | PermissionChecker |
| FR-BR-02 | No approval columns | UI design |
| FR-BR-03 | Approved lines only | EligibilityFilter |
| FR-BR-04 | All roles see all lines | Pipeline scope |
| FR-BR-05 | No prototype data | AggregationEngine |
| FR-BR-06 | Stage 3 non-blocking | Stage3Sender |
| FR-BR-07 | Stage 3 re-sendable | Stage3Sender |
| FR-BR-08 | Stage 3: all lines in one action | Stage3Sender |
| FR-BR-09 | Active cycle only | Cycle scope |
| FR-BR-10 | CSV flat export (1 row per JU) | CSVGlobalExporter |

### Management View (8)

| ID | Regla | ¿Dónde se aplica? |
|----|-------|-------------------|
| MGMT-BR-01 | PMO/Admin only | AccessChecker |
| MGMT-BR-02 | Count (PL, Métier) pairs | MetierFilter.count_by_status() |
| MGMT-BR-03 | Full 6-status model | PieChartBuilder |
| MGMT-BR-04 | H-NP/H-PROJECT excluded | MetierFilter |
| MGMT-BR-05 | Single metier filter for both charts | Pipeline |
| MGMT-BR-06 | Active cycle only | Cycle scope |
| MGMT-BR-07 | On page load refresh (no auto-poll) | UI design |
| MGMT-BR-08 | Read-only | AccessChecker |

### Transversal (13)

| ID | Regla | ¿Dónde se aplica? |
|----|-------|-------------------|
| CYCLE-BR-01 | One active cycle | CycleManager.create_cycle() |
| CYCLE-BR-02 | No reactivation | CycleManager.validate_no_reactivation() |
| CYCLE-BR-03 | No deletion | CycleManager |
| CYCLE-BR-04 | Auto-deactivation on create | CycleManager.create_cycle() |
| WL-BR-01 | Admin/RCRC only upload | WorkloadStandardManager.upload_version() |
| WL-BR-02 | .xlsx only | WorkloadStandardManager.validate_file() |
| WL-BR-03 | Preprocessing on upload | validate pipeline |
| WL-BR-04 | Versioned uploads | WorkloadStandardManager |
| WL-BR-05 | JU coefficients immutable after save | DB layer |
| WL-BR-06 | Validation before commit | WorkloadStandardManager |
| TABLE-BR-01 | Filter/sort/resize on all grids | UI requirement |
| TABLE-BR-02 | State persists within session | TableStateManager |
| TABLE-BR-03 | Reset on page navigation | TableStateManager.reset_page() |
| EMAIL-BR-01 | Weekly fixed cadence | EmailAlertService |
| EMAIL-BR-02 | No per-user opt-out | EmailAlertService |
| EMAIL-BR-03 | Email send log | EmailAlertService.get_log() |
| EMAIL-BR-04 | Log retention = active cycle | Email log |

---

## Pendientes por resolver

| ID | Vista | Tópico | Bloquea |
|----|-------|--------|---------|
| ERev-01 | Estimation Review | Send to HVT: manual vs automático | Sí |
| ERev-02 | Estimation Review | Payload HVT fields | Sí |
| ERev-03 | Estimation Review | Email rejection content | No |
| ALLOC-01 | Allocation | K€ job units handling | Sí |
| FINAL-01 | Final Review | Stage 3 payload fields | Sí |
| MGMT-01 | Management View | Timeline data source (event log vs snapshot) | Sí |
| TRANS-01 | Transversal | Email service provider | Sí |
| TRANS-02 | Transversal | Engineer weekly email content | No |
| TRANS-03 | Transversal | RCRC weekly email content | No |

---

## Tests

```bash
# Todos los tests
pytest tests/ -v

# Tests de una vista específica
pytest tests/test_allocation.py -v

# Tests de un módulo específico
pytest tests/test_pipeline.py::TestCompatibilityRules -v

# Tests con cobertura
pip install pytest-cov
pytest tests/ --cov=great_dspy --cov-report=html
```

---

## Stack recomendado

Este repo es **agnóstico del stack**. Los módulos son Python puro. Para implementar:

- **Backend**: FastAPI, Django Ninja, o Flask
- **DB**: PostgreSQL (soporta schemas, enum types para status/roles)
- **ORM**: SQLAlchemy o Prisma (Python)
- **UI**: React/Vue/Next.js — el prototipo UX está en Vercel
- **Email**: Microsoft Graph API (pendiente TRANS-01)

El patrón de integración es siempre el mismo:

```
[UI] → [API Endpoint] → [Pipeline Module] → [DB]
                         ↕
                    [Spec Registry]
                    (reglas de negocio)
```

---

## Repositorio

[https://github.com/nujovich/great-dspy-pipeline](https://github.com/nujovich/great-dspy-pipeline)