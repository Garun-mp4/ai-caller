#!/bin/sh
set -eu

lock_hash="$(sha256sum package-lock.json | cut -d ' ' -f 1)"
marker="node_modules/.package-lock-sha256"
installed_hash=""
if [ -f "$marker" ]; then
  installed_hash="$(cat "$marker")"
fi

if [ ! -x node_modules/.bin/next ] || [ "$installed_hash" != "$lock_hash" ]; then
  npm ci --no-audit --no-fund
  printf '%s\n' "$lock_hash" > "$marker"
fi

exec "$@"
