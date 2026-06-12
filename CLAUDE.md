# GREAT System — SDD Pipeline

@AGENTS.md

Este repositorio contiene especificaciones ejecutables del sistema GREAT usando el patrón SDD (Specification-Driven Development).

Referencia rápida:
- `great_sdd/specs/` → Reglas de negocio como datos (92 reglas en 6 vistas)
- `great_sdd/modules/` → Lógica del negocio (30 módulos, Python puro)
- `great_sdd/pipeline/` → Blueprint de orquestación para endpoints
- `great_sdd/conformance/` → 4ª capa: el SDD como *oracle* determinista. Emite golden
  fixtures JSON (`fixtures/`) que son el contrato cross-language (Python + TypeScript).
- `tests/` → 321 tests que verifican las reglas (incluye la suite de conformance)

> El número de reglas (92) se deriva programáticamente con
> `great_sdd/conformance/rule_inventory.py`; no lo hardcodees en cambios futuros.

## Capa de conformance

La 4ª capa permite que cualquier consumidor (backend Python o frontend TypeScript) pruebe
que su código cumple las mismas reglas, de forma hermética y en CI. Reglas:
- **Todo determinista**: la generación corre con un *Tripwire LM* inyectado; si una regla
  cubierta llama a un LLM, aborta. Nada toca red, LLM, timestamps ni aleatoriedad.
- **Fixtures byte-estables**: claves ordenadas, indent 2, newline final. Mismo oracle +
  mismo código → mismos bytes.
- **Nunca se descarta una regla en silencio**: las exclusiones están documentadas con razón
  en `great_sdd/conformance/exclusions.py` y aparecen en cada reporte de cobertura.

Comandos (requiere Python ≥3.11):
```bash
python -m great_sdd.conformance.generate            # (re)generar fixtures
python -m great_sdd.conformance.generate --check    # CI: exit 1 si hay drift
python -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70
python -m great_sdd.conformance.collection generate   # exporta collections Bruno/Postman desde los endpoint fixtures
python -m great_sdd.conformance.collection export --out great-collections.zip   # bundle .zip portable
```

Cobertura actual: **55/55 reglas cubribles (100%)**; las 40 restantes son exclusiones
documentadas (LM-only o sin superficie de función). Fixtures estampados en `sdd_version 2.0.0`.
