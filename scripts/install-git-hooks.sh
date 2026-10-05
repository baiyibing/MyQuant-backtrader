#!/bin/sh
set -e
root=$(git rev-parse --show-toplevel)
cd "$root"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || :
echo 'Installed opt-in pre-push hook: core.hooksPath=.githooks'
echo 'Bypass: SKIP_PREPUSH=1 git push ... or git push --no-verify'
echo 'Uninstall: git config --unset core.hooksPath'
