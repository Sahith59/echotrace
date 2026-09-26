#!/usr/bin/env bash
# Runs on the API server (piped over SSH by .github/workflows/deploy-api.yml).
# Fast-forwards the server checkout, rebuilds the containers and waits for health.
set -euo pipefail

repo="${ECHOTRACE_REPO_DIR:-$HOME/echotrace}"
branch="${ECHOTRACE_DEPLOY_BRANCH:-master}"
cd "$repo"
git fetch --prune origin "$branch"
git checkout --quiet "$branch"
git merge --ff-only "origin/$branch"

cd challenges/hearsay-audio-authentication/deploy
docker compose up -d --build --remove-orphans
docker image prune -f >/dev/null

container="$(docker compose ps -q app)"
for _ in $(seq 1 120); do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$container")"
  if [ "$status" = "healthy" ]; then
    echo "API healthy at $(git rev-parse --short HEAD)"
    exit 0
  fi
  [ "$status" = "unhealthy" ] && break
  sleep 10
done
docker compose logs --tail 80 app
echo "API did not become healthy (last status: $status)" >&2
exit 1
