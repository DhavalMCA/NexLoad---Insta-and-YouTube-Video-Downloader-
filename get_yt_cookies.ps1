# ─────────────────────────────────────────────────────────────────────────────
# get_yt_cookies.ps1
#
# Exports YouTube cookies from Chrome (or Edge/Firefox) using yt-dlp,
# base64-encodes the result, and copies it to your clipboard so you can
# paste it straight into Render > Environment > YOUTUBE_COOKIES_B64.
#
# USAGE (run in PowerShell as your normal user, NOT as Admin):
#   .\get_yt_cookies.ps1              # default: Chrome
#   .\get_yt_cookies.ps1 -Browser firefox
#   .\get_yt_cookies.ps1 -Browser edge
#
# REQUIREMENTS:
#   - yt-dlp installed  (pip install yt-dlp)
#   - The chosen browser installed and you are logged in to YouTube in it
#   - The browser must be CLOSED before running (Chrome locks the cookie DB)
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$Browser = "chrome"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== NexLoad – YouTube Cookie Exporter ===" -ForegroundColor Cyan
Write-Host "Browser : $Browser" -ForegroundColor Gray
Write-Host ""
Write-Host ">> Make sure $Browser is CLOSED before continuing." -ForegroundColor Yellow
Read-Host   "   Press ENTER when ready"

# ── 1. Export cookies to a temp file ────────────────────────────────────────
$tmpFile = [System.IO.Path]::GetTempFileName() + "_yt_cookies.txt"

Write-Host ""
Write-Host "Exporting cookies from $Browser..." -ForegroundColor Cyan

try {
    $output = & yt-dlp `
        --cookies-from-browser $Browser `
        --cookies $tmpFile `
        --skip-download `
        --quiet `
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1

    if (-not (Test-Path $tmpFile) -or (Get-Item $tmpFile).Length -eq 0) {
        throw "Cookie file is empty. Make sure you are logged in to YouTube in $Browser."
    }

    Write-Host "Cookies exported successfully." -ForegroundColor Green
}
catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Tip: Make sure the browser is fully closed and you are logged in to YouTube." -ForegroundColor Yellow
    exit 1
}

# ── 2. Base64-encode ─────────────────────────────────────────────────────────
Write-Host "Base64-encoding cookies..." -ForegroundColor Cyan
$bytes  = [System.IO.File]::ReadAllBytes($tmpFile)
$b64    = [Convert]::ToBase64String($bytes)

# ── 3. Copy to clipboard ─────────────────────────────────────────────────────
$b64 | Set-Clipboard
Write-Host "Copied to clipboard!" -ForegroundColor Green

# ── 4. Clean up temp file ────────────────────────────────────────────────────
Remove-Item $tmpFile -Force

# ── 5. Instructions ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host " NEXT STEPS – paste into Render:" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host " 1. Open  https://dashboard.render.com" -ForegroundColor White
Write-Host " 2. Select your NexLoad service" -ForegroundColor White
Write-Host " 3. Go to  Environment  tab" -ForegroundColor White
Write-Host " 4. Add environment variable:" -ForegroundColor White
Write-Host "      Key  :  YOUTUBE_COOKIES_B64" -ForegroundColor Yellow
Write-Host "      Value:  (already in your clipboard — just Ctrl+V)" -ForegroundColor Yellow
Write-Host " 5. Click  Save Changes  — Render will auto-redeploy" -ForegroundColor White
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host " NOTE: Cookies expire. Re-run this script every ~2 weeks." -ForegroundColor Gray
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
