$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Check-Exit($step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed (exit code $LASTEXITCODE)." }
}

& docker info --format '{{.ServerVersion}}' | Out-Null
Check-Exit 'Docker Engine check'

# Pull sequentially so an unreliable proxy does not handle several Hub auth requests at once.
$localImages = & docker image ls --format '{{.Repository}}:{{.Tag}}'
Check-Exit 'Local image listing'
foreach ($image in @('redis:7-alpine', 'python:3.11-slim-bookworm', 'node:24-bookworm-slim', 'node:20-alpine', 'nginx:1.27-alpine')) {
    if ($localImages -contains $image) { continue }
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        & docker pull $image
        if ($LASTEXITCODE -eq 0) { break }
        if ($attempt -lt 3) { Start-Sleep -Seconds (3 * $attempt) }
    }
    Check-Exit "Pulling $image"
}

$source = Join-Path $PSScriptRoot 'backend\book_research.db'
$snapshot = Join-Path $PSScriptRoot 'backend\book_research.docker-import.db'
$dataVolume = 'bookcast_bookcast_data'
$audioVolume = 'bookcast_bookcast_audio'

& docker volume create $dataVolume | Out-Null
Check-Exit 'Database volume creation'
& docker volume create $audioVolume | Out-Null
Check-Exit 'Audio volume creation'

& docker run --rm --mount "type=volume,source=$dataVolume,target=/data" redis:7-alpine sh -c 'test -f /data/book_research.db'
$hasDatabase = $LASTEXITCODE -eq 0

if (-not $hasDatabase -and (Test-Path -LiteralPath $source)) {
    $python = (Get-Command python -ErrorAction Stop).Source
    $backupCode = @'
import sqlite3, sys
source = sqlite3.connect(sys.argv[1], timeout=30)
target = sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
result = target.execute('PRAGMA integrity_check').fetchone()[0]
target.close()
source.close()
if result != 'ok':
    raise SystemExit('SQLite integrity check failed: ' + result)
'@
    & $python -c $backupCode $source $snapshot
    Check-Exit 'SQLite snapshot'
    & docker run --rm --mount "type=volume,source=$dataVolume,target=/data" --mount "type=bind,source=$snapshot,target=/source.db,readonly" redis:7-alpine sh -c 'cp /source.db /data/book_research.db'
    Check-Exit 'Database import'

    $audioSource = Join-Path $PSScriptRoot 'backend\generated_audio'
    if (Get-ChildItem -LiteralPath $audioSource -Filter 'podcast-*.wav' -File -ErrorAction SilentlyContinue | Select-Object -First 1) {
        & docker run --rm --mount "type=volume,source=$audioVolume,target=/audio" --mount "type=bind,source=$audioSource,target=/source,readonly" redis:7-alpine sh -c 'cp /source/podcast-*.wav /audio/'
        Check-Exit 'Audio import'
    }
    Write-Host "Imported a consistent database snapshot and old podcast audio. Backup: $snapshot"
} elseif ($hasDatabase) {
    Write-Host 'Existing Docker database found; keeping its data.'
} else {
    Write-Host 'No Windows database found; Docker will create a new database.'
}

& docker compose up --build -d
Check-Exit 'Docker Compose startup'

for ($attempt = 1; $attempt -le 60; $attempt++) {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:5173/api/health/deep' -TimeoutSec 3
        if ($health.status -eq 'healthy') {
            & docker compose ps
            Write-Host 'Bookcast is ready: http://127.0.0.1:5173'
            Start-Process 'http://127.0.0.1:5173'
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 3
}

& docker compose ps
& docker compose logs --tail=80 api research-worker podcast-worker audio-worker
throw 'Services did not become healthy. Check the logs above.'
