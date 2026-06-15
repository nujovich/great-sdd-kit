# Endpoint Conformance — `GET /project-lines`

**Fecha:** 2026-06-10
**Estado:** Diseño aprobado (pendiente revisión de spec)
**Rama:** `feat/conformance-layer-2.0.0`

## Contexto

La capa de conformance del SDD Kit (4ª capa) hoy es **rule-céntrica**: cada golden
fixture liga `rule_ids` → función pura → `expected_output`. Sirve para probar reglas de
negocio aisladas, no respuestas de endpoints HTTP.

Queremos que la capa de conformance también emita un golden fixture con la **forma y el
comportamiento de la respuesta real** de un endpoint, empezando por `GET /api/v1/project-lines`,
que devuelve `{ "data": [...], "filterOptions": {...} }`.

**Fuente de verdad: un contrato externo** (no inventamos el schema). Vive en el monorepo
hermano `cap_horse_great*`:
- OpenAPI: `cap_horse_great/docs/open-api/pev-openapi.yaml`
- DTO Pydantic: `cap_horse_great_back/app/application/dtos/project_line.py`
- Tipos TS: `cap_horse_great_front/src/types/project-line.ts`
- Contract lock (24 campos): `cap_horse_great_back/tests/integration/api/test_project_lines.py`

**Decisiones tomadas** (brainstorming):
1. **Fuente del schema:** espejar el contrato externo (openapi/back = verdad).
2. **Alcance:** comportamiento completo (scoping por rol, filtros, códigos de error, filterOptions), no solo shape.
3. **Ownership:** solo capa de conformance — un módulo de "endpoint probes". **No** se agrega una vista ni reglas al censo de 92; el SDD refleja el contrato para el test cross-language.

### Objetivo / resultado esperado

Un golden fixture byte-stable que el frontend (TS) y el backend (Python) consumen como
**contrato compartido cross-language** de `GET /project-lines`, generado por un oracle
determinista que espeja la conducta documentada del endpoint. Reutiliza el motor existente
(tripwire, writer byte-stable, gate `--check`) sin contaminar el censo de reglas de negocio.

### No-objetivos (YAGNI)

- No se agrega un framework HTTP ni se sirve el endpoint real desde el SDD.
- No se modela paginación/sorting (el contrato los declara client-side).
- No se agregan reglas `PL-BR-*` al censo ni una vista nueva.
- Solo `GET /project-lines` en este spec; otros endpoints reusan el patrón después.

## Contrato externo a espejar (resumen verbatim)

### `ProjectLine` — 24 campos (orden y nullability del DTO)
`id` (uuid), `pl_number` (str), `pl_name` (str), `status` (enum), `request_type` (str|null),
`client` (str|null), `metier` (enum), `organ_type` (str|null), `project_ranking` (str|null),
`market` (str|null), `alliance_code` (str|null), `vehicle_code` (str|null), `energy` (str|null),
`injection_system` (str|null), `standard_emissions` (str|null), `engineering` (str|null),
`estimate_type` (str|null), `sp_date` (date|null), `pc_date` (date|null), `co_date` (date|null),
`sop_date` (date|null), `assignee` (str|null, mapea de `assignee_oid`), `total_days` (int|null),
`total_keuro` (number|null).

> Requeridos: `id, pl_number, pl_name, status, metier`. El resto nullable.
> `total_days`/`total_keuro` siempre `null` (aún no se computan de job_units).

### Enums
- `ProjectLineMetier`: `H-DESIGN, H-TUNING, H-SOFTWARE, H-CUSTOMER, H-PROJECT, H-NP` (**sin H-TESTING**).
- `Status`: `"To do", Draft, Estimated, Sent, Rejected, Approved`.

### Envelope
`ProjectLinesResponse = { data: ProjectLine[], filterOptions: { assignees: string[], metiers: string[] } }`

### Comportamiento (de openapi + service `list_lines`)
- Acceso: Admin, PMO, RCRC, Engineer. **CPO → 403**, sin JWT → **401**, sin ciclo activo → **404**.
- **Engineer** hard-scoped a `assignee_oid == su oid`; el query `assignee` se ignora para Engineer.
- `filterOptions` reflejan el set **scoped por rol** (Engineer nunca ve OIDs ajenos), ignorando los filtros activos.
- Query `assignee`/`metier` para PMO/Admin/RCRC.
- H-NP y H-PROJECT se incluyen y son filtrables (sin exclusión de métier en este endpoint).

## Arquitectura (Approach A — facilidad de endpoint conformance en paralelo)

