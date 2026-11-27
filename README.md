# Book Podcast Research System

播客制作前端流程验证系统 - 从主题到书籍到资料收集的完整链路。

## 项目概述

本系统验证"用户主题 → 英文畅销书 → 候选筛选 → 资料检索 → 充分度评估"这条关键链路,为播客制作提供可靠的资料基础。

### 核心功能

1. **书单获取**: 支持 Amazon 畅销榜和 CSV 导入
2. **主题筛选**: 基于用户关注主题筛选候选书籍
3. **资料检索**: 检索书评、访谈、出版信息等多源资料
4. **充分度评估**: 评估主题匹配度和资料充分度
5. **播客文稿生成**: 多 Agent 协作生成和评审播客文稿
6. **TTS 语音合成**: 支持多语言和自定义音色的语音生成
7. **用户认证与管理**: JWT 认证、音色保存和语音身份管理

## 系统演示

打开 [`DEMO_SHOWCASE.html`](./DEMO_SHOWCASE.html) 查看完整的前端界面演示，包含：

### 🔍 主题找书
- 输入关注主题（如"死亡""轮回""虚拟世界"）
- 系统从 Amazon 畅销榜中筛选相关书籍
- 显示主题匹配度和相关证据

### 📊 搜索结果
- 实时显示匹配进度
- 每本书展示匹配理由和证据来源
- 一键进行深度研究

### 📖 单书研究
- 资料统计（书评数、作者信息、新闻报道等）
- 资料充分度评估
- 播客文稿生成和语音合成

### 🎤 语音身份管理
- 保存多个个性化音色
- 为主持人/嘉宾配置不同音色
- 试听和更换语音身份

### 🎙️ 语音合成对比
- **原始录音**: 用户上传的 6 秒个人语音样本（WAV 格式）
- **克隆音色**: AI 克隆生成的播客语音（MP3 格式）
- 波形对比展示

### 🔄 端到端工作流
从"输入主题"到"生成播客"的完整 8 步流程可视化

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLAlchemy / Alembic / RQ
- **前端**: React 18 / TypeScript / Vite / TailwindCSS
- **认证**: JWT / Cookie 会话管理
- **数据库**: SQLite + 异步 ORM
- **任务队列**: RQ + Redis（3 个独立队列：research、podcast、audio）
- **AI 能力**: 
  - **LLM**: Trajectory Flow API（文本生成和推理）
  - **搜索**: Tavily API（网络检索）
  - **TTS**: SiliconFlow CosyVoice2（文本转语音）
- **部署**: Docker / Docker Compose（支持 Windows/Linux）
- **多 Agent**: AutoGen 框架（研究 Agent、评审 Agent、音频 Agent）

## 项目结构

```
book-podcast-research/
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/         # API 路由
│   │   ├── core/        # 核心配置
│   │   ├── models/      # 数据库模型
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # 业务逻辑
│   │   └── tasks/       # 后台任务
│   ├── alembic/         # 数据库迁移
│   ├── tests/           # 测试
│   └── requirements.txt
├── frontend/            # React 前端
│   ├── src/
│   │   ├── components/  # React 组件
│   │   ├── pages/       # 页面
│   │   ├── services/    # API 调用
│   │   └── types/       # TypeScript 类型
│   ├── package.json
│   └── vite.config.ts
├── docs/                # 文档
└── docker-compose.yml   # 可选的容器编排

```

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- Redis (用于任务队列)
- Tavily API Key
- OpenAI-compatible API Key

### 环境配置

1. 复制环境变量模板:
```bash
cp backend/.env.example backend/.env
```

2. 编辑 `backend/.env` 填入必要的 API Keys:
```
TAVILY_API_KEY=your_tavily_key
LLM_API_KEY=your_llm_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
```

### 后端启动

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## API 文档

启动后端后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 测试

### 后端测试
```bash
cd backend
pytest
```

### 前端测试
```bash
cd frontend
npm test
```

## 验收测试

项目包含真实案例测试,验证以下场景:

| 书籍与主题 | 测试目的 |
|---|---|
| *Sunrise on the Reaping* + 死亡 | 验证能识别有资料支持的主题候选 |
| *Sunrise on the Reaping* + 轮回 | 验证不会把死亡或暴力自动判断为轮回 |
| *Daddy Issues: A Memoir* + 死亡 | 验证没有直接证据时不会强行匹配 |
| *Dog Man: A Sprinkle in Time* + 死亡 | 验证不会将其他册或系列背景当作本册证据 |

运行验收测试:
```bash
cd backend
pytest tests/acceptance/
```

## 图书资料与搜索配置

首页支持按主题找书：通过网络检索收集候选作品，核对主题证据、Open Library 书目及作者的明确国家身份，再返回最多 10 本。每本展示关联理由和可点击的主题、作者证据来源；证据不足时可能返回更少或零本。选择书籍后可继续创建研究任务和播客稿。原有书单仍可在“历史书单”中访问。
“指定书籍”入口先搜索 Open Library；无匹配或不可用时，使用现有豆包搜索（失败时 Tavily）寻找书名、作者与来源，并再次尝试馆藏核验。仅有网页证据的候选会标注未通过馆藏核验；证据不足时展示搜索来源供人工核对。也可手动输入书名与作者。研究主题可留空，按整本书收集资料、评估缺口，再在研究结果页生成播客稿。接口为 GET /api/books/search、POST /api/books/single、POST /api/research/（themes: []）。

