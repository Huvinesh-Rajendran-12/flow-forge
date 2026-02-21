"""Connector registry: maps service names to connector classes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Type

import httpx

from ..simulator.state import ExecutionTrace
from .base import BaseConnector

if TYPE_CHECKING:
    from ..config import Settings


# Built-in connector class registry — populated via @register decorator
_BUILTIN_REGISTRY: dict[str, Type[BaseConnector]] = {}

# Directory where agent-built custom connectors are persisted
# apps/backend/src/backend/connectors/registry.py -> parents[3] == apps/backend
CUSTOM_CONNECTOR_DIR = Path(__file__).resolve().parents[3] / "custom_connectors"


def register(cls: Type[BaseConnector]) -> Type[BaseConnector]:
    """Class decorator that registers a connector in the built-in registry."""
    _BUILTIN_REGISTRY[cls.service_name] = cls
    return cls


class ConnectorRegistry:
    """Discovers and instantiates connectors for a workflow execution."""

    def __init__(
        self,
        settings: Settings,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._settings = settings
        self._trace = trace
        self._http = http_client
        # Cache instances keyed by service name for the lifetime of this registry
        self._cache: dict[str, BaseConnector] = {}

    def get(self, service_name: str) -> BaseConnector | None:
        """Return a live connector instance, or None if unavailable."""
        if service_name in self._cache:
            return self._cache[service_name]

        # 1. Try built-in registered connectors
        cls = _BUILTIN_REGISTRY.get(service_name)
        if cls is not None:
            instance = cls.from_settings(self._settings, self._trace, self._http)
            self._cache[service_name] = instance
            return instance

        # 2. Try dynamically-loaded custom connector (agent-built)
        custom_path = CUSTOM_CONNECTOR_DIR / f"{service_name}.py"
        if custom_path.exists():
            cls = _load_custom_connector(custom_path, service_name)
            if cls is not None:
                instance = cls.from_settings(self._settings, self._trace, self._http)
                self._cache[service_name] = instance
                return instance

        return None

    def invalidate(self, service_name: str) -> None:
        """Remove a cached connector instance so it will be reloaded on next get()."""
        self._cache.pop(service_name, None)

    def list_available(self) -> list[str]:
        """Return service names for all registered connectors (built-in + custom)."""
        built_in = set(_BUILTIN_REGISTRY.keys())
        custom: set[str] = set()
        if CUSTOM_CONNECTOR_DIR.exists():
            custom = {p.stem for p in CUSTOM_CONNECTOR_DIR.glob("*.py")}
        return sorted(built_in | custom)


def _load_custom_connector(
    path: Path, service_name: str
) -> Type[BaseConnector] | None:
    """Dynamically import a custom connector file and return its connector class.

    Convention: the class must be named {service_name.capitalize()}Connector
    e.g. service_name="zendesk" → class ZendeskConnector
    """
    module_name = f"_flowforge_custom_connector_{service_name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception:
        return None

    class_name = f"{service_name.capitalize()}Connector"
    return getattr(module, class_name, None)
