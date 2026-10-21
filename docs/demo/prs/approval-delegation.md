## Changes

Managers can hand their approvals to another manager while they're on vacation.

- New "Away from work" section on the profile page: pick a manager and the first and last day away.
- During the delegation, the delegate sees the team's submitted expenses in their queue and can approve or reject them.
- Delegates follow the same approval rules as the manager; only managers can be chosen.

Closes #2

## Validation

- [x] ruff, mypy, bandit, pytest (74 passed), pip-audit
- [x] New tests for setting, clearing, and using a delegation
