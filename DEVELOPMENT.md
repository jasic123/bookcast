# 开发指南

## 项目架构

```
book-podcast-research/
├── backend/              # FastAPI 后端
│   ├── alembic/         # 数据库迁移
│   ├── app/
│   │   ├── api/         # API 路由
│   │   ├── core/        # 核心配置（数据库、队列）
│   │   ├── models/      # SQLAlchemy 模型
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # 业务逻辑
│   │   └── tasks/       # 后台任务
│   └── tests/           # 测试
└── frontend/            # React 前端
    └── src/
        ├── components/  # React 组件
        ├── pages/       # 页面组件
        ├── services/    # API 调用
        └── types/       # TypeScript 类型
```

## 添加新功能

### 后端：添加新的 API 端点

1. **定义数据模型** (`app/models/`)
```python
# app/models/example.py
from sqlalchemy import Column, Integer, String
from app.core.database import Base

class Example(Base):
    __tablename__ = "examples"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
```

2. **创建迁移**
```bash
alembic revision --autogenerate -m "add example table"
alembic upgrade head
```

3. **定义 Pydantic Schema** (`app/schemas/`)
```python
# app/schemas/example.py
from pydantic import BaseModel

class ExampleBase(BaseModel):
    name: str

class ExampleCreate(ExampleBase):
    pass

class ExampleResponse(ExampleBase):
    id: int
    
    class Config:
        from_attributes = True
```

4. **实现业务逻辑** (`app/services/`)
```python
# app/services/example_service.py
class ExampleService:
    async def create_example(self, name: str):
        # 业务逻辑
        pass
```

5. **添加 API 路由** (`app/api/`)
```python
# app/api/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

router = APIRouter(prefix="/examples", tags=["examples"])

@router.post("/")
async def create_example(data: ExampleCreate, db: AsyncSession = Depends(get_db)):
    # 调用服务层
    pass
```

6. **注册路由** (`app/main.py`)
```python
from app.api import example
app.include_router(example.router, prefix="/api")
```

### 前端：添加新页面

1. **定义类型** (`src/types/index.ts`)
```typescript
export interface Example {
  id: number
  name: string
}
```

2. **添加 API 调用** (`src/services/api.ts`)
```typescript
export const exampleApi = {
  getExamples: async (): Promise<Example[]> => {
    const response = await api.get('/examples/')
    return response.data
  }
}
```

3. **创建页面组件** (`src/pages/ExamplePage.tsx`)
```tsx
import { useState, useEffect } from 'react'
import { exampleApi } from '../services/api'

export default function ExamplePage() {
  const [data, setData] = useState([])
  
  useEffect(() => {
    loadData()
  }, [])
  
  const loadData = async () => {
    const result = await exampleApi.getExamples()
    setData(result)
  }
  
  return <div>...</div>
}
```

4. **添加路由** (`src/App.tsx`)
```tsx
<Route path="/example" element={<ExamplePage />} />
```

## 测试

### 后端测试

```bash
cd backend

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_book_fetcher.py

# 运行并显示覆盖率
pytest --cov=app tests/

# 运行特定测试函数
pytest tests/test_book_fetcher.py::test_fetch_amazon_list -v
```

### 前端测试

```bash
cd frontend

# 运行测试（待配置）
npm test

# 类型检查
npm run type-check

# Lint 检查
npm run lint
```

## 调试

### 后端调试

**查看日志:**
```bash
# 查看 API 日志
uvicorn app.main:app --log-level debug

# 查看 Worker 日志
python worker.py
```

**使用 Python 调试器:**
```python
import pdb; pdb.set_trace()
```

**查看数据库:**
```bash
sqlite3 book_research.db
.tables
.schema books
SELECT * FROM books LIMIT 5;
```

### 前端调试

- 使用浏览器开发者工具
- 查看 Network 标签页的 API 请求
- 使用 React DevTools

## 代码规范

### Python (后端)

```bash
# 格式化代码
black app/ tests/

# Lint 检查
flake8 app/ tests/

# 类型检查
mypy app/
```

### TypeScript (前端)

```bash
# 格式化代码（待配置）
npm run format

# Lint 检查
npm run lint

# 自动修复
npm run lint:fix
```

## Git 工作流

1. 从 main 分支创建功能分支
```bash
git checkout -b feature/your-feature-name
```

2. 提交时写清晰的提交信息
```bash
git commit -m "feat: add book theme screening"
git commit -m "fix: handle empty search results"
git commit -m "docs: update API documentation"
```

3. 推送并创建 Pull Request
```bash
git push origin feature/your-feature-name
```

## 性能优化

### 后端

- 使用异步 I/O (asyncio, httpx)
- 数据库查询添加索引
- 使用 Redis 缓存频繁访问的数据
- 长时间任务使用 RQ 后台队列

### 前端

- 使用 React.memo 避免不必要的重渲染
- 懒加载大型组件
- 优化图片和静态资源
- 使用虚拟滚动处理长列表

## 环境变量管理

**不要提交包含真实 API Key 的文件到 Git！**

```bash
# .gitignore 已包含
.env
*.db
```

开发时使用本地 `.env` 文件，生产环境通过环境变量或密钥管理服务注入。
