# Chạy tất cả crawler tin tức hằng ngày: Cafef (RSS) + SSI/HSC/VNDIRECT (latest).
# Dùng cho Windows Task Scheduler (vd 2h sáng). Mỗi crawler có dedup riêng nên re-run an toàn.
$ErrorActionPreference = "Continue"
$root = if ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { $PWD.Path }
Set-Location $root
$env:PYTHONUTF8 = "1"

function Run($msg, $cmd) { Write-Host ""; Write-Host "=== $msg ==="; Invoke-Expression $cmd }

Run "Cafef daily (RSS, 3 section)" "python cafef_crawler.py --daily --csv data/cafef_articles.csv"
Run "SSI latest (Bản Tin Thị Trường)" "python ssi_crawler.py --latest --csv data/ssi_articles.csv"
Run "HSC latest (Research Insights)" "python hsc_crawler.py --latest --csv data/hsc_articles.csv"

# VNDIRECT: 4 category (Playwright, chậm hơn)
foreach ($cat in @("company-note", "sector-note", "strategy-note", "economics-note")) {
    Run "VNDIRECT latest ($cat)" "python vndirect_crawler.py --latest --category $cat --csv data/vndirect_articles.csv"
}

# Vietstock: báo cáo phân tích mới nhất (publish 17-20h hôm trước → đã có trước 6h sáng)
$yesterday = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
$env:CSV_FILE = "data/vnstock_articles.csv"
Run "Vietstock recent (>= $yesterday)" "python crawler.py --start-date $yesterday --headless true"
$env:CSV_FILE = $null

# Gộp tất cả nguồn + tạo digest sáng
Run "Merge news_articles.csv" "python merge_news.py"
Run "Morning digest (2 ngày)" "python morning_digest.py --days 2"

# === Objective-data layer (VN30 primary-source, FR-14) ===
# Tier-1 corporate actions + Tier-2 news → build unified VN30 objective dataset.
# Vietstock/Cafef disclosure adapters (E2) pending — add here once implemented.
Run "VSDC latest (VN30 corporate actions)" "python -m objective.adapters.vsdc_crawler --latest"
Run "VnExpress RSS (Tier-2 news)" "python -m objective.adapters.tier2_rss.vnexpress --latest"
foreach ($outlet in @("tuoitre", "nld", "thanhnien", "vietnamplus")) {
    Run "Tier-2 RSS ($outlet)" "python -m objective.adapters.tier2_rss.outlets $outlet --latest"
}
Run "Build unified objective dataset" "python -m objective.build_objective"

Write-Host ""
Write-Host "=== DONE daily all ==="
Get-ChildItem data\*_articles.csv | ForEach-Object {
    $n = (Get-Content $_.FullName | Measure-Object -Line).Lines - 1
    Write-Host ("  {0}: {1} rows" -f $_.Name, $n)
}
