param(
    [string]$ProjectRoot = (Join-Path $PSScriptRoot ".."),
    [ValidateRange(1, 65535)] [int]$PortA = 8765,
    [ValidateRange(1, 65535)] [int]$PortB = 8766,
    [ValidateNotNullOrEmpty()] [string]$NameA = "小明",
    [ValidateNotNullOrEmpty()] [string]$NameB = "小美",
    [switch]$ShowAgentLogs,
    [switch]$DebugCommunicator,
    [string]$DebugCommunicatorAgentId = ""
)

try {
    $utf8ConsoleEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::InputEncoding = $utf8ConsoleEncoding
    [Console]::OutputEncoding = $utf8ConsoleEncoding
    $OutputEncoding = $utf8ConsoleEncoding
} catch {
    # Keep the launcher usable in hosts without a writable console encoding.
}

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root ".venv\Scripts\little-avatar.exe"
if ($PortA -eq $PortB) { throw "PortA and PortB must differ." }
if (-not (Test-Path $python) -or -not (Test-Path $frontend)) { throw "Run uv sync first." }

$launcherLogDirectory = Join-Path $root "logs\dual-avatar"
New-Item -ItemType Directory -Force -Path $launcherLogDirectory | Out-Null
$launcherLog = Join-Path $launcherLogDirectory ("launcher-{0}.jsonl" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

function Write-LauncherLog([string]$Event, [hashtable]$Details = @{}) {
    $entry = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        event = $Event
    }
    foreach ($key in $Details.Keys) { $entry[$key] = $Details[$key] }
    $entry | ConvertTo-Json -Compress -Depth 4 | Add-Content -LiteralPath $launcherLog -Encoding utf8
}

function Get-PortOwner([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $listener) { return $null }
    $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    return [ordered]@{
        pid = $listener.OwningProcess
        process_name = if ($process) { $process.ProcessName } else { "unknown" }
    }
}

function Get-HealthDiagnostic([int]$Port) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/health" -TimeoutSec 1
        return [ordered]@{ status = "response"; http_status = $response.StatusCode; port_owner = Get-PortOwner $Port }
    } catch {
        $httpStatus = $null
        if ($_.Exception.Response) { $httpStatus = [int]$_.Exception.Response.StatusCode }
        return [ordered]@{
            status = "request_failed"
            http_status = $httpStatus
            error_type = $_.Exception.GetType().Name
            error_message = $_.Exception.Message
            port_owner = Get-PortOwner $Port
        }
    }
}

function Start-AvatarBackend([string]$Id, [string]$Identity, [string]$OwnerName, [string]$CommunicatorName, [string]$PeerIdentities, [int]$Port, [string]$Inbound, [string]$Outbound, [string]$Peer, [string]$Profile, [string]$Contact) {
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
    $env:LITTLE_AVATAR_OWNER_NAME = $OwnerName
    $env:LITTLE_AVATAR_COMMUNICATOR_NAME = $CommunicatorName
    $env:LITTLE_AVATAR_A2A_PEER_IDENTITIES = $PeerIdentities
    $env:LITTLE_AVATAR_A2A_BREAKPOINT = $DebugCommunicator.ToString().ToLowerInvariant()
    $env:LITTLE_AVATAR_A2A_BREAKPOINT_AGENT_ID = $DebugCommunicatorAgentId
    $arguments = @("-m", "uvicorn", "p2026_little_avator.api:app", "--host", "127.0.0.1", "--port", "$Port")
    $stdoutLog = Join-Path $launcherLogDirectory "$Id.stdout.log"
    $stderrLog = Join-Path $launcherLogDirectory "$Id.stderr.log"
    $debugThisBackend = $DebugCommunicator -and (-not $DebugCommunicatorAgentId -or $DebugCommunicatorAgentId -eq $Id)
    if ($debugThisBackend -or $ShowAgentLogs) {
        # Pdb and live Agent diagnostics must share this launcher's console. A separate
        # visible window receives EOF for Pdb, while redirected output hides verbose traces.
        $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -NoNewWindow -PassThru
        Write-LauncherLog "backend_started" @{
            avatar_id = $Id
            port = $Port
            pid = $process.Id
            debug = $debugThisBackend
            show_agent_logs = [bool]$ShowAgentLogs
        }
        return $process
    }
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
    Write-LauncherLog "backend_started" @{ avatar_id = $Id; port = $Port; pid = $process.Id; debug = $false; stdout_log = $stdoutLog; stderr_log = $stderrLog }
    return $process
}

