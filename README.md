# GREAT DSPy Pipeline — SDD for Pre-Estimation View

Specification-Driven Development pipeline para la vista Pre-Estimation del sistema GREAT, implementado con un enfoque DSPy.

## ¿Qué es esto?

Un pipeline modular que codifica **todas las reglas de negocio** de la vista Pre-Estimation como datos, no como prompts. Cada módulo corresponde a una sección de la especificación SDD.

## Arquitectura

```
great_dspy/
├── specs/                      # Spec Registry — las reglas como datos
│   └── pre_estimation_specs.py # 17 business rules, state machine, roles, fórmulas
├── signatures/                 # DSPy Signatures — contratos input/output
│   └── pre_estimation.py       # 8 signatures con descripciones formales
├── modules/                    # Módulos de pipeline
│   ├── base.py                 # LM client abstracto (OpenAI-compatible)
│   └── pre_estimation.py       # 8 módulos (SelectionValidator, PermissionChecker, etc.)
├── pipeline/                   # Orquestación
│   └── pre_estimation_pipeline.py  # Pipeline completo de 7 etapas
└── demo.py                     # Demo runner
tests/
├── test_pipeline.py            # 68 tests
└── sample_data.py              # Datos de prueba
```

## Pipeline (7 etapas)

| Stage | Módulo | Reglas | LM? |
|-------|--------|--------|-----|
| 1. Selection Validation | `SelectionValidator` | §5 Compatibility, null handling | Solo explicación |
| 2. Permission Check | `PermissionChecker` | §2 Roles, BR-10 assignments | No |
| 3-4. Inductors | `InductorSelector` | §6-8 Workload standard, crans | Sí |
| 5. Calculation | `EstimationCalculator` | §9 Fórmulas, FTE/BH/KM | No |
| 6. Save Validation | `SaveValidator` | §10 Draft gate, BR-08 SP date | No |
| 7. Distribution | `MonthDistributor` | §9.4-9.5 Monthly/yearly | No |
| 8. Summary | `SummaryGenerator` | §10.3 Pre-save panel | Sí |

## Reglas de Negocio (17)

Codificadas en `specs/pre_estimation_specs.py::BUSINESS_RULES`:

- BR-01: No deletion
- BR-02: Draft gate
- BR-03: Estimated = locked
- BR-04: Approved = terminal
- BR-05: Engineer approval inferred
- BR-06: Multi-select compatibility
- BR-07: Null injection system
- BR-08: SP date mandatory
- BR-09: Occurrence lock default
- BR-10: Assignment read-only
- BR-11: Custom JUs unblocked
- BR-12: Inductor without cran
- BR-13: Zero occurrence
- BR-14: Comments scoped to (line, métier)
- BR-15: Draft is first step
- BR-16: Sent = locked
- BR-17: Re-save overwrites

## Uso

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

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## DSPy

Este pipeline está diseñado para ser portado a Stanford [DSPy](https://github.com/stanfordnlp/dspy) cuando esté disponible:
- Las `Signatures` ya están definidas como dataclasses en `signatures/`
- Los `Modules` ya siguen el patrón `__init__` + `forward()`
- El `Pipeline` es un `dspy.Module` compatible

```bash
pip install dspy-ai  # Cuando el entorno lo permita
```

## Licencia

MIT