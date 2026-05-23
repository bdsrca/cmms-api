$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$ApiUrl = "http://127.0.0.1:8000"
$UiUrl = "$ApiUrl/ui"
$OllamaUrl = "http://localhost:11434"
$ModelName = "qwen3:8b"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "cmms-llm-api.log"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $Line = $_.Trim()
        if (-not $Line -or $Line.StartsWith("#")) {
            return
        }

        $Parts = $Line.Split("=", 2)
        if ($Parts.Count -ne 2) {
            return
        }

        $Name = $Parts[0].Trim()
        $Value = $Parts[1].Trim().Trim('"').Trim("'")
        if ($Name -and -not [Environment]::GetEnvironmentVariable($Name, "Process")) {
            [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
        }
    }
}

function Write-Log {
    param([string]$Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "$Timestamp INFO launcher $Message"
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message ==" -ForegroundColor Cyan
    Write-Log $Message
}

Import-DotEnv (Join-Path $ProjectRoot ".env")

function Get-OllamaTags {
    try {
        return Invoke-RestMethod -Method GET -Uri "$OllamaUrl/api/tags" -TimeoutSec 5
    }
    catch {
        return $null
    }
}

function Start-OllamaIfNeeded {
    $Tags = Get-OllamaTags
    if ($null -ne $Tags) {
        Write-Log "ollama_already_running"
        return $Tags
    }

    Write-Host "Ollama is not responding at $OllamaUrl. Trying to start Ollama..."
    Write-Log "ollama_start_attempt"

    $OllamaCommand = Get-Command "ollama" -ErrorAction SilentlyContinue
    if (-not $OllamaCommand) {
        Write-Host "Could not find ollama.exe on PATH." -ForegroundColor Red
        Write-Host "Start Ollama manually, then run this launcher again." -ForegroundColor Yellow
        Write-Log "ollama_not_found"
        return $null
    }

    Start-Process -FilePath $OllamaCommand.Source -ArgumentList "serve" -WindowStyle Hidden

    for ($Attempt = 1; $Attempt -le 15; $Attempt++) {
        Start-Sleep -Seconds 1
        $Tags = Get-OllamaTags
        if ($null -ne $Tags) {
            Write-Host "Ollama started."
            Write-Log "ollama_started"
            return $Tags
        }
    }

    Write-Host "Ollama did not become ready after 15 seconds." -ForegroundColor Red
    Write-Log "ollama_start_timeout"
    return $null
}

if (-not $env:LLM_API_KEY) {
    Write-Host "LLM_API_KEY must be set before startup." -ForegroundColor Red
    Write-Host "Example:" -ForegroundColor Yellow
    Write-Host '  $env:LLM_API_KEY="use-a-long-unique-api-key"' -ForegroundColor Yellow
    Write-Log "llm_api_key_missing"
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not $env:LOCAL_CONTROL_API_KEY) {
    Write-Host "LOCAL_CONTROL_API_KEY is not set. Portal system controls will be disabled until it is set." -ForegroundColor Yellow
    Write-Host '  $env:LOCAL_CONTROL_API_KEY="use-a-separate-local-control-key"' -ForegroundColor Yellow
    Write-Log "local_control_api_key_missing"
}

if (-not $env:ADMIN_USERNAME -or -not $env:ADMIN_PASSWORD) {
    Write-Host "ADMIN_USERNAME and ADMIN_PASSWORD must be set before startup." -ForegroundColor Red
    Write-Host "Example:" -ForegroundColor Yellow
    Write-Host '  $env:ADMIN_USERNAME="admin"' -ForegroundColor Yellow
    Write-Host '  $env:ADMIN_PASSWORD="use-a-long-unique-password"' -ForegroundColor Yellow
    Write-Log "admin_env_missing"
    Read-Host "Press Enter to exit"
    exit 1
}

if ($env:ADMIN_PASSWORD -eq "change-this-password" -or $env:ADMIN_PASSWORD.Length -lt 12) {
    Write-Host "ADMIN_PASSWORD is too weak or still uses the old default." -ForegroundColor Red
    Write-Host "Use a long unique password before starting the portal." -ForegroundColor Yellow
    Write-Log "admin_password_rejected"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Step "Checking Python environment"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating .venv..."
    Write-Log "creating_venv"
    python -m venv .venv
}

$ImportCheck = @"
import fastapi
import httpx
import pydantic
import uvicorn
"@

try {
    $ImportCheck | & $VenvPython -
}
catch {
    Write-Host "Installing Python requirements..."
    Write-Log "installing_requirements"
    & $VenvPython -m pip install -r requirements.txt
}

Write-Step "Checking Ollama"
$Tags = Start-OllamaIfNeeded
if ($null -eq $Tags) {
    Write-Host "Ollama is not responding at $OllamaUrl." -ForegroundColor Red
    Write-Host "Start Ollama manually, then run:" -ForegroundColor Yellow
    Write-Host "  ollama run $ModelName" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

$ModelAvailable = $false
foreach ($Model in $Tags.models) {
    if ($Model.name -eq $ModelName) {
        $ModelAvailable = $true
        break
    }
}

if (-not $ModelAvailable) {
    Write-Host "Model $ModelName was not found in Ollama." -ForegroundColor Red
    Write-Log "model_missing model=$ModelName"
    Write-Host "Run this first:" -ForegroundColor Yellow
    Write-Host "  ollama pull $ModelName" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Step "Starting local CMMS LLM API"
Write-Host "API: $ApiUrl"
Write-Host "UI:  $UiUrl"
Write-Host "API key: loaded from environment/.env"
Write-Host ""
Write-Host "Cloudflare Tunnel is not started automatically."
Write-Host "Press Ctrl+C in this window to stop the API."

Start-Job -ScriptBlock {
    param($Url)
    Start-Sleep -Seconds 3
    Start-Process $Url
} -ArgumentList $UiUrl | Out-Null

try {
    Write-Log "uvicorn_start host=127.0.0.1 port=8000"
    & $VenvPython -m uvicorn main:app --host 127.0.0.1 --port 8000
}
finally {
    Write-Log "uvicorn_stopped"
}
