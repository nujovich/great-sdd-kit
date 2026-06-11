# API Collection Export — Bruno + Postman from conformance endpoint fixtures

**Fecha:** 2026-06-10
**Estado:** Diseño aprobado (pendiente revisión de spec)
**Rama:** `feat/conformance-layer-2.0.0`
**Depende de:** la sub-capa de endpoint conformance (`fixtures/endpoints/*.json`, oracles en `great_sdd/conformance/endpoints/`).

## Contexto

El golden fixture `fixtures/endpoints/project_lines.json` es óptimo para diff byte-stable,
pero **ilegible para explorar la API**. Queremos derivar de él artefactos consumibles:

1. Una **collection importable** a **Bruno** y a **Postman** con, por request: query
   params + body (si aplica) + **respuestas-ejemplo guardadas por escenario/status** + el
   **JSON Schema de entrada y salida** en la descripción (markdown).
2. Un **`examples.json`** legible con **todos los casos** (todos los status) por endpoint.

**Decisiones (brainstorming):**
- **Formato:** ambos — Postman Collection v2.1 (`postman_collection.json`) **y** carpeta nativa Bruno (`.bru` + `bruno.json`).
- **Esquema:** ejemplos guardados + JSON Schema (in/out) en la descripción de cada request.
- **Distribución:** los artefactos van **committeados** (run por defecto sobre los fixtures del repo) **y** el generador corre **on-demand** sobre data nueva que traiga el usuario.
- **`examples.json`:** todos los casos/status por endpoint.

### Fork de diseño clave (request lógico vs HTTP)

El `request` del fixture es el input *lógico* del oracle (`role`, `user_oid`, `query`,
`active_cycle`), **no** el request HTTP. El HTTP real de `GET /project-lines` es
`GET /api/v1/project-lines?assignee=&metier=` con header `Authorization: Bearer <jwt>`;
`role`/`user_oid`/`active_cycle` provienen del **token/estado del server**, no son inputs
HTTP. Por eso los N casos del fixture (PMO→200, CPO→403, sin-ciclo→404, …) mapean a **un
solo request HTTP** con **varios examples guardados**, uno por escenario. Esto exige un
**binding HTTP** por endpoint (method, path, query params, auth) además del schema.

## Objetivo / no-objetivos

**Objetivo:** un generador determinista en la capa de conformance que, leyendo los endpoint
fixtures + el binding/schema declarado por cada oracle, emita Postman v2.1 + Bruno +
`examples.json`; corre por defecto sobre los fixtures committeados y on-demand sobre data
provista por el usuario.

**No-objetivos (YAGNI):** no ejecuta requests reales; no resuelve auth/JWT (usa placeholders
`{{token}}`); no genera la collection de los ~40 endpoints del openapi — solo de los que
tienen oracle de conformance (hoy `GET /project-lines`); no agrega reglas al censo.

## Arquitectura (Approach A — generador en la capa, binding/schema en el oracle)

```
great_sdd/conformance/
  endpoints/project_lines.py   (modify) + HTTP_BINDING + REQUEST_SCHEMA + RESPONSE_SCHEMA
  collection.py                (create)  generador: fixtures -> Postman + Bruno + examples
  fixtures/endpoints/collections/         (generated, committed)
    postman_collection.json
    examples.json
    bruno/
      bruno.json
      <Endpoint>.bru
```

### Metadata nueva en el oracle (`endpoints/project_lines.py`)

Mirroreado del openapi (`pev-openapi.yaml`), self-contained:

```python
HTTP_BINDING = {
    "method": "GET",
    "path": "/project-lines",        # base server is /api/v1 (collection var {{baseUrl}})
    "query_params": ["assignee", "metier"],
    "auth": "bearer",
    "body": None,                    # GET has no body
}
REQUEST_SCHEMA = { ... }   # JSON Schema of query params (assignee:str, metier:enum)
RESPONSE_SCHEMA = { ... }  # JSON Schema of ProjectLinesResponse (24-field ProjectLine + filterOptions)
```

No new abstraction is needed: `collection.py` keeps a small registry (like the runner's
`_ENDPOINT_ORACLES`) mapping each endpoint name → its oracle module, and reads
`HTTP_BINDING`/`REQUEST_SCHEMA`/`RESPONSE_SCHEMA` plus the matching `fixtures/endpoints/*.json`.
The schemas reuse the oracle's `PROJECT_LINE_FIELDS` names so they stay in sync.

### Generador `great_sdd/conformance/collection.py`

Responsabilidad única: transformar endpoint fixtures + binding/schema → artefactos. Pasos
puros (sin red/LLM/tiempo):
- `build_postman(endpoints) -> dict` — Collection v2.1: `info` + un `item` por endpoint
  (`request`: method, `{{baseUrl}}{path}` + query params; header `Authorization: Bearer {{token}}`;
  body si aplica; `description` markdown con ambos JSON Schema) + `response[]` (un example por
  caso del fixture: `name` = escenario legible, `code` = status, `body` = expected.body).
- `build_bruno(endpoints) -> dict[str, str]` — `bruno.json` + un `<Endpoint>.bru` por endpoint
  (bloques `meta`/`get`/`headers`/`docs`), examples reflejados en `docs`.
