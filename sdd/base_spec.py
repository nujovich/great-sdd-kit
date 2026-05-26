"""
SDD Kit — Base Spec Registry.

Base classes for defining specification-driven development registries.
Any domain (GREAT, or any other system) extends these.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SpecRegistry:
    """
    Base class for a specification registry.

    A registry is a collection of business rules, state machines,
    and permission matrices encoded as data — not as prompts or docs.

    Usage:
        class MySystemSpecs(SpecRegistry):
            RULES = [...]
            STATE_MACHINE = {...}
    """

    @classmethod
    def get_rule(cls, rule_id: str) -> Optional[dict]:
        """Find a rule by its ID."""
        rules = getattr(cls, "BUSINESS_RULES", [])
        for r in rules:
            if r.get("id") == rule_id:
                return r
        return None

    @classmethod
    def get_rules_by_tag(cls, tag: str) -> list[dict]:
        """Filter rules by a tag or keyword."""
        rules = getattr(cls, "BUSINESS_RULES", [])
        return [r for r in rules if tag.lower() in r.get("rule", "").lower()]

    @classmethod
    def rule_count(cls) -> int:
        return len(getattr(cls, "BUSINESS_RULES", []))


class SpecEnum(Enum):
    """Base enum for spec values (statuses, roles, etc.)."""

    @classmethod
    def list_values(cls) -> list[str]:
        return [e.value for e in cls]

    @classmethod
    def list_names(cls) -> list[str]:
        return [e.name for e in cls]


def validate_transition(
    transition_map: dict[Enum, list[Enum]],
    current: Enum,
    target: Enum,
) -> tuple[bool, str]:
    """
    Validate a state machine transition.

    Args:
        transition_map: {FromStatus: [ToStatus1, ToStatus2, ...]}
        current: Current state
        target: Desired next state

    Returns:
        (is_valid, error_message)
    """
    allowed = transition_map.get(current, [])
    if target not in allowed:
        return (
            False,
            f"Cannot transition from '{current.value}' to '{target.value}'"
        )
    if not allowed:
        return (
            False,
            f"'{current.value}' is a terminal state. No transitions allowed."
        )
    return True, ""


def check_permission(
    permission_map: dict[Enum, Any],
    role: Enum,
    action: str,
    role_attr_map: Optional[dict[str, str]] = None,
) -> tuple[bool, str]:
    """
    Generic permission checker.

    Args:
        permission_map: {Role: PermissionDataclass}
        role: The role to check
        action: 'view', 'edit', 'send', etc.
        role_attr_map: Maps action names to permission attributes

    Returns:
        (allowed, reason)
    """
    if role_attr_map is None:
        role_attr_map = {
            "view": "can_view",
            "edit": "can_edit",
            "save": "can_save",
            "send": "can_send_to_hvt",
            "export": "can_export_csv",
        }

    perm = permission_map.get(role)
    if not perm:
        return False, f"No permissions defined for {role.name}"

    attr = role_attr_map.get(action)
    if attr and not getattr(perm, attr, False):
        return False, f"{role.name} cannot {action}"

    return True, f"{role.name} can {action}"