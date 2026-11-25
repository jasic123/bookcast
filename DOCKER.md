# Docker 本机部署

当前 Compose 将 Web 仅绑定到 `127.0.0.1:5173`，供本机使用。首次部署推荐在项目根目录用 Windows PowerShell 运行：

`powershell -ExecutionPolicy Bypass -File .\deploy-local.ps1`

脚本会用 SQLite 在线备份生成一致性快照，首次创建 Docker 数据卷时导入旧数据库和已生成的播客 WAV，构建镜像、启动容器，等待 API、Redis 和三个 Worker 健康后打开浏览器。若数据卷里已有数据库，脚本保留该数据库。备份文件保留在 `backend/book_research.docker-import.db`。之后更新代码可运行 `docker compose up --build -d`。

首次使用前，在 `backend/.env` 设置 `AUTH_REGISTRATION_CODE`、模型/搜索/TTS 密钥；不要提交该文件。打开 `http://127.0.0.1:5173`，点“创建账号”。**首个注册账号会认领此前无账户的书单、主题搜索和其下的研究/播客记录**。此前成功使用的自制音色也会从历史播客记录导入此账号。先注册你打算长期使用的主账号。

旧 Windows SQLite 数据不会随普通的 `docker compose up` 自动进入 Docker 卷，请首次使用时先运行上面的部署脚本，再注册主账号。容器启动时自动进行 SQLite 增列迁移。

运行状态：`docker compose ps`；队列/数据库检查：`http://127.0.0.1:5173/api/health/deep`；日志：`docker compose logs --tail=100 api research-worker podcast-worker audio-worker`。停止：`docker compose down`。不要使用 `down -v`，除非确定要删除数据库、音频与 Redis 数据。

要对外开放，先配 HTTPS 反向代理，设置 `SESSION_COOKIE_SECURE=True` 与精确的 `CORS_ORIGINS`，再重新评估登录限流、备份与数据库迁移策略。当前配置仅按本机私有服务验收。

## 已完成的上线前检查

- 隔离的账号/越权/来源校验测试：注册口令、登录/退出、旧记录认领、跨账号书籍/任务/音色/发音规则隔离与恶意 Origin 拒绝；不调用付费搜索或 TTS。
- 隔离 SQLite 的有限压力冒烟：320 个请求、并发 20，300 次读和 20 次发音规则写入。具体耗时以测试运行输出为准；脚本在 `backend/tests/load_smoke.py`。
- Compose 镜像已在 Docker Desktop 上构建；Web、API、Redis 和三个 Worker 已启动，`/api/health/deep` 返回 `healthy`。旧数据库与播客 WAV 已导入数据卷。

## 给其他人使用

可以交付项目源码与 `compose.yaml`，或在镜像构建成功后导出镜像。使用者仍需安装 Docker Desktop、配置自己的 `backend/.env`（注册口令、搜索、LLM 和 TTS 密钥）并运行 Compose。不要把自己的 `.env`、数据库和音频文件打包给别人。当前配置只允许本机访问；若需其他电脑访问，还要配置 HTTPS 和访问地址，不能直接把本机链接发给对方。
