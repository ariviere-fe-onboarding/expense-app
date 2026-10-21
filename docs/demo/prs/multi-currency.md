## Changes

Employees can now submit expenses in EUR, GBP, or CAD as well as USD, entering the amount exactly as it appears on the receipt.

- New currency picker on the expense form; the expense keeps its original currency.
- Expense pages, lists, and the approval queue show the original amount with its USD equivalent.
- Reimbursement is paid in USD, so the `expense.approved` webhook now sends the converted USD amount.
- Exchange rates come from Finance's monthly rate table in `app/fx.py`.

Closes #1

## Validation

- [x] ruff, mypy, bandit, pytest (70 passed), pip-audit
- [x] Updated the contract fixture and tests for the USD amount
