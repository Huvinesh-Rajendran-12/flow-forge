"""Failure injection configuration for simulated services."""

import random

from pydantic import BaseModel


class FailureRule(BaseModel):
    """Defines how a specific service action should fail."""

    error_type: str  # "rate_limit" | "already_exists" | "permission_denied"
    message: str
    probability: float = 1.0  # 1.0 = always fail, 0.5 = 50% chance


class FailureConfig(BaseModel):
    """Maps service.action keys to failure rules."""

    rules: dict[str, FailureRule] = {}

    def should_fail(self, service: str, action: str) -> FailureRule | None:
        """Check if a service action should fail. Returns the rule if it triggers."""
        key = f"{service}.{action}"
        rule = self.rules.get(key)
        if rule is None:
            return None
        if random.random() <= rule.probability:
            return rule
        return None