研究流程使用 AutoGen 专项 Agent 分别完成书目核对、主题判断、资料收集、证据评估和书评章节撰写。Open Library 的简介和 Project Gutenberg 的原文节选保留来源；节选不代表读过全书。

安装 Python 3.10 或更新版本及 Node.js 24 后，在项目目录执行：

```powershell
cd backend
python -m pip install -r requirements.txt
npm install --prefix mcp-servers
```

要使用火山引擎 SearchInfinity Custom 联网搜索，在 `backend/.env` 配置 `DOUBAO_SEARCH_API_KEY`；地址默认为 `https://open.feedcoopapi.com`。使用 SearchInfinity 搜索专用 API Key，未填写或搜索失败时继续使用 Tavily。不要将 `.env` 提交到 Git。

`GOODREADS_PROXY` 可为 Goodreads、Open Library 和 Gutenberg MCP 设置本机 HTTP 代理；不需要代理时留空。修改配置后重启后端和研究队列工作进程。

### 播客文稿

创建播客文稿时可选择中文或英文（默认中文）；英文稿仍使用中文角色标签以兼容分角色配音，台词正文为英文。新任务所选语言会保存，失败后续跑沿用原语言。

如果最终评审未通过，页面会列出各条意见供勾选。选好后点击“按所选意见修改文稿”，系统在原任务内保存新版本并再次评审；已有稿件和评审记录仍可查看。一次只生成一个新版本，若仍有问题可再次选择修改。

在已完成的研究页面先选择播客人数（单人、双人、三人或四人），再填写主题、时长、风格、听众；可粘贴或导入 TXT / Markdown 参考资料。新任务不预选双人。任务通过 Redis 队列后台执行；AutoGen GraphFlow 使用单线程运行时依次调度策划、资料研究、脚本撰写和评审。每个阶段完成后会保存检查点；失败任务可点击“从最近检查点续跑”，复用已完成的大纲、资料和稿件。单人稿由主持人独白，多人稿要求每位指定角色都有台词；评审不通过时返回撰稿修改，最多三版。仍未通过时显示人工复核和评审意见，不会标记为通过。系统保留大纲、来源、各版文稿及评审记录；引用和事实仍需人工核对。旧任务没有人数记录时按原双人格式读取。

文稿完成评审后可单独点击“生成播客音频”：参考 NeuralNoise 的分角色台词、逐段 TTS 与合成流程，用 SiliconFlow CosyVoice2 为所选角色分别配音，导出可播放、可下载的 WAV。未通过 AI 评审的文稿仍可生成试听音频，但必须先查看问题并明确勾选确认，音频不会被标记为评审通过。默认音色由后端提供，主持人和第一位嘉宾可使用 `bella` / `anna`；更多嘉宾需填写音色 ID。页面可输入自己的音色 ID，手动选择会保存在当前浏览器。没有定制音色时不要输入他人的音色 ID。生成失败只影响音频状态，不会删除文稿。

语音接口使用 `backend/.env` 中的 `TTS_API_KEY`；如留空且 `LLM_BASE_URL` 指向 SiliconFlow，则复用现有 `LLM_API_KEY`。`TTS_BASE_URL` 默认 `https://api.siliconflow.cn/v1`，`TTS_MODEL` 默认 `FunAudioLLM/CosyVoice2-0.5B`。合成会产生语音服务费用，建议先用短稿尝试。

在“录制个人音色”中朗读示例文字约 8–10 秒，试听后填写与录音一致的文字和音色名称，确认拥有该声音的使用授权再上传。录音会发送给 SiliconFlow 创建自定义音色；项目只接收并使用返回的音色 ID，不保存原始录音。自定义音色可以填给主持人或嘉宾。需要录音权限；浏览器中建议使用 localhost。请勿上传未获授权的他人声音。

研究、播客稿和音频分别使用 Redis `research`、`podcast`、`audio` 队列。Windows 可运行 `./start-all.ps1` 等待 Redis、API、三个 Worker 和前端就绪后打开页面；手动运行时在后端目录分别执行 `python worker.py`、`python worker.py --queue podcast` 和 `python worker.py --queue audio`。`/health/deep` 会检查数据库、Redis 和 Worker 心跳。TTS 最多 3 段并发，成功片段缓存 7 天；超时或服务端错误最多重试 3 次，重生成时复用已缓存片段，并统一音量后按稿件顺序拼接。

## 当前限制

- Amazon 抓取依赖公开榜单结构,站点变化可能导致失败
- LLM 判断存在主观性,需要人工复核关键决策
- Tavily 搜索受限于公开可访问内容
- 书评充分度判断是辅助性的,不能替代人工编辑

## 后续工作

本版本聚焦验证核心链路,以下功能计划后续实现:

- [x] 播客文稿生成
- [ ] 文稿编辑与终审
- [x] 预设音色 TTS 与 WAV 音频生成
- [x] 用户录音、授权确认与定制音色创建
- [ ] 用户账户与权限
- [ ] 生产环境部署

## License

MIT
