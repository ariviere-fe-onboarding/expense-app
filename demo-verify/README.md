# Presenter checks

Tests here are run by the presenter, not by CI, to confirm a fix behaves as intended
after a demo (for example, after applying a CodeRabbit autofix to a story branch):

```sh
.venv/bin/pytest demo-verify -p no:cacheprovider --no-cov
```

Keep these out of story PRs so the PRs read like ordinary feature work.
