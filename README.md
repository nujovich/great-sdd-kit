# GREAT DSPy Pipeline — SDD Kit

**Specification-Driven Development** para el sistema GREAT, construido sobre [DSPy](https://github.com/stanfordnlp/dspy) (Stanford NLP).

Las reglas de negocio del sistema GREAT están codificadas como **especificaciones ejecutables** — no como documentación, no como prompts, no como tickets de Jira. Los agentes de IA (Claude, Codex, Copilot, Cursor) leen estas specs y generan código que las cumple, validado por tests.

> **Última actualización:** 29 mayo 2026 — 257 tests, 7 módulos, 6 vistas.
> En progreso: auditoría de schema DB v2 (19 tablas PostgreSQL) vs contrato API (OpenAPI + TypeScript).
> Ver abajo sección "Auditoría DB v2".

## ¿Qué es esto?

Un kit SDD (Spec-Driven Development) que convierte documentos de negocio (PRDs, épicas, historias) en:

1. **Specs estructuradas** — Reglas de negocio con ID, severity, criterios de aceptación
2. **Módulos DSPy** — Lógica pura importable como librería
3. **Pipelines** — Orquestación de módulos como blueprint de endpoints
4. **Tests ejecutables** — 216 tests que verifican las 78 reglas

```plaintext
Documento (PRD/Épica/Story)
        │
        ▼
great_dspy/specs/     ← 78 reglas estructuradas (6 archivos)
        │
        ▼
great_dspy/modules/   ← 30 módulos DSPy (lógica pura)
        │
        ▼
great_dspy/pipeline/  ← 6 pipelines (blueprint de endpoints)
        │
        ▼
tests/                ← 216 tests (pytest)
        │
        ▼
pytest tests/ -v      ← ¿Cumple las 78 reglas? Sí → Merge.
```

## 6 Formas de Usar el SDD Kit

| # | Uso | Cuándo | Stack |
|---|-----|--------|-------|
| **1** | **Como librería** | Necesitás lógica de negocio importable en tu código | Python puro. `from great_dspy.modules.pre_estimation import StatusTransitionValidator` |
| **2** | **Como pipeline** | Necesitás orquestar validaciones en orden (blueprint de endpoints) | DSPy modules. `run_pipeline(selected_lines, role, metier)` |
| **3** | **Como agente de IA** | Querés que Claude/Copilot/Cursor cumpla reglas sin adivinar | AGENTS.md + CLAUDE.md + .cursorrules → specs |
| **4** | **Como documentación** | Querés docs versionadas y testeables (no PDFs que se pudren) | YAML + Markdown + tests como documentación ejecutable |
| **5** | **Como auditoría** | Necesitás verificar compliance en CI/CD o revisar un PR | pytest + 216 tests. Resultado en segundos |
| **6** | **Como framework extensible** | Querés aplicar SDD a otro dominio (no GREAT) | Copiás `sdd/` (base_spec, base_module, base_pipeline) y creás tus reglas |

Cada uso es independiente: podés usar solo la librería sin tocar los pipelines, o solo los tests sin el agente.

## Arquitectura

```plaintext
great-dspy-pipeline/
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
├── great_dspy/                      ← Dominio: Sistema GREAT
│   ├── __init__.py
│   ├── demo.py                      ← Demo runner
│   ├── specs/                       ← 6 archivos, 78 reglas de negocio
│   │   ├── pre_estimation_specs.py      ← 17 reglas (vista Pre-Estimation)
│   │   ├── estimation_review_specs.py   ← 10 reglas (vista Estimation Review)
│   │   ├── allocation_specs.py          ← 16 reglas (vista Allocation)
│   │   ├── final_review_specs.py        ← 10 reglas (vista Final Review)
│   │   ├── management_view_specs.py     ← 8 reglas (vista Management)
│   │   └── transversal_specs.py         ← 13 reglas (ciclos, versiones, emails)
│   │
│   ├── signatures/                  ← DSPy Signatures (contratos input/output)
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
└── tests/                           ← 216 tests que verifican las 78 reglas
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

|| Vista | Archivo de Specs | Reglas | Módulos | Pipeline | Tests |
||-------|-----------------|--------|---------|----------|-------|
|| **Pre-Estimation** | `pre_estimation_specs.py` | 17 | 7 | 7 etapas | 68 |
|| **Estimation Review** | `estimation_review_specs.py` | 10 | — | — | — |
|| **Allocation** | `allocation_specs.py` | 16 | — | — | — |
|| **Final Review** | `final_review_specs.py` | 10 | — | — | — |
|| **Management View** | `management_view_specs.py` | 8 | — | — | — |
|| **Transversal** | `transversal_specs.py` | 13 | — | — | — |
|| **Signature** `signature_module.py` | — | — | 1 | — | — |
|| **Bulk Deletion** `bulk_inductor_deleter.py` | — | 10 | 1 | — | — |
|| **TOTAL** | | **~84** | **~7** | **6** | **257** |

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
from great_dspy.modules.pre_estimation import StatusTransitionValidator

v = StatusTransitionValidator()
result = v.forward("approved", "draft")
assert result["is_valid"] is False  # Approved es terminal

from great_dspy.specs.allocation_specs import calculate_fte_ke
ke = calculate_fte_ke(fte=1.0, societe_site="Horse Spain S.L.-Valladolid", year="2024")
assert ke == 107.0
```

### Como pipeline

```python
from great_dspy.pipeline.pre_estimation_pipeline import run_pipeline

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
python -m pytest tests/ -v              # Todos (216 tests)
python -m pytest tests/test_pre_estimation.py -v  # Solo Pre-Estimation (68 tests)
python -m pytest tests/test_pipeline.py -v        # Pipeline core
```

Cada test verifica una o más reglas de negocio. Si tu código pasa los 216 tests, cumple las 78 reglas.

## Integración en tu proyecto

```bash
# 1. Agregar como git submodule
cd tu-proyecto
git submodule add https://github.com/nujovich/great-dspy-pipeline.git sdd-kit

# 2. Configurar agentes de IA (3 archivos, 1 línea cada uno)
echo "Carga sdd-kit/AGENTS.md antes de generar cualquier código" >> CLAUDE.md
echo "Carga sdd-kit/AGENTS.md" >> .cursorrules
echo "Load sdd-kit/AGENTS.md" >> .github/copilot-instructions.md

# 3. Correr tests
cd sdd-kit && python -m pytest tests/ -v
```

Ver `INTEGRATION.md` para la guía detallada con troubleshooting.

## Cómo actualizar el SDD Kit en tu proyecto

Cuando el SDD Kit se actualiza en el repo principal (nuevas reglas, fixes, nuevos módulos), así lo actualizás en tu proyecto:

```bash
# Opción 1: Pull del último commit en la rama main
cd tu-proyecto/sdd-kit
git checkout main
git pull origin main
cd ..
git add sdd-kit
git commit -m "chore: update SDD Kit submodule"

# Opción 2: Comando único desde la raíz del proyecto
git submodule update --remote sdd-kit
git add sdd-kit
git commit -m "chore: update SDD Kit submodule"

# Opción 3: Actualizar todos los submodules a la vez
git submodule update --remote
git add .
git commit -m "chore: update all submodules"
```

**Importante:** Después de actualizar, corré los tests para verificar que tu código sigue cumpliendo las reglas:

```bash
cd sdd-kit && python -m pytest tests/ -q
# Si algún test falla, es porque una regla cambió o se añadió una nueva.
# Editá los módulos afectados hasta que todo pase.
```

**Qué hacer si un test falla después de actualizar:**

1. Leyendo el nombre del test que falla, identificá qué regla cambió
2. Revisá el spec correspondiente en `great_dspy/specs/` para ver el cambio
3. Actualizá tu código o los tests del proyecto (no los del kit) para cumplir la nueva regla
4. Corré `pytest tests/ -v` hasta que todo pase
5. Commit

**Versionado:** El SDD Kit usa tags semánticos (`v1.0.0`, `v1.1.0`, etc.). Para mantener estabilidad, podés pinchar a una versión específica:

```bash
git submodule add -b v1.0.0 https://github.com/nujovich/great-dspy-pipeline.git sdd-kit
# O si ya lo tenés agregado:
cd sdd-kit && git checkout v1.0.0
```

El SDD Kit de GREAT es complementario con [GitHub Spec Kit](https://github.com/github/spec-kit):

| Dimensión | GitHub Spec Kit | SDD Kit de GREAT |
|-----------|----------------|-----------------|
| **Enfoque** | Desarrollo (agente) | Pipeline declarativo (DSPy) |
| **Motor** | Agentes IA | DSPy + pytest |
| **Input** | Requirements (lenguaje natural) | PRDs, épicas, reglas de negocio |
| **Output** | Código funcional | Specs estructuradas + 216 tests |
| **Validación** | ¿El código hace lo que dice la spec? | ¿Cumple las 78 reglas de negocio? |

**Flujo combinado recomendado:**

```plaintext
GitHub Spec Kit              SDD Kit de GREAT
─────────────────            ─────────────────
specify init              →  git submodule add great-dspy-pipeline
specify plan              →  Cargar reglas aplicables
specify tasks             →  Tests de compliance adjuntos
specify implement         →  Agente escribe código
                         →  pytest tests/ valida reglas
specify validate          →  Merge si pasa todo
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

## Stack

| Componente | Tecnología |
|-----------|-----------|
| **Framework SDD** | DSPy (Stanford NLP) — Declarative Self-improving Python |
| **Lenguaje** | Python 3.11+ (backend), TypeScript (frontend del proyecto consumidor) |
| **Tests** | pytest (216 tests) |
| **Agentes IA** | Claude Code, GitHub Copilot, Cursor, Codex |
| **Integración** | CLAUDE.md, .cursorrules, AGENTS.md, copilot-instructions |
| **Distribución** | Git submodule |
| **Licencia** | MIT |

## Repositorio

[https://github.com/nujovich/great-dspy-pipeline](https://github.com/nujovich/great-dspy-pipeline)

## Referencias

- [DSPy](https://github.com/stanfordnlp/dspy) — Stanford NLP framework
- [GitHub Spec Kit](https://github.com/github/spec-kit) — SDD con agentes (106k ⭐)
- Piskala, D.B. (2026) — *Spec-Driven Development: From Code to Contract* (AIWare 2026)
- Taghavi, P. & Bhavani, S. (2026) — *Spec Kit Agents: Context-Grounded Agentic Workflows*
- Marri, S.R. (2026) — *Constitutional Spec-Driven Development* (security-by-construction)

---

## Auditoría DB v2 — Schema SQL vs Contrato API

**Estado:** En progreso (pendiente revisión con responsable del schema)

**Source of truth declarada:** `schema.sql` + `schema.md` (19 tablas PostgreSQL, Greenfield v2).

**Archivos bajo auditoría:**
- `pev-openapi.yaml` — Contrato OpenAPI 3.1.0 ("PEV API", Pre-Estimation Validation)
- `pev.ts` — Tipos TypeScript auto-generados por openapi-typescript

### Discrepancias detectadas (borrador)

**1. Campos en DB sin cobertura API**
- `project_line`: 15+ columnas sin exponer (HVT attributes, milestone dates, assignee). Solo `id`, `name`, `metier`, `status`, `updated_at` en el listado.
- `job_unit`: sin `unit_type` (Man Day / Bench Hours / Kilometres / Kiloeuros), sin coeficientes (`variable`, `fixed`), sin perfiles FMM/SMM/DMM.
- `job_unit_allocation`: sin endpoints CRUD completos (solo existe prototype y estimation).
- Tablas sin endpoint alguno: `keuro_rate`, `allocation_rule_version`, `allocation_rule`, `metier_distribution_config`, `hvt_audit_log`, `email_send_log`, `status_change_log`.

**2. `project_id` vs `pl_number`**
- API usa `project_id`, DB usa `pl_number`. Nadie sabe si son lo mismo.

**3. Prototipo: estructura incompatible**
- DB: columnas fijas `proto_1`, `proto_2`, `proto_3`
- API: array genérico `categories: [{id, quantity}]`
- Pregunta abierta: ¿la API viene de versión anterior?

**4. `H-TESTING` inconsistente**
- `allocation_rule_version.metier` incluye `H-TESTING`, pero ningún otro CHECK ni el enum `Metier` del OpenAPI lo incluyen.

**5. `energy` vs `fuel_type`**
- `project_line.energy` y `ws_n2_entry.fuel_type` — posible mismatch de naming para el mismo concepto.

**6. `cpo_comment` ubicación**
- API lo muestra en `EstimationPayload`. En la DB vive en `status_change_log.comment` (fila Sent→Rejected).

### Pendiente con responsable del schema

1. ¿Schema SQL congelado o pueden cambiar NOT NULL constraints (HVT-02)?
2. ¿`H-TESTING` es metier real o futuro?
3. ¿`project_id` API = `pl_number` DB?
4. ¿Prototipo API se actualizará al modelo de columnas fijas?
5. ¿El OpenAPI es solo fase 1 (Pre-Estimation)?
6. ¿Dónde está el generador de `pev.ts`?
7. ¿`energy` = `fuel_type`?
8. ¿Para cuándo se necesita el análisis finalizado? (¿compliance en CI? ¿migraciones? ¿documentación?)

### Plan de implementación SDD Kit

Una vez resueltas las preguntas:
1. `great_dspy/specs/db_schema_specs.py` — reglas por tabla (types, constraints, relaciones)
2. `great_dspy/specs/api_contract_specs.py` — reglas de coherencia API↔DB
3. `great_dspy/modules/db_api_consistency.py` — validador cross YAML↔SQL
4. Tests que verifiquen coherencia bidireccional API vs DB
