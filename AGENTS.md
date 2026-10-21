# Repository development workflow

These rules apply to every change in this repository, including application code, tests,
documentation, configuration, and tooling, by every contributor and coding agent.

## 1. Organization standards

Follow the Fernway [engineering standards](https://github.com/ariviere-fe-onboarding/engineering-standards).
They are mandatory and CodeRabbit cites them in review. In particular: integer cents for
money, configuration only through `get_config()`, and bank data only in `payouts-service`.

## 2. Dependencies

Do not add a dependency without the maintainer's explicit approval. Pin every version in
`requirements.txt` or `requirements-dev.txt` and keep `pip-audit` clean.

## 3. Local CodeRabbit review before every push

Run `coderabbit review --committed --base main` over the committed changes before pushing.
Resolve actionable findings and re-run, up to four iterations. If findings remain after
four passes, stop and ask the maintainer how to proceed. Never skip a finding without
explicit approval, and record every approved skip in the PR description. If the CLI is
unavailable or fails, stop and report it; a failed review is not a clean review.

## 4. Pull request and merge gate

Every change goes through a pull request linked to an issue with acceptance criteria.
Never push to or merge into `main` directly. Wait for CodeRabbit to review the latest
commit, reply in line to every finding with the fix or the reason it was not accepted,
and never merge past an unresolved blocking finding or a failed Security Gate.

## 5. Python

- Python 3.13+, fully type-annotated, clean under `mypy --strict`. No `Any` to silence
  the checker and no `# type: ignore` without a comment explaining why.
- Validate external input (HTTP bodies, webhooks, files, model output) with Pydantic at
  the boundary. A cast is not validation.
- Docstrings on modules and public functions. Small functions, early returns.
- Ruff for lint and format, Bandit for security analysis.

## 6. Tests

Add tests for new and changed behavior, including failure paths and authorization
denials. Report which checks ran: ruff, mypy, bandit, pytest, pip-audit.

## 7. Cross-repository changes

`expense-app` and `payouts-service` deploy independently. Any change to the
`expense.approved` webhook or the `/internal` API must keep the pinned contract fixture
identical in both repositories and follow the API contracts guideline. Link the
companion PR in the other repository.
