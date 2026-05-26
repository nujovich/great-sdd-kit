# GREAT System — IA Agent Instructions

Eres un agente de IA ayudando a desarrollar el sistema GREAT. Este repositorio contiene **las reglas de negocio como especificaciones ejecutables** — no documentación, no prompts, sino código verificable que define cómo debe comportarse el sistema.

## Cómo usar este repositorio

### 1. Lee las reglas desde `great_dspy/specs/`

Cada archivo en `specs/` contiene reglas de negocio como estructuras de datos:

- `pre_estimation_specs.py` → 17 reglas, state machine, 6 métiers, fórmulas de estimación
- `estimation_review_specs.py` → 10 reglas, flujo HVT, columnas de aprobación, CSV export
- `allocation_specs.py` → 16 reglas, tasas K€, societes, split allocation, routing H-PROJECT
- `final_review_specs.py` → 10 reglas, Stage 3, niveles de agregación
- `management_view_specs.py` → 8 reglas, dashboard con charts
- `transversal_specs.py` → 13 reglas, ciclos, versiones de workload, tablas, emails

No adivines reglas de negocio. Léelas de estos archivos.

### 2. Entiende la lógica desde `great_dspy/modules/`

Cada módulo implementa una operación atómica del negocio. La mayoría son Python puro sin IA:

- `SelectionValidator` → validación de compatibilidad multi-línea (4 campos)
- `PermissionChecker` → permisos por rol (Admin/Engineer/PMO/RCRC/CPO)
- `StatusTransitionValidator` → máquina de estados (ToDo→Draft→Estimated→Sent→Approved)
- `EstimationCalculator` → fórmula Total = (Variable × Occurrence) + Fixed
- `SaveValidator` → precondiciones para guardar (SP date, Draft gate, inductores)
- `SendEligibilityChecker` → solo status=Estimated es elegible para enviar a HVT
- `KECalculator` → K€ = FTE × Rate(societe, year)
- `CSVExporter` → exportación plana con columnas por año

Los módulos con IA (InductorSelector, SummaryGenerator) usan un LM client OpenAI-compatible — puedes reemplazarlo por el modelo que prefieras.

### 3. Valida contra `tests/`

Hay 216 tests. Si tu código los pasa, cumple las 74 reglas de negocio.

Siempre corre los tests después de generar código:

```bash
pytest tests/ -v
```

Si algún test falla, NO es un bug del test — es que tu código viola una regla de negocio.

### 4. Sigue los pipelines en `great_dspy/pipeline/`

Cada vista tiene un pipeline que orquesta los módulos en orden. Son tu blueprint para implementar los endpoints:

```
Pre-Estimation:    SelectionValidator → PermissionChecker → InductorSelector → EstimationCalculator → SaveValidator → MonthDistributor → SummaryGenerator
Estimation Review: PermissionChecker → ApprovalColumnDeriver → SendEligibilityChecker → HVTPayloadGenerator → CSVExporter
Allocation:        PermissionChecker → EligibilityFilter → RuleMatcher → HProjectRouter → DiversityHandler → KECalculator → SaveValidator
Final Review:      PermissionChecker → EligibilityFilter → AggregationEngine → CSVExporter → Stage3Sender
Management View:   AccessChecker → MetierFilter → PieChartBuilder → TimelineBuilder
```

## Reglas que NUNCA debes violar

Estas reglas están codificadas en los specs y verificadas por tests. Si tu código las viola, los tests fallarán:

1. **No deletion** (BR-01): Las estimaciones nunca se borran
2. **Draft gate** (BR-02): No existe "Save as Definitive" sin "Save as Draft" antes
3. **Estimated = locked** (BR-03): status=Estimated es read-only hasta que CPO actúe
4. **Approved = terminal** (BR-04): Approved no puede cambiar por ninguna acción en GREAT
5. **Multi-select compatibility** (BR-06): 4 campos deben coincidir (Organ Type, Energy, Ranking, Injection)
6. **null vs null = compatible; null vs value = no** (BR-07)
7. **SP date mandatory** (BR-08): No se puede guardar sin fecha SP
8. **Assignment read-only** (BR-10): Las asignaciones engineer→línea vienen de HVT
9. **Sent = irreversible** (ERev-BR-02): Una vez enviado a HVT, no se puede cancelar
10. **Solo Estimated se envía** (ERev-BR-04): Los demás status se ignoran silenciosamente
11. **Approved lines only** (ALLOC-BR-01): Solo Approved aparecen en Allocation
12. **Auto-rules NO sobrescriben** (ALLOC-BR-02): Las reglas saltan rows ya asignadas
13. **TSA/TC sin societe: bloquea save** (ALLOC-BR-06)
14. **Split: 100% obligatorio** (ALLOC-BR-11)
15. **Stage 3 no bloquea** (FR-BR-06): Se envía con warning, no bloqueado
16. **One active cycle** (CYCLE-BR-01): Solo un ciclo activo a la vez
17. **No reactivation** (CYCLE-BR-02): Ciclos inactivos no se reactivan

## Formato de respuesta esperado

Cuando generes código para una vista, incluye:

1. **Endpoint**: qué método HTTP y ruta
2. **Validación**: qué módulo del pipeline usar para validar antes de escribir en DB
3. **Reglas aplicadas**: qué BR/ERev-BR/ALLOC-BR/FR-BR aplican a este endpoint
4. **Tests**: qué test verifica esta funcionalidad

Ejemplo:

```python
# POST /api/pre-estimation/save-draft
# Pipeline: SaveValidator.forward(line, "draft")
# Reglas: BR-02 (Draft gate), BR-08 (SP date), BR-11 (Custom JUs)
# Tests: test_todo_to_draft_valid_transition, test_missing_sp_date_blocks_save
```

## Stack

El stack técnico debes inferirlo del contexto del proyecto. Este repositorio es agnóstico del stack — los módulos son Python puro sin dependencias externas.

## Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `great_dspy/specs/` | Reglas de negocio como datos (la fuente de verdad) |
| `great_dspy/modules/` | Lógica atómica del negocio (importable desde cualquier backend) |
| `great_dspy/pipeline/` | Orquestación por vista (blueprint para endpoints) |
| `great_dspy/signatures/` | Contratos input/output (para cuando uses DSPy real) |
| `tests/` | 216 tests que verifican las 74 reglas |