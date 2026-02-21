"""Slack Web API connector."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ..simulator.services import ServiceError
from ..simulator.state import ExecutionTrace
from .base import BaseConnector
from .registry import register

if TYPE_CHECKING:
    from ..config import Settings

_SLACK_API = "https://slack.com/api"


@register
class SlackConnector(BaseConnector):
    """Real Slack connector using the Slack Web API.

    Required settings: SLACK_BOT_TOKEN (xoxb-...)
    Scopes needed: channels:manage, chat:write, users:read, users:read.email
    """

    service_name = "slack"

    def __init__(
        self,
        bot_token: str,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(trace, http_client)
        self._headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json",
        }

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> SlackConnector:
        return cls(settings.slack_bot_token or "", trace, http_client)

    @classmethod
    def is_configured(cls, settings: Settings) -> bool:
        return bool(settings.slack_bot_token)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def create_channel(self, node_id: str, **params) -> dict:
        """Create a public Slack channel."""
        channel_name = params.get("channel_name", "").lstrip("#")
        resp = await self.http.post(
            f"{_SLACK_API}/conversations.create",
            headers=self._headers,
            json={"name": channel_name, "is_private": False},
        )
        data = resp.json()
        if not data.get("ok"):
            self._map_error(data.get("error", "unknown"))

        channel_id = data["channel"]["id"]
        result = {"channel": f"#{channel_name}", "channel_id": channel_id, "status": "created"}
        self._log(node_id, "create_channel", params, result)
        return result

    async def invite_user(self, node_id: str, **params) -> dict:
        """Invite a user (by email) to a Slack channel."""
        email = params.get("email", "")
        channel_name = params.get("channel_name", "").lstrip("#")

        # Step 1: resolve email → Slack user ID
        resp = await self.http.get(
            f"{_SLACK_API}/users.lookupByEmail",
            headers=self._headers,
            params={"email": email},
        )
        data = resp.json()
        if not data.get("ok"):
            raise ServiceError(
                f"No Slack user found for {email}: {data.get('error', 'unknown')}",
                "not_found",
            )
        user_id = data["user"]["id"]

        # Step 2: find channel ID by name
        channel_id = await self._find_channel_id(channel_name)

        # Step 3: invite user
        resp2 = await self.http.post(
            f"{_SLACK_API}/conversations.invite",
            headers=self._headers,
            json={"channel": channel_id, "users": user_id},
        )
        data2 = resp2.json()
        if not data2.get("ok") and data2.get("error") != "already_in_channel":
            self._map_error(data2.get("error", "unknown"))

        result = {"email": email, "channel": f"#{channel_name}", "status": "invited"}
        self._log(node_id, "invite_user", params, result)
        return result

    async def send_message(self, node_id: str, **params) -> dict:
        """Send a message to a Slack channel."""
        channel_name = params.get("channel_name", "").lstrip("#")
        message = params.get("message", "")
        resp = await self.http.post(
            f"{_SLACK_API}/chat.postMessage",
            headers=self._headers,
            json={"channel": f"#{channel_name}", "text": message},
        )
        data = resp.json()
        if not data.get("ok"):
            self._map_error(data.get("error", "unknown"))

        result = {"channel": f"#{channel_name}", "message": message, "status": "sent"}
        self._log(node_id, "send_message", params, result)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _find_channel_id(self, channel_name: str) -> str:
        """Look up a channel ID by name, paginating if necessary."""
        cursor: str | None = None
        while True:
            query: dict = {"types": "public_channel,private_channel", "limit": 200}
            if cursor:
                query["cursor"] = cursor
            resp = await self.http.get(
                f"{_SLACK_API}/conversations.list",
                headers=self._headers,
                params=query,
            )
            data = resp.json()
            for ch in data.get("channels", []):
                if ch["name"] == channel_name:
                    return ch["id"]
            next_cursor = data.get("response_metadata", {}).get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor
        raise ServiceError(f"Slack channel #{channel_name} not found", "not_found")

    def _map_error(self, error_code: str) -> None:
        mapping: dict[str, tuple[str, str]] = {
            "name_taken": ("Channel already exists", "already_exists"),
            "ratelimited": ("Slack rate limit hit", "rate_limit"),
            "not_in_channel": ("Bot is not in the channel", "permission_denied"),
            "channel_not_found": ("Channel not found", "not_found"),
            "missing_scope": ("Bot missing required Slack scope", "permission_denied"),
        }
        msg, etype = mapping.get(error_code, (f"Slack API error: {error_code}", "connector_error"))
        raise ServiceError(msg, etype)
