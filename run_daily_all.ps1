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

Write-Host ""
Write-Host "=== DONE daily all ==="
Get-ChildItem data\*_articles.csv | ForEach-Object {
    $n = (Get-Content $_.FullName | Measure-Object -Line).Lines - 1
    Write-Host ("  {0}: {1} rows" -f $_.Name, $n)
}
