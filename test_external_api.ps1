# Cloudflare Tunnel external test.
# Set this to the generated https://*.trycloudflare.com URL from:
# cloudflared tunnel --url http://localhost:8000
$BaseUrl = "https://replace-with-your-trycloudflare-url.trycloudflare.com"

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $Line = $_.Trim()
        if (-not $Line -or $Line.StartsWith("#") -or -not $Line.Contains("=")) { return }
        $Name, $Value = $Line.Split("=", 2)
        if ($Name.Trim() -eq "LLM_API_KEY" -and -not $env:LLM_API_KEY) {
            $env:LLM_API_KEY = $Value.Trim().Trim('"')
        }
    }
}

Import-DotEnv (Join-Path $PSScriptRoot ".env")
$ApiKey = if ($env:LLM_API_KEY) { $env:LLM_API_KEY } else { "my-secret-key" }

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Invoke-Api {
    param(
        [string]$Method,
        [string]$Path,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )

    try {
        $params = @{
            Method = $Method
            Uri = "$BaseUrl$Path"
            Headers = $Headers
        }

        if ($null -ne $Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 10)
            $params.ContentType = "application/json"
        }

        $response = Invoke-RestMethod @params
        $response | ConvertTo-Json -Depth 10
    }
    catch {
        Write-Host "Request failed:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        if ($_.ErrorDetails.Message) {
            Write-Host $_.ErrorDetails.Message -ForegroundColor Yellow
        }
    }
}

$AuthHeaders = @{ "x-api-key" = $ApiKey }

Write-Section "External health"
Invoke-Api -Method "GET" -Path "/health"

Write-Section "External CMMS intake"
Invoke-Api -Method "POST" -Path "/api/ai/cmms-intake" -Headers $AuthHeaders -Body @{
    text = "The air conditioner in ARC room 205 is making loud noise and the room is too warm."
    valid_buildings = @("ARC", "CAMPUSVIEW", "ZONE-18")
    valid_priorities = @("LOW", "NORMAL", "URGENT")
}
