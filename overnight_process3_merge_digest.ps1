$log = "logs/overnight_p3.log"
$env:PYTHONUTF8 = "1"
$start = Get-Date

# Process 3: merge + digest + telegram cleanup
"[$((Get-Date -Format HH:mm:ss))] === PROCESS 3: MERGE + DIGEST ===" | Tee-Object -FilePath $log -Append

while ($true) {
    $elapsed = (Get-Date) - $start
    "`n[$((Get-Date -Format HH:mm:ss))] === MERGE + DIGEST (elapsed: $($elapsed.TotalMinutes.ToString('F1')) min) ===" | Tee-Object -FilePath $log -Append

    # Merge all news
    uv run python merge_news.py 2>&1 | Tee-Object -FilePath $log -Append

    # Generate digest
    uv run python morning_digest.py 2>&1 | Tee-Object -FilePath $log -Append

    # Show current CSV sizes
    Get-ChildItem data/*_articles.csv | ForEach-Object {
        $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
        "  $($_.Name): $($lines - 1) rows" | Tee-Object -FilePath $log -Append
    }

    Start-Sleep -Seconds 3600  # 1 hour between merges
}
