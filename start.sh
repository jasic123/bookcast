#!/bin/bash

# 快速启动脚本 - 在项目根目录运行

set -e

echo "🚀 启动 Book Podcast Research 系统..."

# 检查 Redis
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis 未启动，请先启动 Redis"
    echo "   Windows: redis-server.exe"
    echo "   Linux/Mac: redis-server"
    exit 1
fi

echo "✅ Redis 运行中"

# 检查后端虚拟环境
if [ ! -d "backend/venv" ]; then
    echo "❌ 后端虚拟环境不存在，请先运行 'cd backend && python -m venv venv && pip install -r requirements.txt'"
    exit 1
fi

# 检查前端依赖
if [ ! -d "frontend/node_modules" ]; then
    echo "❌ 前端依赖未安装，请先运行 'cd frontend && npm install'"
    exit 1
fi

# 启动后端 API
echo "🔧 启动后端 API (端口 8000)..."
cd backend
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 等待后端启动
sleep 3

# 启动 RQ Worker
echo "🔧 启动 RQ Worker..."
cd backend
python worker.py &
WORKER_PID=$!
python worker.py --queue podcast &
PODCAST_WORKER_PID=$!
python worker.py --queue audio &
AUDIO_WORKER_PID=$!
cd ..

# 启动前端
echo "🔧 启动前端 (端口 5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ 所有服务已启动！"
echo ""
echo "📍 访问地址："
echo "   前端: http://localhost:5173"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "⏹️  停止服务: Ctrl+C"

# 等待用户中断
trap "echo ''; echo '🛑 正在停止所有服务...'; kill $BACKEND_PID $WORKER_PID $PODCAST_WORKER_PID $AUDIO_WORKER_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

wait
