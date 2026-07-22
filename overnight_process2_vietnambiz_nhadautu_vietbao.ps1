$log = "logs/overnight_p2.log"
$env:PYTHONUTF8 = "1"
$start = Get-Date

# === Step 1: nhadautu (single sitemap, fast) ===
"[$((Get-Date -Format HH:mm:ss))] === NHADAUTU BACKFILL ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source nhadautu --from-date 2026-01-01 --workers 4 2>&1 | Tee-Object -FilePath $log -Append

# === Step 2: vietbao (monthly shards, ~30 shards) ===
"[$((Get-Date -Format HH:mm:ss))] === VIETBAO BACKFILL ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source vietbao --from-date 2024-01-01 --workers 6 2>&1 | Tee-Object -FilePath $log -Append

# === Step 3: vietnambiz 9 categories ===
$cats = @("thoi-su", "doanh-nghiep", "chung-khoan", "tai-chinh", "hang-hoa", "nha-dat", "kinh-doanh", "quoc-te", "du-bao")
foreach ($cat in $cats) {
    "`n[$((Get-Date -Format HH:mm:ss))] === VIETNAMBIZ category=$cat ===" | Tee-Object -FilePath $log -Append
    uv run python vietnambiz_crawler.py --range --category $cat --max-pages 0 --workers 6 2>&1 | Tee-Object -FilePath $log -Append
}

# === Step 4: daily/latest for all ===
"[$((Get-Date -Format HH:mm:ss))] === VIETNAMBIZ DAILY ===" | Tee-Object -FilePath $log -Append
uv run python vietnambiz_crawler.py --latest --workers 6 2>&1 | Tee-Object -FilePath $log -Append

"[$((Get-Date -Format HH:mm:ss))] === NHADAUTU DAILY ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source nhadautu --latest --workers 4 2>&1 | Tee-Object -FilePath $log -Append

"[$((Get-Date -Format HH:mm:ss))] === VIETBAO DAILY ===" | Tee-Object -FilePath $log -Append
uv run python news_sitemap_crawler.py --source vietbao --latest --workers 6 2>&1 | Tee-Object -FilePath $log -Append

# === Continuous loop ===
while ($true) {
    $elapsed = (Get-Date) - $start
    "`n[$((Get-Date -Format HH:mm:ss))] === PROCESS 2 CONTINUOUS LOOP (elapsed: $($elapsed.TotalMinutes.ToString('F1')) min) ===" | Tee-Object -FilePath $log -Append

    # Vietnambiz daily
    uv run python vietnambiz_crawler.py --latest --workers 6 2>&1 | Tee-Object -FilePath $log -Append
    # nhadautu daily
    uv run python news_sitemap_crawler.py --source nhadautu --latest --workers 4 2>&1 | Tee-Object -FilePath $log -Append
    # vietbao daily
    uv run python news_sitemap_crawler.py --source vietbao --latest --workers 6 2>&1 | Tee-Object -FilePath $log -Append

    # merge
    "  -> Running merge_news.py" | Tee-Object -FilePath $log -Append
    uv run python merge_news.py 2>&1 | Out-Null

    Start-Sleep -Seconds 1800  # 30 min
}
