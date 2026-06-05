# GREAT System — SDD Pipeline

**Este repositorio NO es documentación para humanos. Es fuel para agentes de IA.**

Las 92 reglas de negocio del sistema GREAT están codificadas como **especificaciones ejecutables** en `great_sdd/specs/`. Los agentes de IA (Claude, Codex, Copilot, Cursor) leen estos archivos, entienden las reglas, y generan código que las cumple — validado por 320 tests.

## Cómo funciona

```
Desarrollador → Pasa el repo a un agente de IA
                     ↓
              Agente lee AGENTS.md + specs/ + modules/ + tests/
                     ↓
              Agente genera código backend/UI
                     ↓
              pytest tests/ → 320 tests validan que cumple las 92 reglas
                     ↓
              Código listo para producción
```

## Para el desarrollador

1. Dale este repo a tu agente de IA favorito (Claude, Codex, Copilot, Cursor)
2. El agente lee `AGENTS.md` que le explica las reglas
3. El agente genera código basado en `specs/` + `modules/` + `pipeline/`
4. Corres `pytest tests/ -v` para validar
5. 320 tests = 92 reglas de negocio verificadas

## Archivos clave para el agente

| Archivo | Qué contiene |
|---------|-------------|
| `AGENTS.md` | Instrucciones para el agente de IA |
| `great_sdd/specs/pre_estimation_specs.py` | 17 reglas, state machine, 6 métiers, fórmulas |
| `great_sdd/specs/estimation_review_specs.py` | 10 reglas, HVT flow, approval columns |
| `great_sdd/specs/allocation_specs.py` | 16 reglas, K€ rates, societes, split |
| `great_sdd/specs/final_review_specs.py` | 10 reglas, Stage 3, aggregation |
| `great_sdd/specs/management_view_specs.py` | 8 reglas, pie chart, timeline |
| `great_sdd/specs/transversal_specs.py` | 13 reglas, cycles, workload, tables, email |
| `great_sdd/modules/` | Lógica pura del negocio (importable) |
| `great_sdd/pipeline/` | Blueprint de endpoints por vista |
| `tests/` | 320 tests que verifican todo |

## Conformance (4ª capa)

El SDD es un **oracle determinista**: emite golden fixtures JSON (`great_sdd/conformance/fixtures/`) que cualquier consumidor (Python o TypeScript) usa para auto-verificarse en CI, sin LLM ni red. Ver `great_sdd/conformance/README.md`.

## Repositorio

https://github.com/nujovich/great-sdd-kit