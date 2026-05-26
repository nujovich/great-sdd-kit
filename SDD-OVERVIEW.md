# GREAT System — Specification-Driven Development (SDD) con DSPy

## ¿Qué es esto?

No es una app. No es un backend. Es **el ADN del sistema GREAT expresado como código verificable**.

Cada regla de negocio, cada transición de estado, cada permiso de rol — todo lo que hace único a GREAT — está codificado como **datos**, no como prompts de IA ni documentos Word ni conversaciones de Slack.

---

## El problema que resuelve

El desarrollo tradicional de software con IA tiene un problema de fondo:

```
PRD en Google Docs → Devs interpretan → Código → Bugs por interpretación
     (ambiguo)           (sesgo)            (implementación)   (discrepancias)
```

Cada vez que un PRD pasa por una persona, se pierde información. Y cuando metes IA generativa, el problema se multiplica: el modelo alucina, inventa transiciones de estado que no existen, o permite acciones que las reglas de negocio prohíben.

**La solución:** que las reglas NO estén en prompts ni en documentos, sino en un **Spec Registry** — código puro que los módulos leen y los tests verifican.

```
Spec como datos → Módulos la leen → Pipeline orquesta → Tests verifican
     (preciso)      (sin interpretación)    (composable)     (sin ambigüedad)
```

---

## La arquitectura

```
great_dspy/
├── specs/                    ← El cerebro. Las reglas como datos.
│   ├── pre_estimation_specs.py     (17 reglas, state machine, 6 métiers)
│   └── estimation_review_specs.py  (10 reglas, HVT flow, CSV export)
│
├── signatures/               ← Contratos input/output (al estilo DSPy)
│   ├── pre_estimation.py          (8 signatures)
│   └── estimation_review.py       (6 signatures)
│
├── modules/                  ← Cada operación del negocio es un módulo
│   ├── base.py                    (LM client — OpenAI-compatible)
│   ├── pre_estimation.py         (8 módulos)
│   └── estimation_review.py      (6 módulos)
│
├── pipeline/                 ← Orquestación por vista del sistema
│   ├── pre_estimation_pipeline.py     (7 etapas)
│   └── estimation_review_pipeline.py  (5 etapas)
│
└── tests/                    ← Tests que verifican las reglas, no el código
    ├── test_pipeline.py            (68 tests)
    └── test_estimation_review.py   (62 tests)
```

---

## Los 4 pilares

### 1. Spec Registry — Las reglas como datos

Cada regla de negocio vive en un diccionario. No en un prompt. No en un ticket de Jira.

```python
BUSINESS_RULES = [
    {"id": "BR-02", "rule": "Draft gate — 'Save as Definitive' requiere 'Save as Draft' primero"},
    {"id": "BR-08", "rule": "SP date mandatory — no se puede guardar sin fecha SP"},
]
```

La máquina de estados es un diccionario:

```python
STATUS_TRANSITIONS = {
    LineStatus.TODO:      [LineStatus.DRAFT],
    LineStatus.DRAFT:     [LineStatus.DRAFT, LineStatus.ESTIMATED],
    LineStatus.ESTIMATED: [LineStatus.SENT, LineStatus.REJECTED],
    LineStatus.SENT:      [LineStatus.APPROVED, LineStatus.REJECTED],
    LineStatus.APPROVED:  [],  # Terminal — no hay salida
}
```

Los permisos son datos:

```python
ROLE_PERMISSIONS = {
    Role.ENGINEER: RolePermission(can_view=True, can_edit=True, scope="assigned_only"),
    Role.PMO:      RolePermission(can_view=True, can_edit=False, scope="all"),
    Role.CPO:      RolePermission(can_view=False, can_edit=False, scope="none"),
}
```

**¿Qué ganas?** Cuando una regla cambia (ej: "ahora CPO también ve Pre-Estimation"), cambias **una línea** en el spec y 130 tests te dicen si algo se rompe.

### 2. Módulos — Operaciones atómicas

Cada módulo hace una sola cosa y la hace bien:

| Módulo | Qué hace | ¿Usa IA? |
|--------|----------|----------|
| `SelectionValidator` | ¿Estas líneas se pueden seleccionar juntas? (4 campos) | Solo explicación |
| `PermissionChecker` | ¿Este rol puede hacer esto? | No |
| `StatusTransitionValidator` | ¿Este cambio de estado es válido? | No |
| `InductorSelector` | ¿Qué inductores aplican a esta línea? | Sí (razonamiento) |
| `EstimationCalculator` | Calcular Total = (Variable × Occurrence) + Fixed | No |
| `SendEligibilityChecker` | ¿Esta estimación se puede enviar a HVT? | No |
| `HVTCallbackProcessor` | Procesar approve/reject de CPO | No |
| `CSVExporter` | Generar CSV con formato exacto del spec | No |

**Regla de oro:** la IA solo se usa para lo que requiere razonamiento humano (ej: "¿qué inductores aplicarían aquí?"). Todo lo demás es código determinista.

### 3. Pipeline — Orquestación por vista

Cada vista del sistema tiene su propio pipeline que llama a los módulos en orden:

