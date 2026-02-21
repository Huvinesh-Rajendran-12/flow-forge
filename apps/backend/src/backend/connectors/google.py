"""Google Workspace connector (Admin SDK, Gmail, Calendar)."""

from __future__ import annotations

import asyncio
import base64
import json
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, Any

import httpx

from ..simulator.services import ServiceError
from ..simulator.state import ExecutionTrace
from .base import BaseConnector
from .registry import register

if TYPE_CHECKING:
    from ..config import Settings

_ADMIN_API = "https://admin.googleapis.com/admin/directory/v1"
_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]


@register
class GoogleConnector(BaseConnector):
    """Real Google Workspace connector using service account with domain-wide delegation.

    Required settings:
        GOOGLE_SERVICE_ACCOUNT_JSON — full JSON string of the service account key
        GOOGLE_ADMIN_EMAIL          — the admin user to impersonate (domain-wide delegation)
    Optional:
        GOOGLE_DOMAIN               — your Google Workspace domain (e.g. company.com)
    """

    service_name = "google"

    def __init__(
        self,
        service_account_info: dict,
        admin_email: str,
        domain: str,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> None:
        super().__init__(trace, http_client)
        self._sa_info = service_account_info
        self._admin_email = admin_email
        self._domain = domain
        self._token_cache: dict[str, Any] = {}

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        trace: ExecutionTrace,
        http_client: httpx.AsyncClient,
    ) -> GoogleConnector:
        sa_json = settings.google_service_account_json or "{}"
        try:
            sa_info = json.loads(sa_json)
        except json.JSONDecodeError:
            sa_info = {}
        return cls(
            sa_info,
            settings.google_admin_email or "",
            settings.google_domain or "",
            trace,
            http_client,
        )

    @classmethod
    def is_configured(cls, settings: Settings) -> bool:
        return bool(settings.google_service_account_json and settings.google_admin_email)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def provision_account(self, node_id: str, **params) -> dict:
        """Create a Google Workspace user account."""
        employee_name = params.get("employee_name", "")
        parts = employee_name.strip().split()
        given_name = parts[0] if parts else employee_name
        family_name = parts[-1] if len(parts) > 1 else ""
        safe_name = employee_name.lower().replace(" ", ".")
        email = params.get("email") or f"{safe_name}@{self._domain}"

        headers = await self._auth_headers()
        resp = await self.http.post(
            f"{_ADMIN_API}/users",
            headers=headers,
            json={
                "primaryEmail": email,
                "name": {"givenName": given_name, "familyName": family_name},
                "password": _temp_password(employee_name),
                "changePasswordAtNextLogin": True,
            },
        )
        if resp.status_code == 409:
            raise ServiceError(f"Google account {email} already exists", "already_exists")
        if resp.status_code not in (200, 201):
            raise ServiceError(
                f"Google provision_account failed ({resp.status_code}): {resp.text[:200]}",
                "connector_error",
            )
        result = {"email": email, "status": "provisioned"}
        self._log(node_id, "provision_account", params, result)
        return result

    async def send_email(self, node_id: str, **params) -> dict:
        """Send an email via Gmail API."""
        to = params.get("to", "")
        subject = params.get("subject", "")
        body = params.get("body", "")

        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        msg["from"] = self._admin_email
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        headers = await self._auth_headers()
        resp = await self.http.post(
            f"{_GMAIL_API}/users/{self._admin_email}/messages/send",
            headers=headers,
            json={"raw": raw},
        )
        if resp.status_code not in (200, 201):
            raise ServiceError(
                f"Gmail send_email failed ({resp.status_code}): {resp.text[:200]}",
                "connector_error",
            )
        result = {"to": to, "subject": subject, "status": "sent"}
        self._log(node_id, "send_email", params, result)
        return result

    async def create_calendar_event(self, node_id: str, **params) -> dict:
        """Create a Google Calendar event."""
        title = params.get("title", "Meeting")
        attendees = params.get("attendees") or []
        date = params.get("date", "2026-01-01")

        headers = await self._auth_headers()
        event_body = {
            "summary": title,
            "attendees": [{"email": a} for a in attendees],
            "start": {"date": date},
            "end": {"date": date},
        }
        resp = await self.http.post(
            f"{_CALENDAR_API}/calendars/{self._admin_email}/events",
            headers=headers,
            json=event_body,
        )
        if resp.status_code not in (200, 201):
            raise ServiceError(
                f"Google Calendar create_event failed ({resp.status_code}): {resp.text[:200]}",
                "connector_error",
            )
        result = {"title": title, "attendees": attendees, "status": "created"}
        self._log(node_id, "create_calendar_event", params, result)
        return result

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _auth_headers(self) -> dict:
        """Return Authorization headers with a fresh access token."""
        token = await asyncio.get_event_loop().run_in_executor(
            None, self._get_access_token
        )
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _get_access_token(self) -> str:
        """Obtain an access token via JWT assertion (service account flow).

        Uses only the standard library + httpx — no google-auth SDK required.
        """
        import time
        import urllib.parse

        try:
            import jwt  # PyJWT
        except ImportError:
            raise ServiceError(
                "PyJWT is required for Google connector. Install with: pip install PyJWT cryptography",
                "connector_error",
            )

        now = int(time.time())
        scope = " ".join(_SCOPES)
        claim = {
            "iss": self._sa_info.get("client_email", ""),
            "sub": self._admin_email,
            "scope": scope,
            "aud": _TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }
        private_key = self._sa_info.get("private_key", "")
        assertion = jwt.encode(claim, private_key, algorithm="RS256")

        # Synchronous token fetch (called from run_in_executor)
        import urllib.request
        data = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }).encode()
        req = urllib.request.Request(_TOKEN_URL, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
        if "access_token" not in body:
            raise ServiceError(f"Failed to obtain Google access token: {body}", "auth_error")
        return body["access_token"]


def _temp_password() -> str:
    """Generate a secure random temporary password for a new user."""
    import secrets, string
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(12))
