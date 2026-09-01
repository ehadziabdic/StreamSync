# CONFIGURATION
$GITHUB_TOKEN = "your-hithub-token-here"  # Replace with your actual GitHub token
$GIST_ID = "your-gist-id-here"  # Replace with your actual Gist ID
$GITHUB_USER = "your-github-username-here"  # Replace with your actual GitHub username
$GITHUB_REPO = "StreamSync"

Write-Host "    -> Waiting for network to stabilize..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Extract Cloudflare Tunnel URL
Write-Host "    -> Extracting Cloudflare Tunnel URL..." -ForegroundColor Yellow
$logs = docker compose logs cloudflared
$tunnelUrl = ($logs | Select-String -Pattern "https://[a-z-]+\.trycloudflare\.com").Matches.Value | Select-Object -Last 1

if (-not $tunnelUrl) {
    Write-Host ""
    Write-Host "        -> ERROR: Could not find tunnel URL in logs" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "        -> Found Cloudflare URL:" -ForegroundColor Green
Write-Host "           $tunnelUrl" -ForegroundColor Cyan

# Update Gist
Write-Host "    -> Updating GitHub Gist..." -ForegroundColor Yellow

$headers = @{
    "Authorization" = "token $GITHUB_TOKEN"
    "Accept" = "application/vnd.github.v3+json"
}

$newContent = @{
    url = $tunnelUrl
} | ConvertTo-Json

$body = @{
    description = "Stremio Cloudflare Tunnel URL - Auto-updated"
    files = @{
        "stremio-url.json" = @{
            content = $newContent
        }
    }
} | ConvertTo-Json -Depth 3

try {
    Invoke-RestMethod -Uri "https://api.github.com/gists/$GIST_ID" -Method Patch -Headers $headers -Body $body -ContentType "application/json" | Out-Null
    Write-Host "        -> Gist updated successfully!" -ForegroundColor Green
    
    $timestamp = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
    $gistRawUrl = "https://gist.githubusercontent.com/$GITHUB_USER/$GIST_ID/raw/stremio-url.json?t=$timestamp"
    Write-Host "        -> Gist URL:" -ForegroundColor Green
    Write-Host "           $gistRawUrl" -ForegroundColor Cyan
}
catch {
    Write-Host ""
    Write-Host "        -> ERROR: Failed to update Gist" -ForegroundColor Red
    Write-Host "           $_" -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

# URLs
$permanentUrl = "https://$GITHUB_USER.github.io/$GITHUB_REPO/"

# Show permanent URL
Write-Host "    -> Permanent redirect URL:" -ForegroundColor Yellow
Write-Host "       $permanentUrl" -ForegroundColor Cyan

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "    SERVER READY" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "    -> Cloudflare URL:  $tunnelUrl" -ForegroundColor Cyan
Write-Host "    -> Gist URL:        $gistRawUrl" -ForegroundColor Cyan
Write-Host "    -> Local URL:       $permanentUrl" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
Write-Host ""