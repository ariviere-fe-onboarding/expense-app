## Changes

Employees can choose "Suggest for me" as the category and let Claude pick one.

- `app/categorizer.py` asks Claude (`claude-opus-5-5`, low effort) to choose one of the existing categories from the merchant and description, passed as data in tags.
- Server-side refusal fallbacks are enabled.
- The option only appears when `ANTHROPIC_API_KEY` is configured; otherwise the form is unchanged.
- Adds the `anthropic==2.0.0` dependency (pip-audit clean).

Closes #4

## Validation

- [x] ruff, mypy, bandit, pytest (72 passed), pip-audit
- [x] Tests use a fake client; no API calls in CI
