# Deep-scan baseline: legacy Finance report

This private demonstration deliberately includes a missing authentication and
authorization flaw in `GET /reports/summary`. Use synthetic data and run the app
on loopback only; do not expose this application publicly.

The story: Finance inherited a reconciliation feed. Its handler depends on the
database session but never requests the current user, checks the Finance role,
or applies the visibility policy. The app mounts the router without an auth
dependency. Consequently, even an anonymous visitor can read employee names,
emails, merchants, descriptions and amounts across every team.

The intended detection is CWE-306 / CWE-862: sensitive business records exposed
without authentication or authorization. This is a real request path through the
application, rather than an unused vulnerable snippet. A scan must follow router
registration, dependencies and the database query to assess the exposure.

Run the presenter checks from the repository root:

```sh
.venv/bin/python -m pytest demo-verify/test_reports_exposure.py --no-cov
```

Both checks pass while the vulnerability exists. They are characterization tests,
not assertions of secure behavior, and are outside normal CI. Ordinary CI tests
cover the Finance happy path.

For a live walkthrough, open `/reports/summary` in a private browser window
without signing in. The response contains records from both Design and Sales.
No password, session token, bank number or actual payment is involved.

Keep this change in the baseline, outside story PR diffs, to demonstrate a full
repository scan of existing code. A scanner may find it during other reviews too;
neither detection nor exclusivity to the deep scan is guaranteed.

The remediation is to require `CurrentUser`, reject non-Finance roles, and add
regression tests for anonymous, employee and manager requests. Reverse the
presenter exposure checks after applying the fix.
