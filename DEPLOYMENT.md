# Book Podcast Research - 部署指南

## 环境要求

- Python 3.11+
- Node.js 18+
- Redis (用于任务队列)
- Tavily API Key
- OpenAI-compatible LLM API Key

## 安装步骤

### 1. 解决网络代理问题（如遇到）

如果 pip 安装失败并显示 `ValueError: check_hostname requires server_hostname`，
这通常是代理配置问题。解决方案：

**选项 A：配置代理**
```bash
# 如果使用 HTTP 代理
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port

# 或临时禁用代理
unset HTTP_PROXY
unset HTTPS_PROXY
```

**选项 B：使用国内镜像源**
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**选项 C：离线安装**
在有网络的环境下载依赖包，然后离线安装。

### 2. 后端安装

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys

# 初始化数据库
alembic upgrade head
```

### 3. 前端安装

```bash
cd frontend

# 安装依赖
npm install

# 或使用国内镜像
npm install --registry=https://registry.npmmirror.com
```

### 4. 启动 Redis

**Windows:**
- 下载 Redis for Windows: https://github.com/microsoftarchive/redis/releases
- 启动：`redis-server.exe`

**Linux/Mac:**
```bash
redis-server
```

**或使用 Docker:**
```bash
docker run -d -p 6379:6379 redis:alpine
```

### 5. 启动服务

**启动后端 API:**
```bash
cd backend
source venv/Scripts/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**启动 RQ Worker:**
```bash
cd backend
source venv/Scripts/activate
python worker.py
```

**启动前端:**
```bash
cd frontend
npm run dev
```

### 6. 访问应用

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

## 验证安装

### 测试后端 API
```bash
curl http://localhost:8000/api/books/lists
```

### 测试数据库
```bash
cd backend
source venv/Scripts/activate
alembic current
```

应显示当前迁移版本：`001 (head)`

### 测试 Redis 连接
```bash
redis-cli ping
```

应返回：`PONG`

## 常见问题

### Q: pip 安装时出现代理错误
**A:** 参考上面的"解决网络代理问题"部分

### Q: alembic upgrade head 失败
**A:** 确保 .env 中的 DATABASE_URL 配置正确，数据库文件目录有写权限

### Q: RQ worker 无法连接 Redis
**A:** 检查 Redis 是否启动，.env 中的 REDIS_URL 是否正确

### Q: 前端无法连接后端 API
**A:** 
1. 确认后端在 8000 端口运行
2. 检查 vite.config.ts 中的 proxy 配置
3. 查看浏览器控制台的网络请求错误

### Q: Tavily 或 LLM API 调用失败
**A:** 
1. 确认 API Key 正确填入 .env
2. 检查 API Key 是否有额度
3. 查看后端日志中的详细错误信息

## 生产环境部署

生产环境部署建议使用：
- Gunicorn + Uvicorn workers (后端)
- Nginx (反向代理)
- Supervisor 或 systemd (进程管理)
- Docker Compose (容器化部署)

详见项目根目录的 `docker-compose.yml`（待完善）
