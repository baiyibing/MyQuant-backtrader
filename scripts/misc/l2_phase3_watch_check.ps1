$ErrorActionPreference = 'Continue'
$pidFile = 'C:\Users\wangc\agent-tools\l2_phase3_pipeline.pid'
$p = (Get-Content $pidFile -Raw).Trim()
Write-Output "PID_FILE=$p"
$proc = Get-Process -Id ([int]$p) -ErrorAction SilentlyContinue
if ($proc) { Write-Output ("PID_ALIVE=yes NAME=" + $proc.ProcessName) } else { Write-Output 'PID_ALIVE=no' }

$days = @(Get-ChildItem -Path 'J:\l2_lake\l2_parquet' -Directory -Filter 'date=*' -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^date=\d{4}-\d{2}-\d{2}$' })
Write-Output ("LAKE_DAYS=" + $days.Count)
$sorted = $days | Sort-Object Name
if ($sorted.Count -gt 0) {
  Write-Output ("FIRST=" + $sorted[0].Name)
  Write-Output ("LAST=" + $sorted[-1].Name)
  $sorted | Select-Object -Last 10 | ForEach-Object { Write-Output $_.Name }
}

Write-Output '=== jsonl tail ==='
Get-Content 'C:\Users\wangc\agent-tools\l2_batch_progress.jsonl' -Tail 5

Write-Output '=== progress md last 3 ok lines ==='
Get-Content 'C:\Users\wangc\agent-tools\l2_batch_progress.md' -Tail 5

# Infer current ETL/extract from work dirs
Write-Output '=== recent csv work dirs ==='
Get-ChildItem 'J:\l2_work\stock_csv_data' -Directory -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 8 |
  ForEach-Object { Write-Output ($_.Name + ' | ' + $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')) }
