from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ApiEntry:
    service: str
    action: str
    description: str
    parameters: list[dict]
    auth: str
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "action": self.action,
            "description": self.description,
            "parameters": self.parameters,
            "auth": self.auth,
        }


def _param(name: str, type_: str = "string", required: bool = True) -> dict:
    return {"name": name, "type": type_, "required": required}


API_CATALOG: list[ApiEntry] = [
    # --- HR ---
    ApiEntry(
        service="hr",
        action="create_employee",
        description="Create a new employee record in the HR Portal",
        parameters=[
            _param("employee_name"),
            _param("role"),
            _param("department", required=False),
        ],
        auth="Internal SSO",
        keywords=["hire", "onboard", "new hire", "employee", "hr record", "personnel"],
    ),
    ApiEntry(
        service="hr",
        action="enroll_benefits",
        description="Enroll an employee in benefits (health, dental, 401k)",
        parameters=[
            _param("employee_id"),
            _param("plan", required=False),
        ],
        auth="Internal SSO",
        keywords=["benefits", "health", "dental", "401k", "insurance", "enrollment"],
    ),
    # --- Google Workspace ---
    ApiEntry(
        service="google",
        action="provision_account",
        description="Provision a Google Workspace account (email, calendar, drive)",
        parameters=[
            _param("employee_name"),
            _param("email", required=False),
        ],
        auth="Service account (OAuth2)",
        keywords=["google", "email", "workspace", "account", "provision", "gmail", "calendar", "drive"],
    ),
    ApiEntry(
        service="google",
        action="send_email",
        description="Send an email via Google Workspace",
        parameters=[
            _param("to"),
            _param("subject"),
            _param("body", required=False),
        ],
        auth="Service account (OAuth2)",
        keywords=["email", "send", "mail", "message", "notification", "welcome"],
    ),
    ApiEntry(
        service="google",
        action="create_calendar_event",
        description="Create a calendar event in Google Calendar",
        parameters=[
            _param("title"),
            _param("attendees", required=False),
            _param("date", required=False),
        ],
        auth="Service account (OAuth2)",
        keywords=["calendar", "event", "meeting", "schedule", "invite", "appointment"],
    ),
    # --- Slack ---
    ApiEntry(
        service="slack",
        action="create_channel",
        description="Create a new Slack channel",
        parameters=[
            _param("channel_name"),
        ],
        auth="Bot token (OAuth2)",
        keywords=["slack", "channel", "create", "messaging", "chat"],
    ),
    ApiEntry(
        service="slack",
        action="invite_user",
        description="Invite a user to a Slack channel",
        parameters=[
            _param("email"),
            _param("channel_name"),
        ],
        auth="Bot token (OAuth2)",
        keywords=["slack", "invite", "user", "channel", "add", "onboard"],
    ),
    ApiEntry(
        service="slack",
        action="send_message",
        description="Send a message to a Slack channel",
        parameters=[
            _param("channel_name"),
            _param("message"),
        ],
        auth="Bot token (OAuth2)",
        keywords=["slack", "message", "send", "notify", "announcement", "post"],
    ),
    # --- Jira ---
    ApiEntry(
        service="jira",
        action="create_issue",
        description="Create a Jira issue (task, bug, story)",
        parameters=[
            _param("summary"),
            _param("issue_type", required=False),
            _param("assignee", required=False),
        ],
        auth="API token (Basic Auth)",
        keywords=["jira", "issue", "task", "ticket", "bug", "story", "create"],
    ),
    ApiEntry(
        service="jira",
        action="create_epic",
        description="Create a Jira epic for grouping related tasks",
        parameters=[
            _param("summary"),
            _param("assignee", required=False),
        ],
        auth="API token (Basic Auth)",
        keywords=["jira", "epic", "project", "group", "sprint", "onboarding"],
    ),
    ApiEntry(
        service="jira",
        action="assign_issue",
        description="Assign a Jira issue to a user",
        parameters=[
            _param("issue_key"),
            _param("assignee"),
        ],
        auth="API token (Basic Auth)",
        keywords=["jira", "assign", "issue", "task", "delegate"],
    ),
    # --- GitHub ---
    ApiEntry(
        service="github",
        action="add_to_org",
        description="Add a user to the GitHub organization",
        parameters=[
            _param("username"),
            _param("employee_name", required=False),
            _param("org", required=False),
        ],
        auth="GitHub App (JWT)",
        keywords=["github", "org", "organization", "add", "member", "team"],
    ),
    ApiEntry(
        service="github",
        action="grant_repo_access",
        description="Grant a user access to a GitHub repository",
        parameters=[
            _param("username"),
            _param("repo"),
            _param("permission", required=False),
        ],
        auth="GitHub App (JWT)",
        keywords=["github", "repo", "repository", "access", "permission", "code"],
    ),
]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def search_api_catalog(query: str, top_k: int = 5) -> list[ApiEntry]:
    """Search the API catalog by keyword overlap with query tokens."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return API_CATALOG[:top_k]

    scored: list[tuple[float, int, ApiEntry]] = []
    for idx, entry in enumerate(API_CATALOG):
        entry_tokens = (
            _tokenize(entry.description)
            | _tokenize(" ".join(entry.keywords))
            | _tokenize(entry.service)
            | _tokenize(entry.action)
        )
        overlap = len(query_tokens & entry_tokens)
        if overlap > 0:
            scored.append((overlap, -idx, entry))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [entry for _, _, entry in scored[:top_k]]
