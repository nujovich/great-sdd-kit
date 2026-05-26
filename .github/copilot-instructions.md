Before generating any code, load AGENTS.md. This project uses Specification-Driven Development: business rules are executable code in great_dspy/specs/.

Always run `pytest tests/ -v` after generating code to validate it complies with the 74 business rules.

Key directories:
- great_dspy/specs/ → business rules as data (6 files, 74 rules)
- great_dspy/modules/ → pure Python business logic (30 modules)
- great_dspy/pipeline/ → endpoint blueprints (6 pipelines)
- tests/ → 216 tests verifying the rules