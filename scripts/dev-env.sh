#!/usr/bin/env bash
# Generate local-only secrets shared by expense-app and payouts-service.
# Writes .env here and, if it is checked out next to this repo, ../payouts-service/.env.
# Existing .env files are kept unless you pass --force.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
payouts="$(cd "$here/.." && pwd)/payouts-service"
force="${1:-}"

if [[ -f "$here/.env" && "$force" != "--force" ]]; then
  echo "$here/.env already exists. Re-run with --force to regenerate both files."
  exit 0
fi

py="$(command -v python3)"
rand() { "$py" -c 'import secrets; print(secrets.token_urlsafe(32))'; }
webhook_secret="$(rand)"
service_token="$(rand)"
demo_password="fernway-$("$py" -c 'import secrets; print(secrets.token_hex(4))')"
fernet_key="$("$py" -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"

umask 077
cat > "$here/.env" <<ENV
FERNWAY_DATABASE_URL=sqlite:///.local/expenses.sqlite
FERNWAY_PUBLIC_ORIGIN=http://127.0.0.1:8000
FERNWAY_PAYOUTS_BASE_URL=http://127.0.0.1:8001
FERNWAY_DEMO_PASSWORD=$demo_password
PAYOUTS_WEBHOOK_SECRET=$webhook_secret
PAYOUTS_SERVICE_TOKEN=$service_token
ENV
echo "Wrote $here/.env"

if [[ -d "$payouts" ]]; then
  cat > "$payouts/.env" <<ENV
PAYOUTS_DATABASE_URL=sqlite:///.local/payouts.sqlite
PAYOUTS_WEBHOOK_SECRET=$webhook_secret
PAYOUTS_SERVICE_TOKEN=$service_token
PAYOUTS_ENCRYPTION_KEY=$fernet_key
ENV
  echo "Wrote $payouts/.env"
else
  echo "payouts-service not found at $payouts; clone it there and re-run with --force."
fi
echo "Demo password for every synthetic account: $demo_password"
