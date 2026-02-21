# Branch Protection Baseline

Use these settings on the default branch (`main` or `master`) to keep merges reliable.

## Required status checks

Mark these as required:

- `CI / backend-tests`
- `CI / frontend-build`

Do not mark this one required unless you always provide external secrets on PRs:

- `Integration / openrouter-integration-tests`

## Recommended pull request rules

- Require a pull request before merging.
- Require at least 1 approving review.
- Dismiss stale approvals when new commits are pushed.
- Require status checks to pass before merging.
- Require branches to be up to date before merging.
- Restrict force pushes and branch deletion.

## Setup notes

1. Open repository settings -> Branches -> Branch protection rules.
2. Add or edit the rule for your default branch.
3. Enable the rules above.
4. Select required checks from the list exactly as shown by GitHub.

If check names differ slightly in your UI, pick the checks that correspond to the CI job names in `.github/workflows/ci.yml`.
