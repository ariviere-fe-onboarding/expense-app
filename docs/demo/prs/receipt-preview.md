## Changes

Employees can open receipts in a new browser tab using a Preview link next to Download.
The new route uses a receipt resolver that loads the stored file and content type,
checks file availability, and returns an inline response. Missing attachments and
invalid storage paths return 404; preview requests require sign-in.

Closes #12

## Validation

- 74 tests pass, including inline delivery, sign-in enforcement, missing files, storage
  path validation, and the existing attachment-download behavior.
- Ruff, formatting, strict mypy, Bandit, and pip-audit pass without new suppressions.
- Local CodeRabbit review results are recorded in the GitHub PR description after review.

This is an intentionally defective CodeRabbit demonstration. Findings are retained
with the maintainer's authorization; leave this PR unmerged.

## Reset

Permanent source: `demo-src/receipt-preview`. From that branch, run
`scripts/demo-reset.sh receipt-preview` to reopen a fresh demonstration. The manifest
entry for this story is included on the source branch.
