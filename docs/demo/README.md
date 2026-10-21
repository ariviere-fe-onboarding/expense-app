# Running the CodeRabbit demo

Three repositories in `ariviere-fe-onboarding` make up the demo:

| Repository | Role in the demo |
|---|---|
| `expense-app` | Main application; most story PRs open here |
| `payouts-service` | Separately owned consumer; shows cross-repository impact |
| `engineering-standards` | Organization guidelines that CodeRabbit cites in review |

## Story PRs

Each story PR lives permanently on a source branch named `demo-src/<name>` and is listed
in [`prs.tsv`](prs.tsv) with its title and description file. Opening a story PR never
touches `main`.

To reset the demo after a customer session (for example, after accepting an autofix):

```sh
scripts/demo-reset.sh --dry-run   # show what would happen
scripts/demo-reset.sh             # close open demo PRs and reopen them fresh
scripts/demo-reset.sh <name>      # reset one story
```

The script only creates, force-pushes, and closes branches under `demo/`. It never
pushes to `main` or to `demo-src/*`.

## Adding a story

1. Create the issue with acceptance criteria using the Feature template.
2. Build the change on `demo-src/<name>` from `main`, with ordinary passing tests.
3. Add `docs/demo/prs/<name>.md` with the PR description, including `Closes #<issue>`.
4. Add a line to `prs.tsv`: `<name><TAB><PR title><TAB>docs/demo/prs/<name>.md`.
5. Put any presenter-only verification tests in `demo-verify/`, not in the PR.

## Presenter checks

`demo-verify/` holds checks that only the presenter runs, for example to confirm that
an autofix produced the intended behavior. CI does not run them, and they are not part
of any story PR.
