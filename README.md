# GREAT SDD Kit

Specification-Driven Development para el sistema GREAT.

Las reglas de negocio del sistema GREAT están codificadas como **especificaciones ejecutables** — no como documentación, no como prompts, no como tickets de Jira. Los agentes de IA (Claude, Codex, Copilot, Cursor) leen estas specs y generan código que las cumple, validado por tests.

> **Última actualización:** 1 junio 2026 — npm como dependencia (no submodule).
> 320 tests, 30 módulos, 6 vistas, 92 reglas de negocio.

## ¿Qué es esto?

Un kit SDD (Spec-Driven Development) que convierte documentos de negocio (PRDs, épicas, historias) en:

1. **Specs estructuradas** — Reglas de negocio con ID, severity, criterios de aceptación
2. **Módulos SDD** — Lógica pura importable como librería
3. **Pipelines** — Orquestación de módulos como blueprint de endpoints
4. **Tests ejecutables** — 320 tests que verifican las 92 reglas

```plaintext
Documento (PRD/Épica/Story)
        │
        ▼
great_sdd/specs/     ← 92 reglas estructuradas (6 archivos)
        │
        ▼
great_sdd/modules/   ← 30 módulos SDD (lógica pura)
        │
        ▼
great_sdd/pipeline/  ← 6 pipelines (blueprint de endpoints)
        │
        ▼
tests/                ← 320 tests (pytest)
        │
        ▼
pytest tests/ -v      ← ¿Cumple las 92 reglas? Sí → Merge.
```

## 6 Formas de Usar el SDD Kit

| # | Uso | Cuándo | Stack |
|---|-----|--------|-------|
| **1** | **Como librería** | Necesitás lógica de negocio importable en tu código | Python puro. `from great_sdd.modules.pre_estimation import StatusTransitionValidator` |
| **2** | **Como pipeline** | Necesitás orquestar validaciones en orden (blueprint de endpoints) | SDD modules. `run_pipeline(selected_lines, role, metier)` |
| **3** | **Como agente de IA** | Querés que Claude/Copilot/Cursor cumpla reglas sin adivinar | AGENTS.md + CLAUDE.md + .cursorrules → specs |
| **4** | **Como documentación** | Querés docs versionadas y testeables (no PDFs que se pudren) | YAML + Markdown + tests como documentación ejecutable |
| **5** | **Como auditoría** | Necesitás verificar compliance en CI/CD o revisar un PR | pytest + 320 tests. Resultado en segundos |
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
│   ├── specs/                       ← 6 archivos, 92 reglas de negocio
│   │   ├── pre_estimation_specs.py      ← 17 reglas (vista Pre-Estimation)
│   │   ├── estimation_review_specs.py   ← 10 reglas (vista Estimation Review)
│   │   ├── allocation_specs.py          ← 16 reglas (vista Allocation)
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
└── tests/                           ← 320 tests que verifican las 92 reglas
    ├── sample_data.py                  ← Datos de prueba
    ├── test_pipeline.py                ← Tests de pipeline core
    ├── test_pipeline.py                ← Tests de Pre-Estimation (unit+módulo+pipeline)
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
| **TOTAL** | | **92** | **~7** | **6** | **257** |

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

## Reglas de Negocio (92 total)

> Número derivado programáticamente por `great_sdd/conformance/rule_inventory.py` (IDs que matchean `…BR-NN`). Hay además 9 marcadores pendientes sin ID de regla (`ALLOC-01`, `ERev-01..03`, `FINAL-01`, `MGMT-01`, `TRANS-01..03`).

### Pre-Estimation (BR-01 a BR-20, 20 reglas)

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

### Allocation (17 reglas)

Reglas de tasas K€, societes, split allocation, TSA/TC, y auto-reglas.

### Final Review (10 reglas)

Reglas de Stage 3 HVT, agregación, y cierre de estimación.

### Management View (8 reglas)

Reglas de dashboard: pie chart, timeline, filtros, y export.

### Transversal (27 reglas)

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
python -m pytest tests/ -v              # Todos (320 tests)
python -m pytest tests/test_pipeline.py -v  # Solo Pre-Estimation (103 tests)
python -m pytest tests/test_pipeline.py -v        # Pipeline core
```

Cada test verifica una o más reglas de negocio. Si tu código pasa los 320 tests, cumple las 92 reglas.

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

El SDD actúa como **oracle determinista**: ejecuta casos representativos contra las funciones puras y emite **golden fixtures** JSON neutros (en `great_sdd/conformance/fixtures/`) que un consumidor (backend Python o frontend TS) usa para verificar que su código cumple las reglas — hermético y en CI. Todo es determinista (sin LLM ni red): la generación se hace con un *Tripwire LM* que aborta ruidosamente si una regla cubierta depende del LM.

```bash
python -m great_sdd.conformance.generate          # (re)generar fixtures
python -m great_sdd.conformance.generate --check    # CI: falla si hay drift
python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70
```

Cobertura actual: 55/55 reglas de negocio con superficie determinista (100% de lo cubrible); 37 reglas de política/UI/persistencia y 3 capacidades LM-only quedan documentadas como exclusiones. Ver `great_sdd/conformance/README.md` para el contrato cross-language.

## Stack

| Componente | Tecnología |
|-----------|-----------|
| **Framework SDD** | SDD Kit propio — specs ejecutables + modules + tests |
| **Lenguaje** | Python 3.11+ (backend), TypeScript (frontend del proyecto consumidor) |
| **Tests** | pytest (320 tests) |
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
