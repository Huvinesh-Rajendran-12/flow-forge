# TechCorp — Available Systems

## Slack
- **Purpose:** Messaging, channel management, notifications
- **Capabilities:** Send messages, create channels, invite users to channels, post announcements
- **API pattern:** `POST /api/slack/messages`, `POST /api/slack/channels`, `POST /api/slack/channels/{id}/invite`
- **Auth:** Bot token (OAuth2)

## Jira
- **Purpose:** Project management, task tracking, sprint planning
- **Capabilities:** Create issues, assign tasks, transition statuses, add comments, create boards
- **API pattern:** `POST /api/jira/issues`, `PUT /api/jira/issues/{key}/assign`, `GET /api/jira/projects/{id}/board`
- **Auth:** API token (Basic Auth)

## Google Workspace
- **Purpose:** Email, calendar, document collaboration
- **Capabilities:** Send email, create calendar events, share documents, provision user accounts
- **API pattern:** `POST /api/google/mail/send`, `POST /api/google/calendar/events`, `POST /api/google/drive/share`
- **Auth:** Service account (OAuth2)

## HR Portal
- **Purpose:** Employee records, benefits enrollment, org chart
- **Capabilities:** Create employee record, enroll in benefits, assign manager, update employment status
- **API pattern:** `POST /api/hr/employees`, `POST /api/hr/employees/{id}/benefits`, `PUT /api/hr/employees/{id}/status`
- **Auth:** Internal SSO

## GitHub
- **Purpose:** Code repositories, access management, CI/CD
- **Capabilities:** Add user to org, grant repo access, create team membership, provision SSH keys
- **API pattern:** `PUT /api/github/orgs/{org}/members/{user}`, `PUT /api/github/repos/{repo}/collaborators/{user}`, `POST /api/github/orgs/{org}/teams/{team}/members`
- **Auth:** GitHub App (JWT)