```
Pre-Estimation Pipeline:
  1. Selection Validation  →  2. Permission Check  →  3. Load Workload Standard
  →  4. Calculate Estimation  →  5. Validate Save  →  6. Monthly Distribution
  →  7. Summary

Estimation Review Pipeline:
  1. Permission Check  →  2. Render Grid (derived columns)
  →  3. Send-to-HVT Eligibility  →  4. HVT Callback Processing
  →  5. CSV Export
```

### 4. Tests de specs — No tests de código

No testeamos que "la función suma bien". Testeamos que **las reglas de negocio se cumplen**:

```python
def test_todo_to_estimated_invalid_no_draft_gate(self):
    """BR-02: No puedes saltar el Draft gate"""
    result = validator.forward("to_do", "estimated")
    assert result["is_valid"] is False

def test_null_vs_value_incompatible(self):
    """§5.2: null vs valor = incompatible"""
    assert are_lines_compatible(lines_with_null_and_value) is False

def test_sent_shows_pending_for_cpo(self):
    """§5.2: Sent muestra ⏳ Pending en columna CPO"""
    assert CPO_APPROVAL_MAP[LineStatus.SENT] == "⏳ Pending"
```

---

## Qué es DSPy y por qué lo usamos

[DSPy](https://github.com/stanfordnlp/dspy) es un framework de Stanford NLP que reemplaza el prompt engineering manual por **programación declarativa**.

En lugar de:

```python
# Prompt engineering tradicional — frágil, no testeable
prompt = f"Eres un experto en estimación. Dados los inductores {x}, calcula..."
```

DSPy propone:

```python
# Programación declarativa — verificable, optimizable
class GenerateEstimate(dspy.Signature):
    """Calcular total de estimación."""
    job_units = dspy.InputField()
    total_fte = dspy.OutputField()

estimator = dspy.ChainOfThought(GenerateEstimate)
```

**Lo que DSPy aporta a este proyecto:**
- **Signatures** que definen contratos input/output (ya las tenemos en `signatures/`)
- **Optimizadores** que mejoran los prompts automáticamente con datos de entrenamiento (BootstrapFewShot, MIPRO)
- **Modularidad** — cada módulo es independiente y reutilizable

> NOTA: El Stanford DSPy no pudo instalarse en este entorno por restricciones corporativas. La arquitectura está diseñada para recibirlo cambiando 3 imports. Mientras tanto, usamos un LM client propio (OpenAI-compatible).

---

## ¿Para qué sirve todo esto?

### 1. Cuando cambie una regla de negocio

Cambias **UNA línea** en el spec. 130 tests te confirman que nada más se rompe.

**Antes:** "Cambiamos el estado del sistema" →改了10 archivos, 3 bugs en producción, 2 días de regresión.

**Ahora:** `patch` a `pre_estimation_specs.py` → `pytest` → 130 green → commit.

### 2. Cuando el modelo de IA alucine

La IA sugiere una transición Approved→Draft. `StatusTransitionValidator` la bloquea porque el spec dice que Approved es terminal. Sin ambigüedad, sin depender de que el prompt sea "lo suficientemente bueno".

### 3. Cuando llegue un nuevo developer

No lee 50 páginas de PRD — lee `pre_estimation_specs.py` y ve la máquina de estados completa en 15 líneas. Lee `estimation_review_specs.py` y entiende el flujo HVT en 10 minutos.

### 4. Cuando quieras migrar a DSPy real

Las Signatures ya están como dataclasses, los Modules ya tienen `forward()`, el Pipeline ya es composable. Cambias la herencia de `Module` a `dspy.Module` y tienes optimización automática de prompts.

---

## Lo que hemos construido hasta ahora

| Vista | Reglas | Módulos | Tests | Estado |
|-------|--------|---------|-------|--------|
| Pre-Estimation | 17 BR + state machine + 6 métiers | 8 | 68 | ✅ Completo |
| Estimation Review | 10 BR + HVT flow + CSV export | 6 | 62 | ✅ Completo |
| Allocation | — | — | — | ⬜ Pendiente |
| Final Review | — | — | — | ⬜ Pendiente |
| Management | — | — | — | ⬜ Pendiente |
| Admin | — | — | — | ⬜ Pendiente |
| **Total** | **27 reglas** | **14 módulos** | **130 tests** | **2/6 vistas** |

---

## Quick Start

```bash
# Clonar
git clone https://github.com/nujovich/great-dspy-pipeline.git
cd great-dspy-pipeline

# Instalar dependencias
pip install pytest

# Ejecutar tests
python -m pytest tests/ -v

# Usar el pipeline
python -c "
from great_dspy.pipeline.pre_estimation_pipeline import run_pipeline

ctx = run_pipeline(
    selected_lines=[{'id': 'PL-001', 'assignee': 'Ana', 'status': 'to_do', 'sp_date': '2026-01-01'}],
    role='Engineer',
    current_user='Ana Martinez',
    metier='Backend',
)
print(f'Can save draft: {ctx.can_save_draft}')
print(f'Total FTE: {ctx.total_fte}')
"
```

---

## Repositorio

[https://github.com/nujovich/great-dspy-pipeline](https://github.com/nujovich/great-dspy-pipeline)