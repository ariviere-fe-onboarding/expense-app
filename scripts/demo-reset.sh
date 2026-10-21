#!/usr/bin/env bash
# Reopen demo story PRs from their permanent demo-src/<name> branches.
# Usage: scripts/demo-reset.sh [--dry-run] [name ...]
set -euo pipefail

cd "$(dirname "$0")/.."
manifest="docs/demo/prs.tsv"
dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
  shift
fi
only=("$@")

run() {
  if $dry_run; then
    printf 'would run:'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

wanted() {
  [[ ${#only[@]} -eq 0 ]] && return 0
  local candidate
  for candidate in "${only[@]}"; do [[ "$candidate" == "$1" ]] && return 0; done
  return 1
}

git fetch --quiet origin
found=0
while IFS=$'\t' read -r name title body_file; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  wanted "$name" || continue
  found=$((found + 1))
  source="demo-src/$name"
  head="demo/$name"

  if ! git rev-parse --verify --quiet "refs/remotes/origin/$source" >/dev/null; then
    echo "skip $name: origin/$source does not exist" >&2
    continue
  fi
  if [[ ! -f "$body_file" ]]; then
    echo "skip $name: missing $body_file" >&2
    continue
  fi

  for number in $(gh pr list --head "$head" --state open --json number --jq '.[].number'); do
    run gh pr close "$number" --comment "Closed by demo reset."
  done
  run git push --force --quiet origin "refs/remotes/origin/$source:refs/heads/$head"
  run gh pr create --base main --head "$head" --title "$title" --body-file "$body_file"
done < "$manifest"

if [[ $found -eq 0 ]]; then
  echo "No matching stories in $manifest."
fi
