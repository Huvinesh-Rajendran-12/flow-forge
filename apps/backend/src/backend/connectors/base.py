"""Base interface for all real service connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

from ..simulator.services import ServiceError
from ..simulator.state import ExecutionTrace, TraceStep

if TYPE_CHECKING:
    from ..config import Settings


class BaseConnector(ABC):
    """Abstract base for all real service connectors.

    Interface contract (preserved by all connectors, including agent-generated ones):

        async def action_name(self, node_id: str, **params) -> dict: ...

    The executor detects async vs sync methods via inspect.iscoroutinefunction and
    dispatches accordingly, so sync implementations are also valid.
    """

    service_name: str = ""

    def __init__(self, trace: ExecutionTrace, http_client: httpx.AsyncClient) -> None:
        self.trace = trace
        self.http = http_client

    def _log(self, node_id: str, action: str, params: dict, result: dict) -> None:
        """Append a success trace step — identical signature to BaseService._log."""
        self.trace.steps.append(
            TraceStep(
                node_id=node_id,
                service=self.service_name,
                action=action,
                parameters=params,
                result=result,
                status="success",
            )
        )

    def _fail(self, message: str, error_type: str = "connector_error") -> None:
        """Raise a ServiceError — convenience wrapper so connectors don't import it directly."""
        raise ServiceError(message, error_type)

    @classmethod
    @abstractmethod
    def from_settings(
        cls,
        settings: Settings,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> BaseConnector:
        """Construct this connector from application Settings."""
        ...

    @classmethod
    @abstractmethod
    def is_configured(cls, settings: Settings) -> bool:
        """Return True if all required credentials are present in settings."""
        ...
