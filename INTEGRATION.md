# SDD Kit — Integración en proyectos

El SDD Kit no es el repo raíz del desarrollador. Es una **dependencia que el agente carga** cuando trabaja en `great-backend` o `great-frontend`.

## Opción recomendada: Git Submodule

```bash
# En el repo del backend o frontend:
cd tu-proyecto
git submodule add https://github.com/nujovich/great-dspy-pipeline.git sdd-kit
git commit -m "feat: add SDD Kit as submodule"
```

Esto crea un directorio `sdd-kit/` en tu proyecto con todas las reglas de negocio.

## Configurar los agentes

Cada proyecto necesita sus propios archivos de entry point que apunten al SDD Kit. Copia estos templates:

### CLAUDE.md (raíz del proyecto)

```markdown
# [Nombre del Proyecto]

## SDD Kit

Este proyecto usa Specification-Driven Development. Las reglas de negocio están en `sdd-kit/`.

**SIEMPRE carga `sdd-kit/AGENTS.md` antes de generar cualquier código.**

Las reglas están en `sdd-kit/great_dspy/specs/` (78 reglas en 6 vistas).
La lógica está en `sdd-kit/great_dspy/modules/` (30 módulos Python puros).
Los pipelines están en `sdd-kit/great_dspy/pipeline/` (6 pipelines).
Los tests están en `sdd-kit/tests/` (216 tests).

Siempre corre `pytest sdd-kit/tests/ -v` después de generar código para validar que cumple las reglas.
```

### .cursorrules (raíz del proyecto)

```
Carga sdd-kit/AGENTS.md antes de generar codigo. Las reglas de negocio estan en sdd-kit/great_dspy/specs/.

Siempre corre pytest sdd-kit/tests/ -v para validar.
```

### .github/copilot-instructions.md (raíz del proyecto)

```markdown
Before generating code, load sdd-kit/AGENTS.md. Business rules are in sdd-kit/great_dspy/specs/.
Always run pytest sdd-kit/tests/ -v to validate compliance.
```

## Estructura resultante

```
tu-backend/
├── src/                    ← Código del backend
├── tests/                  ← Tests del backend
├── sdd-kit/                ← Git submodule del SDD Kit
│   ├── AGENTS.md
│   ├── great_dspy/specs/   ← 78 reglas de negocio
│   ├── great_dspy/modules/ ← 30 módulos
│   ├── great_dspy/pipeline/← 6 pipelines
│   └── tests/              ← 216 tests
├── CLAUDE.md               ← Apunta a sdd-kit/AGENTS.md
├── .cursorrules            ← Apunta a sdd-kit/AGENTS.md
└── .github/copilot-instructions.md ← Apunta a sdd-kit/AGENTS.md
```

## Cómo usar los módulos desde el backend

```python
# En tu backend (FastAPI, Django, etc.)
from sdd-kit.great_dspy.modules.pre_estimation import SaveValidator

@app.post("/api/pre-estimation/save-draft")
def save_draft(line: dict):
    validator = SaveValidator()
    result = validator.forward(line, "draft")
    if not result["can_save"]:
        return {"status": 422, "errors": result["validation_errors"]}
    # ... persistir en DB
```

Para que Python pueda importar desde `sdd-kit/`, añade al PATH o instálalo como paquete editable:

```bash
pip install -e sdd-kit/
```

## Opción alternativa: Copy (sin submodule)

Si no quieres submodules, copia estos directorios mínimos:

```bash
cp -r sdd-kit/great_dspy/specs/ tu-proyecto/sdd-specs/
cp -r sdd-kit/sdd/ tu-proyecto/sdd/
```

Y en tu `AGENTS.md` / `CLAUDE.md` apunta a `sdd-specs/` en lugar de `sdd-kit/`.

## Actualizar el SDD Kit

Cuando las reglas de negocio cambien (nuevo spec en el kit):

```bash
cd tu-proyecto
git submodule update --remote sdd-kit
git commit -m "chore: update SDD Kit to latest specs"
```

El agente, la próxima vez que cargue el proyecto, ya tendrá las nuevas reglas.

## Para crear un SDD Kit para otro dominio

Si quieres aplicar este patrón a otro sistema (no GREAT):

1. Clona este repo como template
2. Borra `great_dspy/`
3. Crea `tu_dominio/specs/` con tus reglas
4. Crea `tu_dominio/modules/` con tu lógica
5. Crea `tu_dominio/pipeline/` con tu orquestación
6. Actualiza `AGENTS.md` con tu dominio
7. Los proyectos que consuman este kit hacen `git submodule add <tu-repo> sdd-kit`