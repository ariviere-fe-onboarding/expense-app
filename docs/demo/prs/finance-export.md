## Changes

Finance can download approved expenses as CSV for monthly reconciliation.

- New export form on the Approvals page for Finance users (From / Through dates).
- One row per approved expense with ID, date, employee, team, merchant, category, and amount, plus a total row.
- Text cells that would start a spreadsheet formula are escaped.
- Finance only; everyone else gets a 403.

Closes #3

## Validation

- [x] ruff, mypy, bandit, pytest (72 passed), pip-audit
