$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = $null
foreach ($candidate in @('D:/miniconda/envs/book-podcast/python.exe', (Join-Path $backend 'venv/Scripts/python.exe'))) {
    if (-not (Test-Path $candidate)) { continue }
    & $candidate -c 'import fastapi, redis, rq, sqlalchemy' 2>$null
    if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
}
if (-not $python) { throw '找不到后端 Python 环境。请先安装 backend/requirements.txt。' }
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npm -or -not (Test-Path (Join-Path $frontend 'node_modules'))) {
    throw '找不到 npm 或前端依赖。请先在 frontend 运行 npm install。'
}

function Test-Port([int]$port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try { return $client.ConnectAsync('127.0.0.1', $port).Wait(500) -and $client.Connected }
    catch { return $false }
    finally { $client.Dispose() }
}

function Wait-Port([int]$port) {
    for ($i = 0; $i -lt 45; $i++) {
        if (Test-Port $port) { return }
        Start-Sleep -Seconds 1
    }
    throw "端口 $port 启动超时。"
}

if (-not (Test-Port 6379)) {
    $redis = (Get-Command redis-server.exe -ErrorAction SilentlyContinue).Source
    if ($redis) { Start-Process -FilePath $redis -WindowStyle Hidden | Out-Null }
    else {
        $service = Get-Service -Name Redis -ErrorAction SilentlyContinue
        if (-not $service) { throw 'Redis 未启动，也找不到 redis-server.exe 或 Redis 服务。' }
        Start-Service -Name Redis
    }
}
Wait-Port 6379

$logs = Join-Path $backend 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if (-not (Test-Port 8000)) {
    Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' `
        -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'api.out.log') `
        -RedirectStandardError (Join-Path $logs 'api.err.log') | Out-Null
}
Wait-Port 8000

Push-Location $backend
try {
    $activeQueues = & $python -c "from app.core.queue import redis_conn; from rq import Worker; print(' '.join({q.name for w in Worker.all(connection=redis_conn) if redis_conn.ttl(w.key) > 0 for q in w.queues}))"
    if ($LASTEXITCODE -ne 0) { throw '无法检查 Worker 状态。' }
} finally {
    Pop-Location
}
foreach ($queue in @('research', 'podcast', 'audio')) {
    if (($activeQueues -split '\s+') -contains $queue) { continue }
    Start-Process -FilePath $python -ArgumentList 'worker.py','--queue',$queue -WorkingDirectory $backend `
        -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "$queue.out.log") `
        -RedirectStandardError (Join-Path $logs "$queue.err.log") | Out-Null
}
if (-not (Test-Port 5173)) {
    Start-Process -FilePath $env:ComSpec -ArgumentList '/c',("`"$npm`" run dev") -WorkingDirectory $frontend -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs 'vite.out.log') `
        -RedirectStandardError (Join-Path $logs 'vite.err.log') | Out-Null
}
Wait-Port 5173

for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-RestMethod 'http://127.0.0.1:8000/health/deep' -TimeoutSec 3
        if ($response.status -eq 'healthy') {
            Start-Process 'http://127.0.0.1:5173/'
            Write-Host 'Redis、API、3 个 Worker 和前端均已就绪。'
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 1
}
throw "服务未全部就绪，请查看 $logs 下的日志。"
