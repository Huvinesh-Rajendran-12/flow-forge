"""Connector package: real API connectors with transparent simulator fallback.

Usage:
    from backend.connectors import create_service_layer
    state, trace, services, failure_config = create_service_layer(settings)

    # services dict is passed directly to WorkflowExecutor — same interface as create_simulator().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ..simulator import create_simulator
from ..simulator.failures import FailureConfig
from ..simulator.state import ExecutionTrace, SimulatorState
from .registry import ConnectorRegistry

if TYPE_CHECKING:
    from ..config import Settings

# Import all built-in connectors to trigger @register decoration
from . import github, google, hr, jira, slack  # noqa: E402, F401


def create_service_layer(
    settings: Settings,
    failure_config: FailureConfig | None = None,
) -> tuple[SimulatorState, ExecutionTrace, dict, FailureConfig | None]:
    """Create a service dict with hybrid real+simulator routing.

    Modes (controlled by settings.connector_mode):
      "simulator"  — always returns the in-memory simulator services (default)
      "hybrid"     — uses a real connector per service when credentials are set,
                     falls back to the simulator service otherwise
      "real"       — same as hybrid; callers can inspect returned services to
                     verify all are real connectors

    The return signature is identical to create_simulator() so pipeline.py
    needs only a one-line import change.
    """
    state, trace, sim_services, _ = create_simulator()

    if settings.connector_mode == "simulator":
        return state, trace, sim_services, failure_config

    http_client = httpx.AsyncClient(timeout=30.0)
    registry = ConnectorRegistry(settings, trace, http_client)

    services: dict = {}
    for name, sim_svc in sim_services.items():
        connector = registry.get(name)
        if connector is not None and connector.is_configured(settings):
            services[name] = connector
        else:
            services[name] = sim_svc  # transparent per-service fallback

    return state, trace, services, failure_config