```
sdd/base_conformance.py
  + EndpointProbe (dataclass)
  + generate_endpoint_fixtures(probes, seed, sdd_version) -> list[dict]
  + run_endpoint_conformance(fixtures, consumer_fn) -> report

great_sdd/conformance/
  endpoints/
    __init__.py
    project_lines.py        ← oracle determinista (espeja list_lines) + SEED + probes
  fixtures/
    endpoints/
      project_lines.json    ← golden fixture byte-stable {seed, cases, sdd_version}
  generate.py               ← emite también endpoint fixtures; --check los cubre
  runner.py                 ← run_endpoint_conformance + oracle_endpoint_consumer_fn de ref
  coverage.py               ← reporta endpoints cubiertos, SEPARADO del censo de 92
```

### Unidades y responsabilidades

**`EndpointProbe`** (en `base_conformance.py`, domain-agnostic):
```
@dataclass
class EndpointProbe:
    endpoint: str                       # "GET /project-lines"
    name: str
    fn: Callable[[dict], dict]          # request -> {"status": int, "body": dict|None}
    cases: list[dict]                   # cada uno es un `request`
```

**`great_sdd/conformance/endpoints/project_lines.py`** — el oracle de referencia:
- `SEED: list[dict]` — filas fijas (UUIDs/OIDs hardcodeados). Ver §Seed.
- `PROJECT_LINE_FIELDS: list[str]` — los 24 campos en el orden del contrato.
- `PROJECT_LINE_METIERS`, `STATUSES` — enums espejados del contrato externo (constantes locales; **no** se importan del taxonómico del SDD, que incluye H-TESTING).
- `list_project_lines(request: dict) -> dict` — implementación determinista que espeja `list_lines`:
  - `active_cycle` false → `{"status": 404, "body": None}`
  - `role` None → `{"status": 401, "body": None}`
  - `role == "CPO"` → `{"status": 403, "body": None}`
  - Engineer: `scope_oid = user_oid`; `effective_assignee = user_oid` (ignora query assignee)
  - otros roles: `scope_oid = None`; `effective_assignee = query.assignee`
  - filtra SEED por `(effective_assignee, query.metier)` → `data` proyectada a los 24 campos
  - `filterOptions` = distinct `assignees`/`metiers` sobre el set scoped por `scope_oid` (ignora filtros activos)
  - ordena `data` por `pl_number`, y `assignees`/`metiers` alfabético (determinismo)
  - → `{"status": 200, "body": {"data": [...], "filterOptions": {...}}}`
- `PROBES: list[EndpointProbe]` — un probe con los casos (§Casos).

### Seed determinista (committeado en el fixture y en el módulo)

| id (uuid fijo) | pl_number | pl_name | metier | status | assignee_oid |
|---|---|---|---|---|---|
| 11111111-1111-4111-8111-111111111111 | PL-001 | Auth refactor | H-SOFTWARE | Rejected | oid-engineer-1 |
| 22222222-2222-4222-8222-222222222222 | PL-002 | OAuth integration | H-DESIGN | To do | oid-engineer-2 |
| 33333333-3333-4333-8333-333333333333 | PL-003 | NP line | H-NP | To do | oid-engineer-1 |
| 44444444-4444-4444-8444-444444444444 | PL-004 | Infra deploy | H-PROJECT | Draft | oid-pmo |

Todos los demás campos del DTO → `null` (incluye `total_days`/`total_keuro`). UUIDs v4-shaped
pero **fijos**; sin `gen_random_uuid`, sin timestamps.

### Casos (cada uno = un `request` → `expected {status, body}`)

1. **Engineer scoped** — `{role:"Engineer", user_oid:"oid-engineer-1", query:{}, active_cycle:true}` → 200, data = PL-001 + PL-003 (sus 2 líneas), `filterOptions.assignees=["oid-engineer-1"]`, `metiers=["H-NP","H-SOFTWARE"]`.
2. **PMO ve todo** — `{role:"PMO", user_oid:"oid-pmo", query:{}, active_cycle:true}` → 200, data = las 4, `assignees=["oid-engineer-1","oid-engineer-2","oid-pmo"]`, `metiers=["H-DESIGN","H-NP","H-PROJECT","H-SOFTWARE"]`.
3. **Filtro metier (PMO)** — `{role:"PMO", query:{metier:"H-DESIGN"}, active_cycle:true}` → 200, data = PL-002; `filterOptions` siguen siendo el set completo (ignoran filtros activos).
4. **Engineer ignora filtro assignee** — `{role:"Engineer", user_oid:"oid-engineer-1", query:{assignee:"oid-engineer-2"}, active_cycle:true}` → 200, data = PL-001 + PL-003 (el query assignee se ignora).
5. **CPO → 403** — `{role:"CPO", active_cycle:true}` → `{status:403, body:null}`.
6. **Sin ciclo activo → 404** — `{role:"PMO", active_cycle:false}` → `{status:404, body:null}`.
7. **Sin rol/JWT → 401** — `{role:null, active_cycle:true}` → `{status:401, body:null}`.

