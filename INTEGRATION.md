# SDD Kit — Integración en proyectos

El SDD Kit no es el repo raíz del desarrollador. Es una **dependencia que el agente carga** cuando trabaja en cualquier proyecto que use las reglas de negocio del GREAT System.

## Instalación como dependencia npm

```bash
# En la raíz del proyecto (frontend o backend):
npm install git+https://github.com/nujovich/great-sdd-kit.git
```

Esto descarga el SDD Kit en `node_modules/great-sdd-kit/`.

### Pinchar una versión específica

```bash
npm install git+https://github.com/nujovich/great-sdd-kit.git#v1.0.0
```

### Actualizar a la última versión

```bash
npm update great-sdd-kit
```

## Configurar los agentes de IA

Cada proyecto necesita sus propios archivos de entry point que apunten al SDD Kit. Copia estos templates:

### CLAUDE.md (raíz del proyecto)

```markdown
# [Nombre del Proyecto]

Lee `node_modules/great-sdd-kit/AGENTS.md` antes de generar cualquier código. Este proyecto usa Specification-Driven Development: las reglas de negocio están en `node_modules/great-sdd-kit/great_sdd/specs/` como datos verificables (78 reglas en 6 vistas).

Siempre corre `pytest node_modules/great-sdd-kit/tests/ -v` después de generar código para validar que cumple las reglas.

Referencia rápida del SDD Kit:
- `node_modules/great-sdd-kit/great_sdd/specs/` → 78 reglas de negocio
- `node_modules/great-sdd-kit/great_sdd/modules/` → 30 módulos Python puros
- `node_modules/great-sdd-kit/great_sdd/pipeline/` → 6 pipelines (blueprint para endpoints)
- `node_modules/great-sdd-kit/tests/` → 257 tests que verifican las reglas
```

### .cursorrules (raíz del proyecto)

```
Carga node_modules/great-sdd-kit/AGENTS.md antes de generar codigo. Las reglas de negocio estan en node_modules/great-sdd-kit/great_sdd/specs/ (78 reglas, 6 vistas).

Siempre corre pytest node_modules/great-sdd-kit/tests/ -v para validar que cumples las reglas.
```

### .github/copilot-instructions.md (raíz del proyecto)

```markdown
Before generating code, load node_modules/great-sdd-kit/AGENTS.md. Business rules are in node_modules/great-sdd-kit/great_sdd/specs/.
Always run pytest node_modules/great-sdd-kit/tests/ -v to validate compliance.
```

### AGENTS.md (raíz del proyecto, opcional pero recomendado)

```markdown
# AGENTS.md — [Nombre del Proyecto]

Eres un agente de IA generando código para este proyecto.

## Antes de generar cualquier código

1. Lee `node_modules/great-sdd-kit/AGENTS.md` — contiene las reglas de negocio.
2. Lee las specs relevantes en `node_modules/great-sdd-kit/great_sdd/specs/`.

## Tests

Después de generar código que implemente reglas de negocio:
pytest node_modules/great-sdd-kit/tests/ -v
```

## Estructura resultante

```plaintext
tu-proyecto/
├── src/                                    ← Código del proyecto
├── tests/                                  ← Tests del proyecto
├── node_modules/
│   └── great-sdd-kit/                      ← Dependencia npm (no submodule)
│       ├── AGENTS.md
│       ├── great_sdd/specs/               ← 78 reglas de negocio
│       ├── great_sdd/modules/             ← 30 módulos
│       ├── great_sdd/pipeline/            ← 6 pipelines
│       └── tests/                          ← 257 tests
├── CLAUDE.md                               ← Apunta a node_modules/great-sdd-kit/
├── .cursorrules                            ← Apunta a node_modules/great-sdd-kit/
└── package.json                            ← "great-sdd-kit": "git+https://..."
```

## Cómo usar los módulos desde el backend (Python)

Para que Python pueda importar los módulos del SDD Kit, agregá el path:

```python
import sys
sys.path.insert(0, "node_modules/great-sdd-kit")

from great_sdd.modules.pre_estimation import SaveValidator

validator = SaveValidator()
result = validator.forward(line, "draft")
if not result["can_save"]:
    return {"status": 422, "errors": result["validation_errors"]}
```

O instalalo como paquete editable:

```bash
pip install -e node_modules/great-sdd-kit/
```

## Cómo usar los módulos desde el frontend (TypeScript/React)

El frontend no importa los módulos Python directamente. En su lugar:

1. **Las reglas de negocio** se consumen como datos (specs son Python dicts/JSON-serializables)
2. **Los endpoints del backend** implementan la lógica usando los módulos
3. **El frontend** llama a los endpoints y muestra los resultados

Si necesitás las reglas como datos en el frontend, podés exportarlas como JSON:

```bash
# Desde el repo del SDD Kit, generar JSON de specs
python3 -c "from great_sdd.specs.pre_estimation_specs import *; import json; print(json.dumps(SPECS, indent=2))" > specs.json
```

## Actualizar el SDD Kit

Cuando las reglas de negocio cambien (nuevo spec en el kit):

```bash
npm update great-sdd-kit
pytest node_modules/great-sdd-kit/tests/ -q
```

Si algún test falla, es porque una regla cambió o se añadió una nueva. Editá los módulos afectados hasta que todo pase.

## Para crear un SDD Kit para otro dominio

Si quieres aplicar este patrón a otro sistema (no GREAT):

1. Clona este repo como template
2. Borra `great_sdd/`
3. Crea `tu_dominio/specs/` con tus reglas
4. Crea `tu_dominio/modules/` con tu lógica
5. Crea `tu_dominio/pipeline/` con tu orquestación
6. Actualiza `AGENTS.md` con tu dominio
7. Publica en GitHub y los proyectos consumidores hacen `npm install git+https://<tu-repo>.git`