$profileA = @{ contacts = @{ $NameB = "avatar-b" } } | ConvertTo-Json -Compress
$profileB = @{ contacts = @{ $NameA = "avatar-a" } } | ConvertTo-Json -Compress
$communicatorA = "${NameA}的秘書"
$communicatorB = "${NameB}的秘書"
$identityA = "MOMO（$communicatorA）"
$identityB = "MOMO（$communicatorB）"
$peerIdentitiesA = @{ "avatar-b" = @{ owner_name = $NameB; communicator_name = $communicatorB } } | ConvertTo-Json -Compress
$peerIdentitiesB = @{ "avatar-a" = @{ owner_name = $NameA; communicator_name = $communicatorA } } | ConvertTo-Json -Compress
$a = $null
$b = $null
Write-LauncherLog "launcher_started" @{
    port_a = $PortA
    port_b = $PortB
    name_a = $NameA
    name_b = $NameB
    show_agent_logs = [bool]$ShowAgentLogs
    debug_communicator = [bool]$DebugCommunicator
}

try {
    foreach ($port in @($PortA, $PortB)) {
        $owner = Get-PortOwner $port
        if ($owner) {
            $diagnostic = Get-HealthDiagnostic $port
            Write-LauncherLog "port_in_use" @{ port = $port; port_owner = $owner; diagnostic = $diagnostic }
            throw "Port $port is already in use by $($owner.process_name) (PID $($owner.pid)). See $launcherLog"
        }
        Write-LauncherLog "port_available" @{ port = $port }
    }

    $a = Start-AvatarBackend "avatar-a" $identityA $NameA $communicatorA $peerIdentitiesA $PortA '{"avatar-b":"b-to-a"}' ("{`"avatar-b`":{`"url`":`"http://127.0.0.1:$PortB/a2a`",`"credential`":`"a-to-b`"}}") "avatar-b" $profileA $NameB
    $b = Start-AvatarBackend "avatar-b" $identityB $NameB $communicatorB $peerIdentitiesB $PortB '{"avatar-a":"a-to-b"}' ("{`"avatar-a`":{`"url`":`"http://127.0.0.1:$PortA/a2a`",`"credential`":`"b-to-a`"}}") "avatar-a" $profileB $NameA

    foreach ($port in @($PortA, $PortB)) {
        $deadline = (Get-Date).AddSeconds(20)
        $ready = $false
        do {
            $health = Get-HealthDiagnostic $port
            $healthLog = @{ port = $port }
            foreach ($key in $health.Keys) { $healthLog[$key] = $health[$key] }
            Write-LauncherLog "health_check" $healthLog
            if ($health.http_status -eq 200) {
                $ready = $true
                break
            }
            Start-Sleep -Milliseconds 200
        } while ((Get-Date) -lt $deadline)
        if (-not $ready) {
            Write-LauncherLog "backend_unhealthy" @{ port = $port; diagnostic = (Get-HealthDiagnostic $port) }
            throw "Avatar backend on port $port did not become healthy. See $launcherLog"
        }
    }
    $env:LITTLE_AVATAR_API_URL = "http://127.0.0.1:$PortA"
    $env:LITTLE_AVATAR_DISPLAY_NAME = $identityA
    $desktopA = Start-Process -FilePath $frontend -WorkingDirectory $root -PassThru
    $env:LITTLE_AVATAR_API_URL = "http://127.0.0.1:$PortB"
    $env:LITTLE_AVATAR_DISPLAY_NAME = $identityB
    $desktopB = Start-Process -FilePath $frontend -WorkingDirectory $root -PassThru
    Write-LauncherLog "desktop_started" @{ avatar_id = "avatar-a"; port = $PortA; pid = $desktopA.Id }
    Write-LauncherLog "desktop_started" @{ avatar_id = "avatar-b"; port = $PortB; pid = $desktopB.Id }
    Write-Host "$identityA=$PortA and $identityB=$PortB are running."
    Wait-Process -Id $desktopA.Id, $desktopB.Id
} catch {
    Write-LauncherLog "launcher_failed" @{ error_type = $_.Exception.GetType().Name; error_message = $_.Exception.Message }
    throw
} finally {
    foreach ($process in @($a, $b)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            Write-LauncherLog "backend_stopped" @{ pid = $process.Id; reason = "launcher_exit" }
        }
    }
    Write-LauncherLog "launcher_stopped" @{}
}
