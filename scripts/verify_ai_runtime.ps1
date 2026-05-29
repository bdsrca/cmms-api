$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string[]]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    & $Command[0] $Command[1..($Command.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $RepoRoot
try {
    Invoke-Step "Python compile check" @(
        $Python,
        "-m",
        "py_compile",
        "app/config.py",
        "app/ai_endpoints.py",
        "app/main.py",
        "app/management_routes.py",
        "app/safety_reviewer.py",
        "app/workflow_trace.py"
    )

    $tests = @(
        "test_ai_runtime_config.py",
        "test_extractor_model_config.py",
        "test_fast_mode_intake_api.py",
        "test_operator_chat_console_static.py",
        "test_safety_reviewer.py"
    )

    foreach ($test in $tests) {
        Invoke-Step "Unit test $test" @(
            $Python,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            $test
        )
    }

    Write-Host ""
    Write-Host "AI runtime verification passed."
}
finally {
    Pop-Location
}