- `build_examples(endpoints) -> dict` — `{ "GET /project-lines": [ {scenario, request, response:{status,body}}, ... todos los casos ] }`.
- Escenario legible derivado del caso: ej. `"PMO — all lines (200)"`, `"CPO — forbidden (403)"`,
  `"no active cycle (404)"`, `"no JWT (401)"` — función pura `_scenario_label(case)` a partir de `role`/`active_cycle`/`query` y el status esperado.
- Variables de collection: `baseUrl = /api/v1`, `token = <JWT placeholder>`.

### CLI / determinismo

El módulo usa subcomandos (argparse subparsers):

```bash
python -m great_sdd.conformance.collection generate                       # default: lee fixtures/endpoints/, escribe fixtures/endpoints/collections/
python -m great_sdd.conformance.collection generate --check                # CI: exit 1 si los artefactos committeados driftan
python -m great_sdd.conformance.collection generate --fixtures-dir DIR --out DIR   # on-demand sobre data del usuario
python -m great_sdd.conformance.collection download --out coleccion.zip     # empaqueta las collections en UN zip portable
python -m great_sdd.conformance.collection download --fixtures-dir DIR --out c.zip   # zip a partir de data on-demand
```

- **`generate`:** produce/`--check`ea los artefactos en disco (el run por defecto queda committeado).
- **`download`:** empaqueta en UN `.zip` portable el `postman_collection.json` + la carpeta
  `bruno/` + `examples.json`, listo para compartir/importar sin clonar el repo. Por defecto
  arma el zip desde las collections committeadas; con `--fixtures-dir` arma el zip on-demand a
  partir de data nueva del usuario (genera en memoria y comprime, sin tocar el árbol committeado).
  Salida por defecto `--out great-collections.zip`.
- **On-demand con data nueva:** el usuario regenera un endpoint fixture con su propio seed
  (`generate` con datos nuevos) o arma un JSON con la forma `{endpoint, seed, cases}` y apunta
  `--fixtures-dir` a su carpeta — sirve tanto para `generate` como para `download`.
- Byte-stable vía `canonical_json` (sorted keys, indent 2, newline final); `.bru` con orden de
  bloques fijo. El `.zip` es determinista: cada entrada se escribe con un `date_time` fijo
  (constante, no `now()`) y orden de archivos estable, así el mismo input produce el mismo zip.

## Data flow

```
fixtures/endpoints/*.json  ──┐
oracle HTTP_BINDING+SCHEMAS ─┤→ collection.py ─→ postman_collection.json
                             │                  ─→ bruno/*.bru + bruno.json
                             └─────────────────  ─→ examples.json
```

## Testing (`tests/test_conformance.py` o `tests/test_collection.py`)

1. **Postman v2.1 válido:** tiene `info.schema` v2.1.0 + `item[]`; el item de project-lines tiene method GET, url con `{{baseUrl}}/project-lines`, header Authorization Bearer, y `response[]` con un example por caso del fixture (7).
2. **Bruno:** se genera `bruno.json` + un `.bru` por endpoint; el `.bru` parsea (bloques esperados) y nombra los escenarios.
3. **examples.json:** una entrada por endpoint, con TODOS los casos (7 para project-lines), cada uno con `request` + `response{status,body}`.
4. **Schema embebido:** la descripción del request contiene los 24 campos del contrato y no incluye `H-TESTING` en el enum métier.
5. **Byte-stability:** `collection --check` no reporta drift tras regenerar; regenerar dos veces = bytes idénticos.
6. **On-demand:** correr el generador con un `--fixtures-dir` temporal (un fixture mínimo) produce artefactos coherentes (smoke).
7. **download (zip):** `download --out tmp.zip` crea un zip que contiene `postman_collection.json`, `examples.json` y `bruno/...`; reabrirlo (`zipfile`) lista esas entradas y su contenido coincide con `generate`. El zip es determinista (dos corridas → mismos bytes, gracias al `date_time` fijo).

### Verificación end-to-end

```bash
python3 -m great_sdd.conformance.collection            # genera artefactos
python3 -m great_sdd.conformance.collection --check     # exit 0, sin drift
python3 -m pytest tests/ -q                             # suite verde
# Manual: importar fixtures/endpoints/collections/postman_collection.json en Postman y la carpeta bruno/ en Bruno
```

## Archivos

| Archivo | Acción |
|---|---|
| `great_sdd/conformance/endpoints/project_lines.py` | + `HTTP_BINDING`, `REQUEST_SCHEMA`, `RESPONSE_SCHEMA` |
| `great_sdd/conformance/collection.py` | nuevo — generador Postman/Bruno/examples + CLI con subcomandos `generate` y `download` (zip) |
| `great_sdd/conformance/fixtures/endpoints/collections/postman_collection.json` | generado, committeado |
| `great_sdd/conformance/fixtures/endpoints/collections/examples.json` | generado, committeado |
| `great_sdd/conformance/fixtures/endpoints/collections/bruno/` | generado, committeado |
| `tests/test_conformance.py` | + tests del generador |
| `great_sdd/conformance/README.md` | documentar el export de collections + uso on-demand |

## Divergencias / notas
- El binding/schema se re-encodea a mano desde el openapi (igual que ya se hace con los 24
  campos), manteniendo la capa self-contained; riesgo de drift documentado. Un futuro
  endpoint puede sumar su binding/schema con el mismo patrón.
- El enum métier del schema embebido excluye `H-TESTING` (contrato de project-lines), igual que el oracle.
