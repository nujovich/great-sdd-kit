# SDD Kit — Universal Agent Instructions

Eres un agente de IA generando código para un proyecto que usa **Specification-Driven Development (SDD)**.

## Cómo integrarlo en tu proyecto

Este repositorio NO es el proyecto raíz del desarrollador. Es una **dependencia npm** que se instala con:

```bash
npm install git+https://github.com/nujovich/great-sdd-kit.git
```

El código queda en `node_modules/great-sdd-kit/`. Luego en tu `CLAUDE.md` / `.cursorrules` del proyecto principal:

```
Lee node_modules/great-sdd-kit/AGENTS.md antes de generar cualquier código.
```

Ver `INTEGRATION.md` para más detalles.

---

## Qué es este repositorio

Este repositorio es un **SDD Kit**: las reglas de negocio están codificadas como especificaciones ejecutables (no prompts, no documentación, no tickets de Jira). Cada regla tiene un ID, está en un archivo de `specs/`, implementada en un módulo de `modules/`, y verificada por tests en `tests/`.

## Estructura

```
├── AGENTS.md              ← Este archivo. CÁRGALO SIEMPRE.
├── CLAUDE.md              ← Entry point para Claude Code
├── .cursorrules           ← Entry point para Cursor IDE
├── .github/copilot-instructions.md  ← Entry point para GitHub Copilot
│
├── sdd/                   ← SDD Core Framework (reutilizable)
│   ├── base_spec.py       ← Base class para definir specs
│   ├── base_module.py     ← Base class para módulos
│   └── base_pipeline.py   ← Base class para pipelines
│
├── great_sdd/            ← Dominio: Sistema GREAT
│   ├── specs/             ← 6 archivos, 92 reglas de negocio
│   ├── modules/           ← 30 módulos con lógica pura
│   ├── pipeline/          ← 6 pipelines (uno por vista)
│   └── signatures/        ← Contratos input/output
│
└── tests/                 ← 320 tests que verifican las 92 reglas
```

## Cómo usar este kit

### 1. Siempre carga AGENTS.md primero

Antes de generar CUALQUIER código, lee este archivo completo. Contiene las reglas de negocio que tu código debe cumplir.

### 2. Las reglas están en `great_sdd/specs/`

No adivines reglas de negocio. No las inventes. No las saques de tu training data. Están aquí:

| Archivo | Contenido |
|---------|-----------|
| `great_sdd/specs/pre_estimation_specs.py` | 17 reglas, state machine, 6 métiers, fórmulas |
| `great_sdd/specs/estimation_review_specs.py` | 10 reglas, flujo HVT, columnas de aprobación |
| `great_sdd/specs/allocation_specs.py` | 16 reglas, tasas K€, societes, split allocation |
| `great_sdd/specs/final_review_specs.py` | 10 reglas, Stage 3 HVT, agregación |
| `great_sdd/specs/management_view_specs.py` | 8 reglas, dashboard con charts |
| `great_sdd/specs/transversal_specs.py` | 13 reglas, ciclos, versiones, emails |

### 3. La lógica está en `great_sdd/modules/`

Cada módulo es Python puro. Úsalos como librería desde cualquier backend:

```python
import sys
sys.path.insert(0, "node_modules/great-sdd-kit")

from great_sdd.specs.allocation_specs import calculate_fte_ke
ke = calculate_fte_ke(fte=1.0, societe_site="Horse Spain S.L.-Valladolid", year="2024")
# → 107.0

from great_sdd.modules.pre_estimation import StatusTransitionValidator
v = StatusTransitionValidator()
assert v.forward("approved", "draft")["is_valid"] is False  # Approved es terminal
```

Los módulos que usan IA (InductorSelector, SummaryGenerator) tienen un LM client intercambiable.

### 4. Los pipelines son el blueprint de endpoints

Cada pipeline orquesta módulos en el orden correcto. Cada etapa del pipeline es un paso en tu endpoint:

