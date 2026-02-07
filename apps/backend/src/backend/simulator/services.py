"""Simulated service backends for workflow execution."""

from __future__ import annotations

import uuid
from datetime import datetime

from .state import ExecutionTrace, SimulatorState, TraceStep


class ServiceError(Exception):
    """Raised when a service precondition is not met."""

    def __init__(self, message: str, error_type: str = "precondition_failed"):
        self.error_type = error_type
        super().__init__(message)


class BaseService:
    """Shared init and logging for all simulated services."""

    service_name: str = ""

    def __init__(self, state: SimulatorState, trace: ExecutionTrace):
        self.state = state
        self.trace = trace

    def _log(self, node_id: str, action: str, params: dict, result: dict):
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


class HRService(BaseService):
    service_name = "hr"

    def create_employee(self, node_id: str, **params) -> dict:
        employee_name = params.get("employee_name", "Unknown")
        role = params.get("role", "Employee")
        department = params.get("department", "General")
        employee_id = f"EMP-{uuid.uuid4().hex[:6].upper()}"

        self.state.employees[employee_id] = {
            "id": employee_id,
            "name": employee_name,
            "role": role,
            "department": department,
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }

        result = {"employee_id": employee_id, "name": employee_name, "status": "created"}
        self._log(node_id, "create_employee", params, result)
        return result

    def enroll_benefits(self, node_id: str, **params) -> dict:
        employee_id = params.get("employee_id")
        if employee_id and employee_id not in self.state.employees:
            raise ServiceError(f"Employee {employee_id} not found — create HR record first")

        plan = params.get("plan", "standard")
        result = {"employee_id": employee_id, "plan": plan, "status": "enrolled"}
        self._log(node_id, "enroll_benefits", params, result)
        return result


class GoogleService(BaseService):
    service_name = "google"

    def provision_account(self, node_id: str, **params) -> dict:
        employee_name = params.get("employee_name", "Unknown")
        if not any(e["name"] == employee_name for e in self.state.employees.values()):
            raise ServiceError(
                f"No HR record found for {employee_name} — create employee record first"
            )

        email = params.get("email", f"{employee_name.lower().replace(' ', '.')}@company.com")
        self.state.google_accounts[email] = {
            "email": email,
            "name": employee_name,
            "status": "active",
        }

        result = {"email": email, "status": "provisioned"}
        self._log(node_id, "provision_account", params, result)
        return result

    def send_email(self, node_id: str, **params) -> dict:
        result = {"to": params.get("to", ""), "subject": params.get("subject", ""), "status": "sent"}
        self._log(node_id, "send_email", params, result)
        return result

    def create_calendar_event(self, node_id: str, **params) -> dict:
        result = {"title": params.get("title", "Meeting"), "attendees": params.get("attendees", []), "status": "created"}
        self._log(node_id, "create_calendar_event", params, result)
        return result


class SlackService(BaseService):
    service_name = "slack"

    def create_channel(self, node_id: str, **params) -> dict:
        channel_name = params.get("channel_name", "#general")
        self.state.slack_channels[channel_name] = []
        result = {"channel": channel_name, "status": "created"}
        self._log(node_id, "create_channel", params, result)
        return result

    def invite_user(self, node_id: str, **params) -> dict:
        email = params.get("email", "")
        channel_name = params.get("channel_name", "#general")

        if email and email not in self.state.google_accounts:
            raise ServiceError(
                f"No Google account found for {email} — provision account first"
            )

        self.state.slack_users.add(email)
        if channel_name in self.state.slack_channels:
            self.state.slack_channels[channel_name].append(email)

        result = {"email": email, "channel": channel_name, "status": "invited"}
        self._log(node_id, "invite_user", params, result)
        return result

    def send_message(self, node_id: str, **params) -> dict:
        result = {"channel": params.get("channel_name", "#general"), "message": params.get("message", ""), "status": "sent"}
        self._log(node_id, "send_message", params, result)
        return result


class JiraService(BaseService):
    service_name = "jira"

    def create_issue(self, node_id: str, **params) -> dict:
        issue_key = f"ONBOARD-{uuid.uuid4().hex[:4].upper()}"
        summary = params.get("summary", "")
        issue_type = params.get("issue_type", "Task")

        self.state.jira_issues[issue_key] = {
            "key": issue_key,
            "summary": summary,
            "type": issue_type,
            "status": "To Do",
            "assignee": params.get("assignee"),
        }

        result = {"issue_key": issue_key, "summary": summary, "status": "created"}
        self._log(node_id, "create_issue", params, result)
        return result

    def create_epic(self, node_id: str, **params) -> dict:
        params["issue_type"] = "Epic"
        return self.create_issue(node_id, **params)

    def assign_issue(self, node_id: str, **params) -> dict:
        issue_key = params.get("issue_key", "")
        assignee = params.get("assignee", "")

        if issue_key and issue_key in self.state.jira_issues:
            self.state.jira_issues[issue_key]["assignee"] = assignee

        result = {"issue_key": issue_key, "assignee": assignee, "status": "assigned"}
        self._log(node_id, "assign_issue", params, result)
        return result


class GitHubService(BaseService):
    service_name = "github"

    def add_to_org(self, node_id: str, **params) -> dict:
        username = params.get("username", "")
        employee_name = params.get("employee_name", "")

        if employee_name and not any(
            e["name"] == employee_name for e in self.state.employees.values()
        ):
            raise ServiceError(
                f"No HR record found for {employee_name} — create employee record first"
            )

        org = params.get("org", "techcorp")
        self.state.github_members[username] = {
            "username": username,
            "org": org,
            "role": "member",
        }

        result = {"username": username, "org": org, "status": "added"}
        self._log(node_id, "add_to_org", params, result)
        return result

    def grant_repo_access(self, node_id: str, **params) -> dict:
        username = params.get("username", "")
        repo = params.get("repo", "")

        if username and username not in self.state.github_members:
            raise ServiceError(f"{username} is not in the org — add to org first")

        permission = params.get("permission", "read")
        result = {"username": username, "repo": repo, "permission": permission, "status": "granted"}
        self._log(node_id, "grant_repo_access", params, result)
        return result