### Formato del fixture — `fixtures/endpoints/project_lines.json`

```json
{
  "endpoint": "GET /project-lines",
  "sdd_version": "2.0.0",
  "seed": [ { /* las 4 filas, 24 campos cada una */ } ],
  "cases": [
    { "request": { "role": "Engineer", "user_oid": "oid-engineer-1", "query": {}, "active_cycle": true },
      "expected": { "status": 200, "body": { "data": [ ... ], "filterOptions": { ... } } } }
  ]
}
```

Byte-stable vía `canonical_json` (sorted keys, indent 2, newline final). `cases` ordenados
determinísticamente (por `canonical_json(request)`).

### Runner / consumo cross-language

`run_endpoint_conformance(fixtures, consumer_fn)`:
- A cada caso le pasa `{"endpoint", "request"}` (con el `seed` accesible aparte) — **nunca** `expected`.
- `consumer_fn` devuelve `{"status", "body"}`; exact-match contra `expected`.
- Reporta `passed`, `failures`, y `endpoints_exercised`.

Consumidores:
- **Frontend** (hoy mock en `project-line.service.ts`): carga el JSON como data del mock **y**
  test de contrato contra `ProjectLinesResponse`. No Python, no red.
- **Backend**: opcional — siembra `seed` en su DB de test, llama `list_lines` por cada `request`,
  compara. Complementa el `EXPECTED_PROJECT_LINE_KEYS` existente.
- **Oracle de referencia**: `runner.py` trae `oracle_endpoint_consumer_fn` = re-corre el propio
  oracle; pasa el 100% de los casos (self-check).

### Coverage

`coverage.py` agrega un bloque **separado**: "Endpoints cubiertos: GET /project-lines (7 casos)".
No entra en el cómputo de 55/92 reglas; el censo de negocio queda intacto.

## Determinismo y divergencias

- Sin red, LLM, timestamps ni aleatoriedad. El oracle corre bajo `TripwireLM` (trivialmente
  LM-free: es filtrado/proyección puro).
- Regenerar dos veces → diff vacío (byte-stability).
- **Divergencia documentada:** el enum métier del endpoint (6 valores, sin H-TESTING) difiere del
  taxonómico del SDD (`great_sdd/specs/pre_estimation_specs.py`, que incluye H-TESTING). El oracle
  de endpoint usa el del **contrato externo**; se deja constancia para que un futuro lector no lo
  "corrija" hacia el taxonómico del SDD.

## Testing

Nuevos tests en `tests/test_conformance.py` (o `tests/test_endpoint_conformance.py`):
1. **Self-check**: `oracle_endpoint_consumer_fn` pasa los 7 casos (exact-match).
2. **Byte-stability**: `generate --check` no reporta drift para `fixtures/endpoints/`.
3. **Tripwire**: la generación corre con `TripwireLM` sin abortar.
4. **Contrato de campos**: cada `data[]` tiene exactamente los 24 campos del contrato (paridad con `EXPECTED_PROJECT_LINE_KEYS`).
5. **Reglas de conducta**: asserts puntuales — Engineer ve solo sus líneas; CPO→403; sin ciclo→404; filterOptions scoped.
6. **Enum métier**: ningún `data[].metier` ni `filterOptions.metiers` contiene `H-TESTING`.

### Verificación end-to-end

```bash
python3 -m great_sdd.conformance.generate            # genera rule + endpoint fixtures
python3 -m great_sdd.conformance.generate --check     # exit 1 si drift (incluye endpoints)
python3 -m great_sdd.conformance.coverage --from-fixtures --threshold 0.70   # reglas intactas + bloque endpoints
python3 -m pytest tests/ -q                           # suite completa verde
```

## Archivos a tocar

| Archivo | Acción |
|---|---|
| `sdd/base_conformance.py` | + `EndpointProbe`, `generate_endpoint_fixtures`, `run_endpoint_conformance` |
| `great_sdd/conformance/endpoints/__init__.py` | nuevo |
| `great_sdd/conformance/endpoints/project_lines.py` | nuevo — SEED + oracle + probes |
| `great_sdd/conformance/fixtures/endpoints/project_lines.json` | nuevo — golden (generado) |
| `great_sdd/conformance/generate.py` | emitir endpoint fixtures + `--check` |
| `great_sdd/conformance/runner.py` | + `run_endpoint_conformance` + consumer de ref |
| `great_sdd/conformance/coverage.py` | bloque de endpoints (separado del censo) |
| `tests/test_conformance.py` | + tests de endpoint conformance |
| `great_sdd/conformance/README.md` | documentar la sub-capa de endpoints |
