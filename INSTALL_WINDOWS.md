# Windows 安装指南

## 前置要求

1. **Python 3.11+**
   - 下载：https://www.python.org/downloads/
   - 安装时勾选 "Add Python to PATH"

2. **Node.js 18+**
   - 下载：https://nodejs.org/
   - 推荐下载 LTS 版本

3. **Redis**
   - 下载：https://github.com/tporadowski/redis/releases
   - 下载 Redis-x64-xxx.zip
   - 解压到任意目录（如 `C:\Redis`）

4. **API Keys**
   - Tavily API Key：https://tavily.com/
   - OpenAI-compatible LLM API Key

---

## 安装步骤

### 1. 下载项目

```bash
# 如果已克隆项目，跳过此步
git clone <repository-url>
cd book-podcast-research
```

### 2. 安装后端依赖

打开 PowerShell 或命令提示符：

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 如果遇到网络代理错误，使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或者正常安装（如果网络正常）
pip install -r requirements.txt
```

**如果仍然失败，尝试：**
```bash
# 临时禁用代理
set HTTP_PROXY=
set HTTPS_PROXY=
pip install -r requirements.txt
```

### 3. 配置后端环境变量

```bash
# 复制环境变量模板
copy .env.example .env

# 用记事本或 VSCode 编辑 .env
notepad .env
```

**必须填写的配置：**
```
TAVILY_API_KEY=你的_tavily_api_key
LLM_API_KEY=你的_llm_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4-turbo-preview
```

### 4. 初始化数据库

```bash
# 确保在 backend 目录，虚拟环境已激活
alembic upgrade head
```

如果成功，会看到：
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial schema
```

### 5. 安装前端依赖

打开新的命令行窗口：

```bash
cd frontend

# 使用国内镜像（推荐）
npm install --registry=https://registry.npmmirror.com

# 或者正常安装
npm install
```

### 6. 启动 Redis

打开新的命令行窗口：

```bash
# 进入 Redis 目录
cd C:\Redis

# 启动 Redis 服务器
redis-server.exe
```

保持此窗口打开。如果看到 Redis ASCII logo，说明启动成功。

---

## 启动服务

现在需要启动 3 个服务。

### 方式一：使用启动脚本（推荐）

双击项目根目录的 `start.bat`，会自动启动所有服务。

### 方式二：手动启动

**窗口 1 - 后端 API：**
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**窗口 2 - RQ Worker：**
```bash
cd backend
venv\Scripts\activate
python worker.py
```

**窗口 3 - 前端：**
```bash
cd frontend
npm run dev
```

---

## 访问应用

打开浏览器访问：

- **前端界面**：http://localhost:5173
- **API 文档**：http://localhost:8000/docs
- **ReDoc**：http://localhost:8000/redoc

---

## 验证安装

### 1. 测试后端 API

打开浏览器访问：http://localhost:8000/docs

应该看到 Swagger UI 界面。

### 2. 测试数据库

```bash
cd backend
venv\Scripts\activate
alembic current
```

应显示：`001 (head)`

### 3. 测试 Redis

```bash
redis-cli ping
```

应返回：`PONG`

### 4. 测试前端

访问 http://localhost:5173，应该看到首页：
- 标题："播客制作前端流程验证系统"
- 导航栏："播客研究系统" 和 "书单管理"

---

## 常见问题

### ❌ pip 安装失败：`ValueError: check_hostname requires server_hostname`

**原因：** 网络代理配置问题

**解决方案：**
```bash
# 方案 1：使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 方案 2：临时禁用代理
set HTTP_PROXY=
set HTTPS_PROXY=
pip install -r requirements.txt

# 方案 3：配置代理（如果使用代理）
set HTTP_PROXY=http://你的代理地址:端口
set HTTPS_PROXY=http://你的代理地址:端口
pip install -r requirements.txt
```

### ❌ alembic upgrade head 失败

**检查项：**
1. 是否在 backend 目录下？
2. 虚拟环境是否激活？（命令行前面有 `(venv)` 标识）
3. `.env` 文件是否存在？

### ❌ Redis 无法启动

**解决方案：**
1. 检查是否已经有 Redis 在运行：
   ```bash
   redis-cli ping
   ```
2. 如果端口被占用，修改 Redis 配置文件 `redis.conf`：
   ```
   port 6380
   ```
   然后在 `.env` 中修改：
   ```
   REDIS_URL=redis://localhost:6380/0
   ```

### ❌ npm install 失败

**解决方案：**
```bash
# 清理缓存
npm cache clean --force

# 使用国内镜像
npm install --registry=https://registry.npmmirror.com
```

### ❌ 前端无法连接后端

**检查项：**
1. 后端是否在 8000 端口运行？访问 http://localhost:8000/docs
2. 查看浏览器控制台（F12）的 Network 标签页
3. 检查 [vite.config.ts](frontend/vite.config.ts#L9-L12) 的 proxy 配置

### ❌ RQ Worker 无法连接 Redis

**检查项：**
1. Redis 是否运行？
   ```bash
   redis-cli ping
   ```
2. `.env` 中的 `REDIS_URL` 是否正确？
   ```
   REDIS_URL=redis://localhost:6379/0
   ```

---

## 下一步

安装完成后，可以：

1. **查看开发文档**：[DEVELOPMENT.md](DEVELOPMENT.md)
2. **开始使用系统**：
   - 访问 http://localhost:5173
   - 点击"书单管理"
   - 尝试获取 Amazon 书单或上传 CSV
   - 选择一本书开始研究

3. **查看 API 文档**：http://localhost:8000/docs

---

## 停止服务

- 在每个命令行窗口按 `Ctrl+C`
- 或直接关闭窗口
- Redis 可以保持运行，不影响系统

---

## 需要帮助？

遇到问题请查看：
- [README.md](README.md) - 项目概述
- [DEPLOYMENT.md](DEPLOYMENT.md) - 部署指南
- [DEVELOPMENT.md](DEVELOPMENT.md) - 开发指南
