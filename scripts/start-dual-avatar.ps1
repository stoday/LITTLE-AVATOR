param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
    [ValidateRange(1, 65535)] [int]$PortA = 8765,
    [ValidateRange(1, 65535)] [int]$PortB = 8766,
    [ValidateNotNullOrEmpty()] [string]$NameA = "Alice",
    [ValidateNotNullOrEmpty()] [string]$NameB = "Xiaomei",
    [switch]$DebugCommunicator,
    [string]$DebugCommunicatorAgentId = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root ".venv\Scripts\little-avatar.exe"
if ($PortA -eq $PortB) { throw "PortA and PortB must differ." }
if (-not (Test-Path $python) -or -not (Test-Path $frontend)) { throw "Run uv sync first." }

function Start-AvatarBackend([string]$Id, [string]$Identity, [int]$Port, [string]$Inbound, [string]$Outbound, [string]$Peer, [string]$Profile, [string]$Contact) {
    $dataDirectory = Join-Path $root "data\dual-avatar\$Id"
    $scheduleTemplateRelativePath = if ($Id -eq "avatar-a") { "docs\dual-avatar-schedules\avatar-a.schedule.md" } else { "docs\dual-avatar-schedules\avatar-b.schedule.md" }
    $scheduleTemplate = Join-Path $root $scheduleTemplateRelativePath
    $schedulePath = Join-Path $dataDirectory "schedule.md"
    New-Item -ItemType Directory -Force -Path $dataDirectory | Out-Null
    if (-not (Test-Path -LiteralPath $schedulePath)) {
        Copy-Item -LiteralPath $scheduleTemplate -Destination $schedulePath
    }
    $env:LITTLE_AVATAR_A2A_AGENT_ID = $Id
    $env:LITTLE_AVATAR_A2A_DB = (Join-Path $root "data\dual-avatar\$Id\a2a.db")
    $env:LITTLE_AVATAR_DATA_DIR = $dataDirectory
    $env:LITTLE_AVATAR_A2A_PEERS = $Inbound
    $env:LITTLE_AVATAR_A2A_OUTBOUND_PEERS = $Outbound
    $env:LITTLE_AVATAR_A2A_DEFAULT_PEER = $Peer
    $env:LITTLE_AVATAR_ADMIN_PROFILE = $Profile
    $env:LITTLE_AVATAR_ADMIN_DEFAULT_CONTACT = $Contact
    $env:LITTLE_AVATAR_IDENTITY = $Identity
    $env:LITTLE_AVATAR_A2A_BREAKPOINT = $DebugCommunicator.ToString().ToLowerInvariant()
    $env:LITTLE_AVATAR_A2A_BREAKPOINT_AGENT_ID = $DebugCommunicatorAgentId
    $arguments = @("-m", "uvicorn", "p2026_little_avator.api:app", "--host", "127.0.0.1", "--port", "$Port")
    $debugThisBackend = $DebugCommunicator -and (-not $DebugCommunicatorAgentId -or $DebugCommunicatorAgentId -eq $Id)
    if ($debugThisBackend) {
        # Pdb needs the launcher's stdin; a separate visible window receives EOF and exits immediately.
        return Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -NoNewWindow -PassThru
    }
    return Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru
}

$profileA = @{ contacts = @{ $NameB = "avatar-b" } } | ConvertTo-Json -Compress
$profileB = @{ contacts = @{ $NameA = "avatar-a" } } | ConvertTo-Json -Compress
$identityA = "$NameA's Momo (initiator)"
$identityB = "$NameB's Momo (invitee)"
$a = Start-AvatarBackend "avatar-a" $identityA $PortA '{"avatar-b":"b-to-a"}' ("{`"avatar-b`":{`"url`":`"http://127.0.0.1:$PortB/a2a`",`"credential`":`"a-to-b`"}}") "avatar-b" $profileA $NameB
$b = Start-AvatarBackend "avatar-b" $identityB $PortB '{"avatar-a":"a-to-b"}' ("{`"avatar-a`":{`"url`":`"http://127.0.0.1:$PortA/a2a`",`"credential`":`"b-to-a`"}}") "avatar-a" $profileB $NameA

try {
    foreach ($port in @($PortA, $PortB)) {
        $deadline = (Get-Date).AddSeconds(20)
        $ready = $false
        do {
            try {
                if ((Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/health" -TimeoutSec 1).StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            } catch { Start-Sleep -Milliseconds 200 }
        } while ((Get-Date) -lt $deadline)
        if (-not $ready) { throw "Avatar backend on port $port did not become healthy." }
    }
    $env:LITTLE_AVATAR_API_URL = "http://127.0.0.1:$PortA"
    $env:LITTLE_AVATAR_DISPLAY_NAME = $identityA
    $desktopA = Start-Process -FilePath $frontend -WorkingDirectory $root -PassThru
    $env:LITTLE_AVATAR_API_URL = "http://127.0.0.1:$PortB"
    $env:LITTLE_AVATAR_DISPLAY_NAME = $identityB
    $desktopB = Start-Process -FilePath $frontend -WorkingDirectory $root -PassThru
    Write-Host "$identityA=$PortA and $identityB=$PortB are running."
    Wait-Process -Id $desktopA.Id, $desktopB.Id
} finally {
    foreach ($process in @($a, $b)) { if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force } }
}
