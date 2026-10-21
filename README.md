# Fernway expenses

Employees submit expenses with receipts, managers approve their team's expenses, and
Finance gives final approval on larger ones. Owned by the **Product** team.

Fernway is fictional. All people, accounts, and amounts are synthetic and no money moves.

## How it fits together

```text
              ┌──────────────── expense-app (this repo) ────────────────┐
browser ────▶ │ FastAPI + Jinja → policy (who may see/approve) → SQLite │
              └───────┬─────────────────────────────────────▲───────────┘
   signed expense.approved webhook (outbox, retried)   service-token /internal API
                      ▼                                      │  (payout status, masked bank)
              ┌───────────────────── payouts-service ────────┴───────────┐
              │ verifies signature → pays each expense once → ACH (sim)  │
              │ the only place bank account numbers are stored           │
              └──────────────────────────────────────────────────────────┘
```

Bank details live only in [`payouts-service`](https://github.com/ariviere-fe-onboarding/payouts-service),
which keeps this app outside financial-audit scope. The two services deploy independently
and share one contract: [`tests/contract/expense_approved_v1.json`](tests/contract/expense_approved_v1.json),
pinned identically in both repositories and documented in
[payouts-service/docs/webhook-contract.md](https://github.com/ariviere-fe-onboarding/payouts-service/blob/main/docs/webhook-contract.md).

Organization rules (money, security, contracts, data handling, configuration) live in
[`engineering-standards`](https://github.com/ariviere-fe-onboarding/engineering-standards)
and are cited by CodeRabbit in both repositories.

## Approval rules

| Submitter | First decision | Final approval |
|---|---|---|
| Employee, expense ≤ $500.00 | Their manager | Their manager |
| Employee, expense > $500.00 | Their manager | Finance |
| Manager or anyone without a manager | Finance | Finance |

Nobody decides on their own expense. Final approval sends the `expense.approved` webhook.

## Run locally

Requires Python 3.13+ and `payouts-service` checked out next to this repository.

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
scripts/dev-env.sh                      # shared secrets for both services; prints the demo password
.venv/bin/python -m app.cli seed
.venv/bin/uvicorn app.main:create_app --factory --port 8000
```

In `../payouts-service`, seed and start it on port 8001 (see its README). Open
http://127.0.0.1:8000 and sign in as any account listed on the sign-in page.

| Account | Role |
|---|---|
| `priya@fernway.example` | Employee, Design (manager: Marcus) |
| `jonah@fernway.example` | Employee, Sales (manager: Lena) |
| `marcus@fernway.example` | Manager, Design |
| `lena@fernway.example` | Manager, Sales |
| `dana@fernway.example` | Finance |

Password-reset emails are written to `.local/mail/`. If payouts-service was down when an
expense was approved, deliver the queued webhooks with `.venv/bin/python -m app.cli retry-webhooks`.
Delete `.local/` to start over.

## Layout

- `app/config.py`: the only module that reads the environment (`get_config()`).
- `app/policy.py`: every view and approval rule.
- `app/routes/`: sign-in and password reset, expenses, approvals, profile.
- `app/webhooks.py`, `app/payouts_client.py`: outbox and client for payouts-service.
- `app/money.py`: amounts are integer cents, parsed with `Decimal`.
- `app/receipts.py`: content-sniffed uploads stored under generated names.

## Checks

```sh
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/bandit -c pyproject.toml -r app
.venv/bin/pytest
.venv/bin/pip-audit -r requirements.txt
```

## Demo

This repository is a CodeRabbit demonstration. See [docs/demo/README.md](docs/demo/README.md).
