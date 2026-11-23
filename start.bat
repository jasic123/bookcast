@echo off
REM 快速启动脚本 - Windows 版本

echo 🚀 启动 Book Podcast Research 系统...

REM 检查 Redis
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Redis 未启动，请先启动 Redis
    echo    运行: redis-server.exe
    exit /b 1
)

echo ✅ Redis 运行中

REM 检查后端虚拟环境
if not exist "backend\venv" (
    echo ❌ 后端虚拟环境不存在
    echo    请先运行: cd backend ^&^& python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
    exit /b 1
)

REM 检查前端依赖
if not exist "frontend\node_modules" (
    echo ❌ 前端依赖未安装
    echo    请先运行: cd frontend ^&^& npm install
    exit /b 1
)

echo.
echo 🔧 启动服务...
echo.

REM 启动后端 API
start "Backend API" cmd /k "cd backend && venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动 RQ Worker
start "RQ Worker" cmd /k "cd backend && venv\Scripts\activate && python worker.py"
start "Podcast Worker" cmd /k "cd backend && venv\Scripts\activate && python worker.py --queue podcast"
start "Audio Worker" cmd /k "cd backend && venv\Scripts\activate && python worker.py --queue audio"

REM 启动前端
start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ✅ 所有服务已启动！
echo.
echo 📍 访问地址：
echo    前端: http://localhost:5173
echo    API 文档: http://localhost:8000/docs
echo.
echo ⏹️  关闭窗口即可停止对应服务
echo.

pause
