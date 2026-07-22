$log = "logs/overnight_p1.log"
$env:PYTHONUTF8 = "1"
$start = Get-Date

# === Step 1: coin68 backfill (crypto, deep, slug-based, all shards) ===
"[$((Get-Date -Format HH:mm:ss))] === COIN68 BACKFILL ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source coin68 --from-date 2021-01-01 --workers 8 2>&1 | Tee-Object -FilePath $log -Append

"[$((Get-Date -Format HH:mm:ss))] === COIN68 DAILY ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source coin68 --latest --workers 8 2>&1 | Tee-Object -FilePath $log -Append

# === Step 2: thuonghieucongluan backfill (daily shards, 2013-2026) ===
"[$((Get-Date -Format HH:mm:ss))] === THUONGHIEUCONGLUAN BACKFILL ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source thuonghieucongluan --from-date 2013-10-01 --workers 8 2>&1 | Tee-Object -FilePath $log -Append

"[$((Get-Date -Format HH:mm:ss))] === THUONGHIEUCONGLUAN DAILY ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source thuonghieucongluan --latest --workers 8 2>&1 | Tee-Object -FilePath $log -Append

# === Continuous loop: daily crawl every 30 min ===
while ($true) {
    $elapsed = (Get-Date) - $start
    "`n[$((Get-Date -Format HH:mm:ss))] === PROCESS 1 CONTINUOUS LOOP (elapsed: $($elapsed.TotalMinutes.ToString('F1')) min) ===" | Tee-Object -FilePath $log -Append

    # coin68 daily
    uv run python news_sitemap_crawler.py --source coin68 --latest --workers 8 2>&1 | Tee-Object -FilePath $log -Append

    # thuonghieucongluan daily  
    uv run python news_sitemap_crawler.py --source thuonghieucongluan --latest --workers 8 2>&1 | Tee-Object -FilePath $log -Append

    # merge
    "  -> Running merge_news.py" | Tee-Object -FilePath $log -Append
    uv run python merge_news.py 2>&1 | Out-Null

    Start-Sleep -Seconds 1800  # 30 min
}
