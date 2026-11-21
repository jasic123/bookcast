# Book Podcast Research System

播客制作前端流程验证系统 - 从主题到书籍到资料收集的完整链路。

## 项目概述

本系统验证"用户主题 → 英文畅销书 → 候选筛选 → 资料检索 → 充分度评估"这条关键链路,为播客制作提供可靠的资料基础。

### 核心功能

1. **书单获取**: 支持 Amazon 畅销榜和 CSV 导入
2. **主题筛选**: 基于用户关注主题筛选候选书籍
3. **资料检索**: 检索书评、访谈、出版信息等多源资料
4. **充分度评估**: 评估主题匹配度和资料充分度

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SQLAlchemy / Alembic
- **前端**: React 18 / TypeScript / Vite / TailwindCSS
- **数据库**: SQLite
- **任务队列**: RQ + Redis
- **外部服务**: Tavily API / OpenAI-compatible LLM API

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

## 当前限制

- Amazon 抓取依赖公开榜单结构,站点变化可能导致失败
- LLM 判断存在主观性,需要人工复核关键决策
- Tavily 搜索受限于公开可访问内容
- 书评充分度判断是辅助性的,不能替代人工编辑

## 后续工作

本版本聚焦验证核心链路,以下功能计划后续实现:

- [ ] 播客文稿生成
- [ ] 文稿编辑与终审
- [ ] TTS 与音频生成
- [ ] 用户账户与权限
- [ ] 生产环境部署

## License

MIT
