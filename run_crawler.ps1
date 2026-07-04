# PowerShell script wrapper for Vietstock Crawler
# This script is used by Windows Task Scheduler

# Configuration
$ProjectDir = "D:\bmad-projects\crawl_data"
$PythonExe = "python"
$LogFile = Join-Path $ProjectDir "logs\vietstock_crawler.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Create logs directory if not exists
$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Log start
$LogMessage = "========================================`n"
$LogMessage += "[$Timestamp] Starting Vietstock Crawler`n"
$LogMessage += "========================================`n"
Add-Content -Path $LogFile -Value $LogMessage

# Change to project directory
Set-Location $ProjectDir

# Run the crawler
try {
    & $PythonExe crawler.py *>> $LogFile
    $ExitCode = $LASTEXITCODE

    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    if ($ExitCode -eq 0) {
        Add-Content -Path $LogFile -Value "[$Timestamp] Crawler completed successfully`n"
    } else {
        Add-Content -Path $LogFile -Value "[$Timestamp] Crawler exited with code: $ExitCode`n"
    }
} catch {
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $ErrorMsg = $_.Exception.Message
    Add-Content -Path $LogFile -Value "[$Timestamp] ERROR: $ErrorMsg`n"
}
