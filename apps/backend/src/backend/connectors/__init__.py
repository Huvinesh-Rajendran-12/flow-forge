"""Connector package: real API connectors with transparent simulator fallback.

Usage:
    from backend.connectors import create_service_layer, close_service_layer

    state, trace, services, failure_config = create_service_layer(settings)
    try:
        ...
    finally:
        await close_service_layer(services)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from ..simulator import create_simulator
from ..simulator.failures import FailureConfig
from ..simulator.state import ExecutionTrace, SimulatorState
from .base import BaseConnector
from .registry import ConnectorRegistry

if TYPE_CHECKING:
    from ..config import Settings

# Import all built-in connectors to trigger @register decoration
from . import github, google, hr, jira, slack  # noqa: E402, F401


def create_service_layer(
    settings: Settings,
    failure_config: FailureConfig | None = None,
) -> tuple[SimulatorState, ExecutionTrace, dict[str, Any], FailureConfig | None]:
    """Create a service dict with hybrid real+simulator routing.

    Modes (controlled by settings.connector_mode):
      "simulator"  — always returns the in-memory simulator services (default)
      "hybrid"     — uses a real connector per service when credentials are set,
                     falls back to the simulator service otherwise
      "real"       — same as hybrid; callers can inspect returned services to
                     verify all are real connectors
    """
    state, trace, sim_services, _ = create_simulator()

    if settings.connector_mode == "simulator":
        return state, trace, sim_services, failure_config

    http_client = httpx.AsyncClient(timeout=30.0)
    registry = ConnectorRegistry(settings, trace, http_client)

    services: dict[str, Any] = {}
    service_names = set(sim_services.keys()) | set(registry.list_available())

    for name in sorted(service_names):
        connector = registry.get(name)
        sim_svc = sim_services.get(name)

        # Prefer a configured connector, and always expose connector-only services
        # (services that do not exist in the legacy simulator set).
        if connector is not None and (connector.is_configured(settings) or sim_svc is None):
            services[name] = connector
            continue

        if sim_svc is not None:
            services[name] = sim_svc

    # Stash the http_client so close_service_layer can always close it,
    # even when no connectors ended up in the service map.
    services["_http_client"] = http_client

    return state, trace, services, failure_config


async def close_service_layer(services: dict[str, Any]) -> None:
    """Close any connector AsyncClient instances attached to the service map."""
    clients: dict[int, httpx.AsyncClient] = {}

    # Always close the shared http_client created by create_service_layer.
    stashed = services.pop("_http_client", None)
    if isinstance(stashed, httpx.AsyncClient):
        clients[id(stashed)] = stashed

    for service in services.values():
        if isinstance(service, BaseConnector):
            clients[id(service.http)] = service.http

    for client in clients.values():
        await client.aclose()
