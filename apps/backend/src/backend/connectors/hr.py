"""HR system connector — generic configurable REST webhook."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ..simulator.services import ServiceError
from ..simulator.state import ExecutionTrace
from .base import BaseConnector
from .registry import register

if TYPE_CHECKING:
    from ..config import Settings


@register
class HrConnector(BaseConnector):
    """Real HR connector that calls a configurable internal REST API.

    Required settings:
        HR_BASE_URL — base URL of your HR system API (e.g. https://hr.internal/api)
        HR_API_KEY  — Bearer token for authentication

    Expected endpoints (adapt to your HR system's actual shape):
        POST {HR_BASE_URL}/employees           → create_employee
        POST {HR_BASE_URL}/benefits/enroll     → enroll_benefits

    Each endpoint should return JSON with at least an "id" field.
    """

    service_name = "hr"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(trace, http_client)
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> HrConnector:
        return cls(
            settings.hr_base_url or "",
            settings.hr_api_key or "",
            trace,
            http_client,
        )

    @classmethod
    def is_configured(cls, settings: Settings) -> bool:
        return bool(settings.hr_base_url and settings.hr_api_key)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def create_employee(self, node_id: str, **params) -> dict:
        """Create an HR record for a new employee."""
        payload = {
            "name": params.get("employee_name", ""),
            "role": params.get("role", ""),
            "department": params.get("department", ""),
        }
        resp = await self.http.post(
            f"{self._base}/employees",
            headers=self._headers,
            json=payload,
        )
        self._check_error(resp, "create_employee")
        body = resp.json()
        employee_id = body.get("id") or body.get("employee_id", "")
        result = {
            "employee_id": str(employee_id),
            "name": params.get("employee_name", ""),
            "status": "created",
        }
        self._log(node_id, "create_employee", params, result)
        return result

    async def enroll_benefits(self, node_id: str, **params) -> dict:
        """Enroll an employee in a benefits plan."""
        payload = {
            "employee_id": params.get("employee_id", ""),
            "plan": params.get("plan", "standard"),
        }
        resp = await self.http.post(
            f"{self._base}/benefits/enroll",
            headers=self._headers,
            json=payload,
        )
        self._check_error(resp, "enroll_benefits")
        result = {
            "employee_id": params.get("employee_id", ""),
            "plan": params.get("plan", "standard"),
            "status": "enrolled",
        }
        self._log(node_id, "enroll_benefits", params, result)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_error(self, resp: httpx.Response, action: str) -> None:
        if resp.status_code in (200, 201, 204):
            return
        if resp.status_code == 401:
            raise ServiceError("HR API authentication failed — check HR_API_KEY", "auth_error")
        if resp.status_code == 403:
            raise ServiceError("HR API permission denied", "permission_denied")
        if resp.status_code == 404:
            raise ServiceError("HR API endpoint not found — check HR_BASE_URL", "not_found")
        if resp.status_code == 409:
            raise ServiceError("HR record already exists", "already_exists")
        body = resp.text[:300]
        raise ServiceError(
            f"HR {action} failed ({resp.status_code}): {body}", "connector_error"
        )
