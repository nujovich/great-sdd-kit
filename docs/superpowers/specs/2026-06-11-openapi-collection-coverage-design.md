# Full-API Collection Coverage from the Vendored OpenAPI

**Fecha:** 2026-06-11
**Estado:** Diseño aprobado (pendiente revisión de spec)
**Rama:** (nueva, a partir de `feat/conformance-layer-2.0.0` / master tras merge)
**Sub-proyecto 1 de 2** — el 2 (oracles de conformance curados) es spec aparte.

## Contexto

La capa de conformance ya exporta collections Bruno/Postman, pero solo cubre los endpoints
con **oracle de conformance** (hoy `GET /project-lines`). El equipo quiere la **API completa**
importable. El contrato externo (`cap_horse_great/docs/open-api/pev-openapi.yaml`) define **43
operaciones** y **71 schemas**. Casi no trae `example`s (1 sola), así que los ejemplos se
**sintetizan** del JSON Schema.

Decisión de descomposición (brainstorming): híbrido en dos sub-proyectos. **Este spec = sub-proyecto 1:**
cobertura de collection para los 43 endpoints generada desde un snapshot del openapi. El
sub-proyecto 2 (oracles deterministas de conducta para un set curado) va aparte.

**Decisiones tomadas:**
- **Vendoring:** snapshot del openapi convertido a **JSON committeado** (`contracts/pev-openapi.json`), leído con `json` stdlib (sin dependencia nueva, hermético, determinista). Script/nota documenta el refresh.
- **Ejemplos:** sintetizados del schema (resolviendo `$ref`), deterministas.
- **Carpetas:** por las **6 vistas** del SDD, agrupando tags afines (mapa abajo).
- **examples.json + examples guardados:** **todas** las respuestas documentadas por endpoint, **incluidos los 4xx**.

### Objetivo / no-objetivos

**Objetivo:** un generador determinista que, desde el openapi vendoreado, emita Bruno + Postman +
`examples.json` cubriendo las 43 operaciones, organizadas en 6 carpetas (vistas), con request/response
JSON Schema en docs y un ejemplo sintetizado por cada response code (200/4xx). Donde exista un oracle
de conformance, se usan sus ejemplos ricos por escenario en vez de los sintetizados.

**No-objetivos (YAGNI):** no re-implementa la conducta de cada endpoint (eso es el sub-proyecto 2); no
ejecuta requests; no resuelve auth (placeholders `{{baseUrl}}`/`{{token}}`); no agrega reglas al censo.

## Mapa tag → vista (6 carpetas)

| Vista (carpeta) | Tags del openapi |
|---|---|
| Pre-Estimation | `ProjectLines`, `Estimation`, `Prototype` |
| Estimation Review | `EstimationReview`, `HVT` |
| Allocation | `Allocation`, `AllocationConfig` |
| Final Review | `FinalReview` |
| Management View | `ManagementView` |
| Transversal | `Transversal` |

(El mapa vive como `TAG_TO_VIEW` en `openapi.py`; un tag desconocido cae en una carpeta "Other" y se `log`uea, para no perder endpoints en silencio.)

## Arquitectura

```
great_sdd/conformance/
  contracts/pev-openapi.json        (create, committed)  snapshot del contrato externo
  contracts/REFRESH.md              (create)             cómo regenerar el JSON desde el .yaml
  openapi.py                        (create)  loader + $ref deref + synth example + iter_operations + TAG_TO_VIEW
  collection.py                     (modify)  descriptor unificado + merge openapi⊕fixtures + folders
  endpoints/project_lines.py        (unchanged — sigue siendo el oracle rico)
  fixtures/endpoints/collections/   (regenerated, committed)  ahora cubre las 43 ops en 6 carpetas
tests/test_conformance.py           (modify)  tests del loader/synth/merge/folders
scripts/refresh_openapi_snapshot.py (create)  yaml→json (usa PyYAML solo en dev, no en runtime)
```

### `openapi.py` (parsing puro, foco único)

- `OPENAPI_PATH = .../contracts/pev-openapi.json`; `load_openapi()` → dict.
- `deref(spec, node)` → si `node` tiene `$ref` (`#/components/schemas/X` o `#/components/responses/X`), lo resuelve; recursivo-shallow.
- `synthesize_example(schema, spec, _seen=())` → valor JSON determinista:
  - `$ref` → deref y recursión (con guard de ciclos vía `_seen` de refs visitados → corta a `None`).
  - `enum` → primer valor. `type:object` → dict con las `properties` de `required` (o todas si no hay required), recursivo. `type:array` → `[synthesize(items)]`. `string`+`format:uuid`→`"00000000-0000-4000-8000-000000000000"`; `format:date`→`"2026-01-01"`; `format:date-time`→`"2026-01-01T00:00:00Z"`; string→`"string"`. `integer`→`0`. `number`→`0`. `boolean`→`false`. `["string","null"]`/nullable → el valor tipado (no null, para que ilustre).
- `iter_operations(spec)` → ordenado por `(view, path, method)`; por op:
  `{name:"METHOD /path", tag, view, method, path, path_params:[...], query_params:[...], auth, request_schema|None, response_schemas:{code: schema|None}}`.
  `path_params` se derivan de `{...}` en el path y/o `parameters[in=path]`; `query_params` de `parameters[in=query]`. Cada response code resuelve `content.application/json.schema` (deref de `components/responses` cuando aplica); code sin content → schema `None`.

### Descriptor unificado + merge (`collection.py`)

