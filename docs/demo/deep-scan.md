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

## Additional baseline options

These are deliberately vulnerable features for this private, loopback-only demo.
They are candidates for additional findings, not a guarantee of High/Critical
severity or scanner detection. Use only synthetic data. Keep them outside the
existing feature-story PR diffs once the baseline PR is reviewed and merged.

### Profile update permits self-promotion

`POST /profile` accepts a JSON `role` field and writes it directly to the signed-in
user's database record. An employee can set `role` to `finance`, then use the real
Finance queue and final-approval permissions. This is a privilege escalation
(CWE-269 / CWE-862), rather than just an incorrect role label on screen.

Presenter line: **“I'm an employee. I changed my profile request, and now I have
Finance approval rights.”**

Sign in as Priya. First open `/approvals` to show access is denied. In the browser
developer console, run this same-origin request:

```js
await fetch('/profile', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({name: 'Priya Nair', role: 'finance'})
});
location.href = '/approvals';
```

The queue now includes Marcus's pending Monitor Depot expense. Final approval is
available on another user's request; the separate self-approval prohibition still
applies. The presenter test also verifies final approval on a Sales expense using
isolated fixtures and a mocked payouts service. Restore Priya afterward by making
the same profile request with `role: 'employee'`.

Fix: remove `role` from the self-service request schema and require a separate,
authorized administrative path for permission changes.

### Receipt archive permits reading files outside its directory

`GET /receipts/download?filename=...` requires login but joins the supplied filename
to the receipt directory without checking containment. `../` escapes the directory;
an absolute path replaces the directory entirely. The process can return any file
it can read (CWE-22). This could expose application configuration or reset-email
files; the demonstration reads only a synthetic marker.

Presenter line: **“This button should download a receipt. Changing the filename
lets me read a private server file instead.”**

With the default local directory layout, create a harmless marker:

```sh
mkdir -p .local/receipts
printf 'SYNTHETIC_SECRET=demo-only\n' > .local/demo-private.txt
```

Sign in as an employee and open
`/receipts/download?filename=..%2Fdemo-private.txt`. The downloaded file is outside
the receipt archive. Do not use real credentials or real host files on screen.

Fix: look up a receipt by expense ID, enforce the expense visibility policy, and
use the existing `receipt_path()` containment validation. Remove the filename route.

Verify both flaws without accessing real files or sending real payouts:

```sh
.venv/bin/python -m pytest demo-verify/test_deep_scan_options.py --no-cov
```

These characterization checks pass while the vulnerabilities exist. Reverse them
when demonstrating remediation. Normal route tests check login, validation, and
ordinary behavior; a green test suite is not evidence of security.
