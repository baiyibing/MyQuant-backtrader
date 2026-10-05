$ErrorActionPreference = 'Stop'
$root = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate repository root' }
git -C $root config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) { throw 'Cannot configure core.hooksPath' }
Write-Host 'Installed opt-in pre-push hook: core.hooksPath=.githooks'
Write-Host 'Bypass: $env:SKIP_PREPUSH=1; git push; Remove-Item Env:SKIP_PREPUSH'
Write-Host 'Or: git push --no-verify'
Write-Host 'Uninstall: git config --unset core.hooksPath'
