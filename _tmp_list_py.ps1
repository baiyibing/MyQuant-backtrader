Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  $mb = [math]::Round($_.WorkingSetSize/1MB,0)
  $cl = $_.CommandLine
  if (-not $cl) { $cl = '' }
  $n = [Math]::Min(350, $cl.Length)
  $cmd = $cl.Substring(0, $n)
  Write-Output ("{0}`t{1}MB`t{2}" -f $_.ProcessId, $mb, $cmd)
}