```
Pre-Estimation endpoint:
  POST /api/pre-estimation/save-draft
  Pipeline: SelectionValidator → PermissionChecker → InductorSelector
            → EstimationCalculator → SaveValidator → MonthDistributor → SummaryGenerator
  Reglas: BR-02 (Draft gate), BR-08 (SP date), BR-11 (Custom JUs)
  Tests: test_todo_to_draft_valid_transition, test_missing_sp_date_blocks_save
```

### 5. Los tests verifican las reglas

320 tests. Si tu código los pasa, cumple las 92 reglas de negocio.

```bash
pytest tests/ -v              # Todos los tests
pytest tests/test_allocation.py -v  # Solo Allocation
```

### 6. Cuando una regla cambie

Si el negocio cambia una regla, el flujo es:

1. Editas el spec en `great_sdd/specs/`
2. Corres `pytest tests/ -v` para ver qué se rompe
3. Arreglas los módulos y tests afectados
4. Vuelves a correr pytest hasta que todo pase
5. Commit

No implementes un cambio de regla sin pasar por este flujo. Si el test no existe, la regla no está cubierta.

## Reglas que NUNCA debes violar

Estas son las reglas más críticas. Si tu código las viola, los tests fallarán:

1. **No deletion** (BR-01): Las estimaciones nunca se borran
2. **Draft gate** (BR-02): No existe "Save as Definitive" sin "Save as Draft" antes
3. **Estimated = locked** (BR-03): status=Estimated es read-only hasta que CPO actúe
4. **Approved = terminal** (BR-04): Approved no cambia por ninguna acción en GREAT
5. **Multi-select compatibility** (BR-06): 4 campos deben coincidir para selección múltiple
6. **null vs null = compatible; null vs value = no** (BR-07)
7. **SP date mandatory** (BR-08): No se guarda sin fecha SP
8. **Sent = irreversible** (ERev-BR-02): Una vez enviado a HVT, no se cancela
9. **Solo Estimated se envía** (ERev-BR-04): Los demás status se ignoran
10. **Approved lines only** (ALLOC-BR-01): Solo Approved aparecen en Allocation
11. **Auto-rules NO sobrescriben** (ALLOC-BR-02): Rules saltan rows ya asignadas
12. **TSA/TC sin societe: bloquea save** (ALLOC-BR-06)
13. **Split: 100% obligatorio** (ALLOC-BR-11)
14. **Stage 3 no bloquea** (FR-BR-06): Se envía con warning
15. **One active cycle** (CYCLE-BR-01): Solo un ciclo activo
16. **No reactivation** (CYCLE-BR-02): Ciclos inactivos no se reactivan

## Para extender este kit a otro dominio

Si quieres aplicar SDD a otro sistema (no GREAT):

1. Copia `sdd/` a tu proyecto
2. Crea `domains/tu_dominio/specs/` con tus reglas
3. Crea `domains/tu_dominio/modules/` con tu lógica
4. Crea `domains/tu_dominio/pipeline/` con tu orquestación
5. Crea `tests/` que verifiquen tus reglas
6. Copia AGENTS.md, CLAUDE.md, .cursorrules, copilot-instructions.md

## Versionado

Este proyecto usa Semantic Versioning. Ver `VERSIONING.md` para la guía completa.

**Resumen rápido:**
- **PATCH** (0.0.1): Fix de bug, corrige comportamiento, no rompe API
- **MINOR** (0.X.0): Nueva funcionalidad, nuevo módulo, nueva regla — no rompe API
- **MAJOR** (X.0.0): Cambio en la API pública de módulos (firma, retorno, nombres)

Para hacer un bump: `python3 scripts/bump_version.py <major|minor|patch>`

Nunca hagas un bump sin actualizar `CHANGELOG.md`.

## Stack

Los módulos son Python puro sin dependencias externas. El stack técnico (backend, DB, UI) lo defines tú como desarrollador.
