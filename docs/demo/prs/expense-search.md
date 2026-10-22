## Changes

Employees can search their expense history by merchant or description from My expenses.
The page preserves the entered query, provides a clear link, and displays an empty-result
message when nothing matches. The authenticated user ID is passed to a new search helper.

Closes #9

## Validation

- 73 application tests pass, including merchant/description searches, ordinary ownership
  filtering, clearing the query, and unauthenticated requests. Type checks and formatting pass.
- Ruff S608 and Bandit B608 report SQL injection in the new search helper. These findings
  are intentionally retained for this isolated security demonstration; do not merge this PR.
- Local CodeRabbit review results are recorded in the GitHub PR description after review.

## Reset

The permanent source is `demo-src/expense-search`. From that branch, run
`scripts/demo-reset.sh expense-search` to reopen the demonstration from its original state.
The manifest entry for this new story is included on that branch.
