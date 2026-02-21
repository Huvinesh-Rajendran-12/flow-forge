"""GitHub REST API connector."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ..simulator.services import ServiceError
from ..simulator.state import ExecutionTrace
from .base import BaseConnector
from .registry import register

if TYPE_CHECKING:
    from ..config import Settings

_GH_API = "https://api.github.com"
_GH_ACCEPT = "application/vnd.github+json"
_GH_API_VERSION = "2022-11-28"


@register
class GithubConnector(BaseConnector):
    """Real GitHub connector using the GitHub REST API.

    Required settings: GITHUB_TOKEN, GITHUB_ORG
    Token needs: admin:org, repo scopes (or a GitHub App installation token)
    """

    service_name = "github"

    def __init__(
        self,
        token: str,
        default_org: str,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(trace, http_client)
        self._default_org = default_org
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": _GH_ACCEPT,
            "X-GitHub-Api-Version": _GH_API_VERSION,
        }

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> GithubConnector:
        return cls(
            settings.github_token or "",
            settings.github_org or "",
            trace,
            http_client,
        )

    @classmethod
    def is_configured(cls, settings: Settings) -> bool:
        return bool(settings.github_token and settings.github_org)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def add_to_org(self, node_id: str, **params) -> dict:
        """Add a user to the GitHub organization."""
        username = params.get("username", "")
        org = params.get("org", self._default_org)
        resp = await self.http.put(
            f"{_GH_API}/orgs/{org}/memberships/{username}",
            headers=self._headers,
            json={"role": "member"},
        )
        if resp.status_code == 403:
            raise ServiceError("Insufficient GitHub org permissions", "permission_denied")
        if resp.status_code == 404:
            raise ServiceError(f"GitHub org '{org}' or user '{username}' not found", "not_found")
        if resp.status_code not in (200, 201):
            raise ServiceError(
                f"GitHub add_to_org failed ({resp.status_code}): {resp.text[:200]}",
                "connector_error",
            )
        result = {"username": username, "org": org, "status": "added"}
        self._log(node_id, "add_to_org", params, result)
        return result

    async def grant_repo_access(self, node_id: str, **params) -> dict:
        """Grant a user access to a repository."""
        username = params.get("username", "")
        repo = params.get("repo", "")
        # GitHub API uses "pull"/"push"/"admin" — map simulator "read"→"pull", "write"→"push"
        raw_permission = params.get("permission", "read")
        permission = {"read": "pull", "write": "push"}.get(raw_permission, raw_permission)
        org = self._default_org

        resp = await self.http.put(
            f"{_GH_API}/repos/{org}/{repo}/collaborators/{username}",
            headers=self._headers,
            json={"permission": permission},
        )
        if resp.status_code == 403:
            raise ServiceError("Insufficient GitHub repo permissions", "permission_denied")
        if resp.status_code == 404:
            raise ServiceError(
                f"GitHub repo '{org}/{repo}' or user '{username}' not found", "not_found"
            )
        # 201 = invitation sent, 204 = already a collaborator
        if resp.status_code not in (200, 201, 204):
            raise ServiceError(
                f"GitHub grant_repo_access failed ({resp.status_code}): {resp.text[:200]}",
                "connector_error",
            )
        result = {"username": username, "repo": repo, "permission": raw_permission, "status": "granted"}
        self._log(node_id, "grant_repo_access", params, result)
        return result