Refactor: `build_postman`/`build_bruno`/`build_examples` pasan a consumir una lista de **descriptores unificados**:
```
{name, view, method, path, path_params, query_params, auth,
 request_schema, request_body_example, response_schema,         # para docs/url/body
 examples:[{scenario, status, body}, ...]}                       # uno por response code, o ricos por escenario
```
- **Desde openapi** (`_descriptors_from_openapi`): por cada op, `request_body_example = synthesize_example(request_schema)`; `examples = [{scenario:f"{code}", status:int(code), body: synthesize_example(response_schemas[code]) or None} for code in sorted(codes)]`; `response_schema` = el del 200/201.
- **Desde fixtures** (`_descriptors_from_fixtures`, lo actual): project-lines con sus 7 escenarios; `examples` = los ricos (200/401/403/404 por escenario).
- **Merge** (`_unified_descriptors`): índice por `name` ("METHOD /path"); la versión fixture **pisa** la openapi. Los demás quedan de openapi. Orden estable por `(view, path, method)`.

Builders (adaptados al descriptor; las piezas existentes `_pm_url`/`_pm_headers`/`_markdown_docs`/`_indent_docs`/`_scenario_label` se reusan):
- **Postman v2.1:** top-level `item[]` = **6 folders** `{name: view, item:[requests]}` (orden fijo de vistas). Cada request: method, url `{{baseUrl}}{path}` con path params como `:param` y query params; header Bearer; `body` (raw JSON) = `request_body_example` para mutaciones; `description` = schemas (request+response) en markdown; `response[]` = un example guardado por cada code (body sintetizado o "" si null; `_postman_previewlanguage` text cuando vacío; `status` label del code).
- **Bruno:** subcarpeta por vista → `bruno/<view-slug>/<op-slug>.bru`; `meta`/`<method>`/`headers`/`auth:bearer`/`body:json` (para mutaciones)/`docs` (schemas + lista de escenarios con sus status), docs indentado (`_indent_docs`).
- **examples.json:** `{ "METHOD /path": {view, examples:[{scenario, status, body}, ...]} }` — todos los codes.

### CLI / determinismo

`generate`/`export` no cambian de interfaz; ahora el set de endpoints = merge openapi⊕fixtures (43 ops). `--check` byte-stable. Sintetización sin random/tiempo (valores fijos); orden estable; `canonical_json`; zip determinista. Path params (`:id`) y query params como variables/blank.

## Testing (`tests/test_conformance.py`)

1. **loader+deref:** `load_openapi()` parsea; `deref` resuelve un `$ref` de `components/schemas` y uno de `components/responses`.
2. **synthesize_example:** object→required props; array→1 ítem; enum→primero; `format:uuid`/`date` fijos; nullable→valor tipado; `$ref` recursivo; ciclo no cuelga (corta a None).
3. **iter_operations:** devuelve 43 ops; una mutación conocida (`PUT /project-lines/{id}/allocation`) tiene `request_schema` no-None y `path_params==["id"]`; cada op tiene ≥1 response code.
4. **merge:** el descriptor de `GET /project-lines` usa los ejemplos del FIXTURE (7 escenarios, incluye 403/404/401), no el sintetizado; el resto viene de openapi.
5. **Postman folders:** `item[]` tiene exactamente 6 folders con los nombres de las vistas; el total de requests anidados == 43; una mutación lleva `request.body` no vacío y su description incluye "Request schema"; un endpoint tiene examples para sus 4xx (p.ej. un `code==404`).
6. **Bruno:** un `.bru` por op bajo `bruno/<view>/`; ningún bare `}` dentro del bloque `docs` (regresión del bug ya conocido).
7. **byte-stability + zip:** `collection generate --check` sin drift; `build_zip_bytes` determinista; regenerar 2× = idéntico.

### Verificación end-to-end

```bash
python3 scripts/refresh_openapi_snapshot.py   # (dev) regenera contracts/pev-openapi.json desde el .yaml
python3 -m great_sdd.conformance.collection generate
python3 -m great_sdd.conformance.collection generate --check   # exit 0
python3 -m great_sdd.conformance.collection export --out /tmp/api.zip
python3 -m pytest tests/ -q
# Manual: importar postman_collection.json en Postman (6 carpetas, 43 requests) y bruno/ en Bruno
```

## Archivos

| Archivo | Acción |
|---|---|
| `great_sdd/conformance/contracts/pev-openapi.json` | nuevo — snapshot JSON del contrato (committeado) |
| `great_sdd/conformance/contracts/REFRESH.md` | nuevo — cómo refrescar el snapshot |
| `scripts/refresh_openapi_snapshot.py` | nuevo — yaml→json (dev-only; PyYAML no es dep de runtime) |
| `great_sdd/conformance/openapi.py` | nuevo — loader, deref, synthesize_example, iter_operations, TAG_TO_VIEW |
| `great_sdd/conformance/collection.py` | modify — descriptor unificado, merge, folders por vista |
| `great_sdd/conformance/fixtures/endpoints/collections/*` | regenerados (43 ops, 6 carpetas), committeados |
| `tests/test_conformance.py` | + tests loader/synth/merge/folders/4xx |
| `great_sdd/conformance/README.md` | actualizar: cobertura full-API desde openapi + refresh |

## Divergencias / notas
- El snapshot JSON es un **mirror pinneado**; si el openapi externo cambia, se refresca con el script. Riesgo de drift documentado (igual que el resto de la capa).
- Endpoints LM-only o con conducta compleja **no** obtienen oracle acá — solo aparecen en la collection con su schema+ejemplo sintetizado; su conformance determinista es decisión del sub-proyecto 2.
- Synthesize usa valores fijos ilustrativos (no datos reales); el seed determinista de los oracles (sub-proyecto 2) es lo que da ejemplos "reales" por escenario.
