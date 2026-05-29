"""
GREAT SDD Kit — Signature-Driven Module Base.

Bridges the gap between Signatures (input/output contracts) and Modules
(implementation). Each SignatureModule:
  1. Declares which Signature it satisfies
  2. Validates inputs against the Signature before calling forward_impl
  3. Validates outputs against the Signature after forward_impl
  4. Provides introspection: what signature, what inputs, what outputs

This is what makes the specs *executable*: the signature IS the contract
that the module must honor. If you change the signature, the module must
adapt — the tests will catch it.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, get_type_hints

from great_sdd.modules.base import Module, LMClient
from great_sdd.signatures.pre_estimation import Signature, Field

logger = logging.getLogger(__name__)


class SignatureContractError(Exception):
    """Raised when a module violates its Signature contract."""
    pass


class SignatureModule(Module):
    """
    Base class for modules that honor a Signature contract.

    Subclasses MUST set `signature` (a Signature instance) and implement
    `forward_impl(**kwargs) -> dict`.

    The `forward()` method handles contract validation automatically:
      - Checks all required inputs are present
      - Calls forward_impl
      - Checks all declared outputs are present in the result
      - Coerces output types (boolean, string, json)

    Usage:
        class MyModule(SignatureModule):
            signature = VALIDATE_LINE_SELECTION

            def forward_impl(self, lines_json: str) -> dict:
                # actual implementation
                return {"is_compatible": True, "incompatibility_reason": ""}
    """

    # Subclasses MUST override this
    signature: Signature = None  # type: ignore[assignment]

    def forward(self, **kwargs) -> dict:
        """
        Validate inputs → call forward_impl → validate outputs.

        All kwargs are validated against the signature's input fields.
        The result is validated against the signature's output fields.
        """
        if self.signature is None:
            raise SignatureContractError(
                f"{self.__class__.__name__} must declare a `signature` attribute"
            )

        # ── Input validation ──
        self._validate_inputs(kwargs)

        # ── Call implementation ──
        result = self.forward_impl(**kwargs)

        # ── Output validation ──
        self._validate_outputs(result)

        return result

    def forward_impl(self, **kwargs) -> dict:
        """Override this in subclasses with the actual logic.

        IMPORTANT: Subclasses should declare explicit keyword arguments
        matching their Signature's input fields, e.g.:
            def forward_impl(self, lines_json: str) -> dict:
        This enables the Signature contract to be validated at runtime.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement forward_impl()"
        )

    # ── Validation internals ──

    def _validate_inputs(self, kwargs: dict) -> None:
        """Check that all required signature inputs are present."""
        required = {f.name for f in self.signature.inputs if not f.optional}
        provided = set(kwargs.keys())

        missing = required - provided
        if missing:
            raise SignatureContractError(
                f"{self.__class__.__name__}: missing required inputs: {missing}. "
                f"Signature '{self.signature.name}' expects: {required}"
            )

    def _validate_outputs(self, result: dict) -> None:
        """Check that all declared output fields are present and correctly typed."""
        if not isinstance(result, dict):
            raise SignatureContractError(
                f"{self.__class__.__name__}: forward() must return a dict, "
                f"got {type(result).__name__}"
            )

        for field in self.signature.outputs:
            if field.name not in result:
                raise SignatureContractError(
                    f"{self.__class__.__name__}: missing output '{field.name}'. "
                    f"Signature '{self.signature.name}' declares outputs: "
                    f"{[f.name for f in self.signature.outputs]}"
                )

            # Type coercion / validation
            result[field.name] = self._coerce(result[field.name], field.field_type, field.name)

    def _coerce(self, value: Any, field_type: str, field_name: str) -> Any:
        """Coerce a value to the type declared in the signature."""
        if value is None:
            return value

        try:
            if field_type == "boolean":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.strip().lower() in ("true", "1", "yes")
                return bool(value)
            elif field_type == "string":
                return str(value)
            elif field_type == "json":
                import json as _json
                if isinstance(value, str):
                    try:
                        return _json.loads(value)
                    except (_json.JSONDecodeError, TypeError):
                        return value
                return value
            else:
                return value
        except (ValueError, TypeError) as e:
            logger.warning(
                "Type coercion failed for %s.%s (expected %s): %s",
                self.signature.name, field_name, field_type, e,
            )
            return value

    def describe(self) -> str:
        """Human-readable description of this module's contract."""
        sig = self.signature
        inputs = ", ".join(f"{f.name}: {f.field_type}" for f in sig.inputs)
        outputs = ", ".join(f"{f.name}: {f.field_type}" for f in sig.outputs)
        return f"{self.__class__.__name__}({sig.name}): [{inputs}] → [{outputs}]"
