#!/usr/bin/env bash
# Atomic deploy of the static site to dronesclub.
#
# Procedure (see CLAUDE.md): rsync site/build/ into a fresh timestamped release
# dir under /var/www/schoolfactors-releases/, swap the /var/www/schoolfactors-current
# symlink atomically (ln -s + mv -T), prune to the last KEEP releases. Never
# rsync --delete into the live root — mid-deploy hydration breaks.
#
# Usage: scripts/deploy.sh [--build]
#   --build   run `npm run build` in site/ first; otherwise deploys site/build as-is

set -euo pipefail

HOST=dronesclub
RELEASES=/var/www/schoolfactors-releases
CURRENT=/var/www/schoolfactors-current
KEEP=3
SITE_URL=https://schoolfactors.org

repo_root=$(cd "$(dirname "$0")/.." && pwd)
build_dir="$repo_root/site/build"

if [[ "${1:-}" == "--build" ]]; then
  echo "==> building site"
  (cd "$repo_root/site" && npm run build)
fi

[[ -f "$build_dir/index.html" ]] || {
  echo "error: $build_dir/index.html not found — run with --build or build the site first" >&2
  exit 1
}

ts=$(date -u +%Y%m%d-%H%M%S)
echo "==> deploying release $ts"

# The releases dir is root-owned; create the release dir via sudo, owned by the
# deploy user so plain rsync can write into it.
ssh "$HOST" "sudo install -d -o \$(whoami) -g \$(whoami) $RELEASES/$ts"
# --link-dest hardlinks files unchanged since the live release (og images and
# data payloads mostly), so successive releases cost little disk or transfer.
prev=$(ssh "$HOST" "readlink $CURRENT" || true)
rsync -a ${prev:+--link-dest="$prev"} "$build_dir/" "$HOST:$RELEASES/$ts/"

echo "==> swapping symlink"
ssh "$HOST" "set -e
  sudo ln -sfn $RELEASES/$ts $CURRENT.new
  sudo mv -T $CURRENT.new $CURRENT
  echo \"   current -> \$(readlink $CURRENT)\"
  cd $RELEASES
  ls -1d 2*/ | sort | head -n -$KEEP | while read -r old; do
    echo \"   pruning \$old\"
    sudo rm -rf \"$RELEASES/\$old\"
  done"

echo "==> verifying"
code=$(curl -sS -o /dev/null -w '%{http_code}' "$SITE_URL/")
[[ "$code" == 200 ]] || { echo "error: $SITE_URL/ returned HTTP $code" >&2; exit 1; }
live=$(ssh "$HOST" "readlink $CURRENT")
[[ "$live" == "$RELEASES/$ts" ]] || { echo "error: symlink points at $live, expected $RELEASES/$ts" >&2; exit 1; }
echo "==> deployed $ts ($SITE_URL live, HTTP $code)"
