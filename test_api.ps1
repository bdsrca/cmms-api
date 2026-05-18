$BaseUrl = "http://localhost:8000"
$ApiKey = "my-secret-key"

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
$ValidBuildings = @("ARC", "CAMPUSVIEW", "ZONE-18")
$ValidPriorities = @("LOW", "NORMAL", "URGENT")

Write-Section "1. Health"
Invoke-Api -Method "GET" -Path "/health"

Write-Section "2. Summarize work order"
Invoke-Api -Method "POST" -Path "/api/ai/summarize-work-order" -Headers $AuthHeaders -Body @{
    text = "The air conditioner in ARC room 205 is making loud noise and the room is too warm."
}

Write-Section "3. Extract complete HVAC request"
Invoke-Api -Method "POST" -Path "/api/ai/extract-work-order-fields" -Headers $AuthHeaders -Body @{
    text = "The air conditioner in ARC room 205 is making loud noise and the room is too warm."
    valid_buildings = $ValidBuildings
    valid_priorities = $ValidPriorities
}

Write-Section "4. CMMS intake complete HVAC request"
Invoke-Api -Method "POST" -Path "/api/ai/cmms-intake" -Headers $AuthHeaders -Body @{
    text = "The air conditioner in ARC room 205 is making loud noise and the room is too warm."
    valid_buildings = $ValidBuildings
    valid_priorities = $ValidPriorities
}

Write-Section "5. CMMS intake ambiguous request"
Write-Host "Expected: request_type probably HVAC, building null, room null, needs_human_review true, missing_fields includes building and room, can_create_work_order false."
Invoke-Api -Method "POST" -Path "/api/ai/cmms-intake" -Headers $AuthHeaders -Body @{
    text = "The room is too hot."
    valid_buildings = $ValidBuildings
    valid_priorities = $ValidPriorities
}

Write-Section "6. Invalid API key"
Write-Host "Expected: 401"
Invoke-Api -Method "POST" -Path "/api/ai/summarize-work-order" -Headers @{ "x-api-key" = "wrong-key" } -Body @{
    text = "This should fail because the API key is invalid."
}
