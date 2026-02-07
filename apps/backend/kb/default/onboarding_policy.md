# TechCorp — Employee Onboarding Policy

## Day 1: System Access & Welcome

### Required
1. **Create employee record** in HR Portal (owner: HR Manager)
2. **Provision Google Workspace account** — email, calendar, drive (owner: IT Admin; depends on: step 1)
3. **Provision Slack account** and invite to `#general`, `#new-hires`, and team channel (owner: IT Admin; depends on: step 2)
4. **Send welcome email** with login credentials and first-day instructions (owner: HR Manager; depends on: step 2)
5. **Create GitHub account** and add to org and team (owner: IT Admin; depends on: step 1)

### Optional
- Add to optional Slack interest channels (e.g., `#social`, `#pets`)

## Week 1: Integration & Training

### Required
1. **Schedule team introduction meeting** via Google Calendar (owner: Team Lead; depends on: Day 1 complete)
2. **Create onboarding Jira epic** with training tasks and deadlines (owner: Team Lead)
3. **Assign compliance training** modules in HR Portal (owner: HR Manager)
4. **Set up workstation** — laptop, monitors, peripherals (owner: IT Admin)
5. **Grant repository access** based on team and role (owner: IT Admin; depends on: Day 1 step 5)

### Optional
- Office tour (for on-site employees)
- Schedule lunch with team

## Month 1: Goals & Benefits

### Required
1. **Set 30/60/90-day performance goals** in Jira (owner: Team Lead; depends on: Week 1 step 2)
2. **Assign onboarding buddy** from the same team (owner: HR Manager)
3. **Enroll in benefits** — health, dental, 401k (owner: New Employee; depends on: Day 1 step 1; deadline: 30 days from start)
4. **Complete all compliance training** (owner: New Employee; deadline: 30 days from start)

### Optional
- Schedule skip-level 1:1 with department head
- Join an employee resource group

## Dependency Summary

```
Employee Record (HR Portal)
├── Google Workspace Account
│   ├── Slack Account & Channels
│   └── Welcome Email
├── GitHub Org Membership
│   └── Repository Access
└── Benefits Enrollment (within 30 days)

Team Introduction ← Day 1 complete
Onboarding Jira Epic → Performance Goals
```
