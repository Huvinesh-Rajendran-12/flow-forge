"""Jira Cloud REST API v3 connector."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import httpx

from ..simulator.services import ServiceError
from ..simulator.state import ExecutionTrace
from .base import BaseConnector
from .registry import register

if TYPE_CHECKING:
    from ..config import Settings


@register
class JiraConnector(BaseConnector):
    """Real Jira connector using the Jira Cloud REST API v3.

    Required settings: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN
    Optional: JIRA_PROJECT_KEY (defaults to "ONBOARD")
    """

    service_name = "jira"

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project_key: str,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(trace, http_client)
        self._base = base_url.rstrip("/")
        self._project_key = project_key
        creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> JiraConnector:
        return cls(
            settings.jira_base_url or "",
            settings.jira_email or "",
            settings.jira_api_token or "",
            settings.jira_project_key or "ONBOARD",
            trace,
            http_client,
        )

    @classmethod
    def is_configured(cls, settings: Settings) -> bool:
        return bool(settings.jira_base_url and settings.jira_email and settings.jira_api_token)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def create_issue(self, node_id: str, **params) -> dict:
        """Create a Jira issue."""
        issue_type = params.get("issue_type", "Task")
        payload: dict = {
            "fields": {
                "project": {"key": self._project_key},
                "summary": params.get("summary", ""),
                "issuetype": {"name": issue_type},
            }
        }
        if params.get("assignee"):
            # Jira Cloud v3 uses accountId for assignee
            payload["fields"]["assignee"] = {"accountId": params["assignee"]}

        resp = await self.http.post(
            f"{self._base}/rest/api/3/issue",
            headers=self._headers,
            json=payload,
        )
        self._check_error(resp)
        issue_key = resp.json()["key"]
        result = {"issue_key": issue_key, "summary": params.get("summary", ""), "status": "created"}
        self._log(node_id, "create_issue", params, result)
        return result

    async def create_epic(self, node_id: str, **params) -> dict:
        """Create a Jira epic (delegates to create_issue with issue_type=Epic)."""
        params = dict(params)
        params["issue_type"] = "Epic"
        return await self.create_issue(node_id, **params)

    async def assign_issue(self, node_id: str, **params) -> dict:
        """Assign a Jira issue to a user."""
        issue_key = params.get("issue_key", "")
        assignee_account_id = params.get("assignee", "")
        resp = await self.http.put(
            f"{self._base}/rest/api/3/issue/{issue_key}/assignee",
            headers=self._headers,
            json={"accountId": assignee_account_id},
        )
        # 204 = success, no body
        if resp.status_code not in (200, 204):
            self._check_error(resp)
        result = {"issue_key": issue_key, "assignee": assignee_account_id, "status": "assigned"}
        self._log(node_id, "assign_issue", params, result)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_error(self, resp: httpx.Response) -> None:
        if resp.status_code in (200, 201, 204):
            return
        if resp.status_code == 401:
            raise ServiceError("Jira authentication failed — check JIRA_EMAIL and JIRA_API_TOKEN", "auth_error")
        if resp.status_code == 403:
            raise ServiceError("Jira permission denied", "permission_denied")
        if resp.status_code == 404:
            raise ServiceError("Jira resource not found", "not_found")
        body = resp.text[:300]
        raise ServiceError(f"Jira API error {resp.status_code}: {body}", "connector_error")
