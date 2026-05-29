# Versioning — GREAT SDD Kit

Este proyecto usa [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

Formato: `MAJOR.MINOR.PATCH` (ej: `1.0.0`)

---

## Las dos APIs del SDD Kit

Es fundamental entender que el SDD Kit tiene **dos APIs distintas** con impacto de versionado diferente:

### 1. API pública de módulos (lo que un backend importa y llama)

```python
from great_sdd.modules.pre_estimation import StatusTransitionValidator

v = StatusTransitionValidator()
result = v.forward(current_status="draft", target_status="estimated", has_saved_draft_in_session=True)
# result = {"is_valid": True, "error_message": ""}
```

Si cambiás **cualquiera de estas cosas**, el backend que importa el kit **se rompe**:

- Nombre de la clase o función exportada
- Parámetros de entrada de `forward()` (obligatorios o sus nombres)
- Keys del diccionario de retorno
- Comportamiento de una regla (de `True` a `False` para el mismo input)

→ Esto es siempre un bump **MAJOR**.

### 2. Pipeline (blueprint — guía de orquestación)

Los pipelines documentan **qué pasos y en qué orden** se recomienda orquestar los módulos:

```
Pre-Estimation pipeline:
  1. SelectionValidator → 2. PermissionChecker → 3. InductorSelector
  4. EstimationCalculator → 5. SaveValidator → 6. MonthDistributor → 7. SummaryGenerator
```

El backend **no importa el pipeline**. El pipeline es documentación/guía, que cada backend implementa a su manera (API endpoints, Celery tasks, scripts, etc.).

Cambiar el pipeline es un bump **minor** o **patch** — no rompe ningún consumer.

---

## Cuándo es cada bump

### MAJOR (X.0.0)

Rompe la API pública de módulos. Un backend que actualiza **sin cambiar su código** deja de funcionar.

Ejemplos concretos:
- Cambiar la firma de `forward()` de un módulo
- Renombrar una clase o función exportada
- Cambiar las keys del dict de retorno
- Eliminar un módulo que backends importan
- Cambiar la estructura de specs (dict → dataclass)
- Cambiar el comportamiento de una regla (el mismo input da resultado opuesto)

### MINOR (0.X.0)

Agrega funcionalidad nueva sin romper lo existente. Un backend que actualiza **sigue funcionando igual** y puede optar por usar lo nuevo.

Ejemplos concretos:
- Nuevo módulo (nadie lo importa hasta que quiere)
- Nueva regla de negocio en specs
- Nuevo pipeline
- Nuevo test para una regla nueva
- Nuevo parámetro opcional en `forward()` (con default)
- Agregar una etapa al pipeline

### PATCH (0.0.1)

Fix o mejora interna. No cambia la API pública ni agrega funcionalidad.

Ejemplos concretos:
- Fix en fórmula de cálculo (misma API, resultado correcto)
- Fix en test que estaba mal
- Fix en validación de una regla (corrige comportamiento incorrecto)
- Mejorar docstrings
- Refactor interno sin cambiar API
- Cambiar orden del pipeline (es documentación, no código importable)

---

## Regla de oro

**Pregunta:** ¿Un backend que usa este kit se rompe si actualiza sin cambiar su código?

| Respuesta | Bump |
|---|---|
| No se rompe — funciona igual | **patch** |
| No se rompe — pero hay funcionalidad nueva disponible | **minor** |
| Sí se rompe — hay que cambiar código del backend | **major** |

---

## Regla práctica para el SDD Kit

```
¿Agregás algo nuevo?
  └─ Sí → MINOR
  └─ No → ¿Arreglás algo roto?
            └─ Sí → PATCH
            └─ No → ¿Cambiás la API pública?
                      └─ Sí → MAJOR
                      └─ No → PATCH
```

---

## Cómo hacer un bump

```bash
# Desde la raíz del repo
python3 scripts/bump_version.py patch   # 1.0.0 → 1.0.1
python3 scripts/bump_version.py minor   # 1.0.0 → 1.1.0
python3 scripts/bump_version.py major   # 1.0.0 → 2.0.0
```

El script actualiza automáticamente:
- `great_sdd/__init__.py` → `__version__`
- `pyproject.toml` → `version`
- Git commit + tag (`v1.0.0`, `v1.1.0`, etc.)

Luego:
```bash
git push && git push --tags
```

---

## Dónde se registra cada cambio

- **CHANGELOG.md** — registro histórico de cada versión
- **Git tags** — `v1.0.0`, `v1.1.0`, etc. en GitHub
- **`great_sdd/__version__`** — accesible en runtime para backends

```python
from great_sdd import __version__
print(f"Using GREAT SDD Kit v{__version__}")
```
