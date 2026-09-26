#!/usr/bin/env bash
# Build the landing page (/) and workspace (/app/) into one Vercel Build Output,
# and proxy /api/* to the ECHOTRACE API server named by ECHOTRACE_API_ORIGIN.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
api_origin="${ECHOTRACE_API_ORIGIN:-}"
if [[ ! "$api_origin" =~ ^https://[a-z0-9.-]+$ ]]; then
  echo "Set ECHOTRACE_API_ORIGIN in Vercel to the API server, for example https://api.echotrace.tech (https, no path, no trailing slash)." >&2
  exit 1
fi

build_app() {
  cd "$root/$1"
  [ -d node_modules ] || npm ci --no-audit --no-fund
  npm run build
}
(build_app landing)
(build_app frontend)

out="$root/.vercel/output"
rm -rf "$out"
mkdir -p "$out/static/app"
cp -R "$root/landing/dist/." "$out/static/"
cp -R "$root/frontend/dist/." "$out/static/app/"

cat > "$out/config.json" <<JSON
{
  "version": 3,
  "routes": [
    {
      "src": "^/(.*)$",
      "headers": {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
        "X-Frame-Options": "DENY"
      },
      "continue": true
    },
    { "src": "^/api/(.*)$", "dest": "$api_origin/api/\$1" },
    { "src": "^/(app/)?assets/(.*)$", "headers": { "Cache-Control": "public, max-age=31536000, immutable" }, "continue": true },
    { "handle": "filesystem" },
    { "src": "^/app$", "status": 308, "headers": { "Location": "/app/" } },
    { "src": "^/app/(?!.*\\\\.[A-Za-z0-9]+$).*$", "dest": "/app/index.html" },
    { "src": "^/(?!.*\\\\.[A-Za-z0-9]+$).*$", "dest": "/index.html" }
  ]
}
JSON
echo "Build output ready: / (landing), /app/ (workspace), /api/* -> $api_origin"
