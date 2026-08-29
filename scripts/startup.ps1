param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $ProjectRoot.Trim().Trim('"')
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root ".venv\Scripts\p2026-little-avator.exe"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $frontend)) {
    throw "The project virtual environment is incomplete. Run uv sync again."
}

try {
    $existing = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8765/health" -TimeoutSec 1
    if ($existing.StatusCode -eq 200) {
        throw "An API is already running on port 8765. Stop the old API before using the single-console launcher."
    }
} catch [System.Net.WebException] {
    # No local API is listening. The supervisor can safely create one.
}

$backendProcess = $null
$frontendProcess = $null
$stdoutLog = Join-Path ([System.IO.Path]::GetTempPath()) ("momo-api-{0}.stdout.log" -f [guid]::NewGuid())
$stderrLog = Join-Path ([System.IO.Path]::GetTempPath()) ("momo-api-{0}.stderr.log" -f [guid]::NewGuid())
$stdoutPosition = 0L
$stderrPosition = 0L

function Show-NewApiLines {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [ref]$Position
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite
    )

    try {
        if ($Position.Value -gt $stream.Length) {
            $Position.Value = 0L
        }

        $null = $stream.Seek($Position.Value, [System.IO.SeekOrigin]::Begin)
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.UTF8Encoding]::new($false), $true, 1024, $true)
        try {
            while (($line = $reader.ReadLine()) -ne $null) {
                Write-Host "[API] $line"
            }
            $Position.Value = $stream.Position
        } finally {
            $reader.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
}

function Show-NewApiOutput {
    Show-NewApiLines -Path $stdoutLog -Position ([ref]$stdoutPosition)
    Show-NewApiLines -Path $stderrLog -Position ([ref]$stderrPosition)
}

try {
    $backendProcess = Start-Process `
        -FilePath $python `
        -ArgumentList @("-u", "-m", "uvicorn", "p2026_little_avator.api:app", "--host", "127.0.0.1", "--port", "8765") `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -PassThru

    $deadline = (Get-Date).AddSeconds(30)
    do {
        Show-NewApiOutput
        try {
            $health = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8765/health" -TimeoutSec 1
            if ($health.StatusCode -eq 200) {
                break
            }
        } catch [System.Net.WebException] {
            Start-Sleep -Milliseconds 250
        }

        if ($backendProcess.HasExited) {
            Show-NewApiOutput
            throw "The API exited before it became healthy."
        }
    } while ((Get-Date) -lt $deadline)

    if ($health.StatusCode -ne 200) {
        throw "The API did not become healthy within 10 seconds."
    }

    $frontendProcess = Start-Process -FilePath $frontend -WorkingDirectory $root -WindowStyle Hidden -PassThru
    Write-Host "Momo is running. Close Momo or press Ctrl+C here to stop both processes."
    Write-Host "API and Akasha verbose output will appear below."

    while (-not $frontendProcess.HasExited) {
        Show-NewApiOutput

        if ($backendProcess.HasExited) {
            Show-NewApiOutput
            throw "The API exited unexpectedly."
        }

        Start-Sleep -Milliseconds 150
    }

    Show-NewApiOutput
} finally {
    foreach ($process in @($frontendProcess, $backendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }

    foreach ($path in @($stdoutLog, $stderrLog)) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
}
