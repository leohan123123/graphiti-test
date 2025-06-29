# 桥梁工程知识图谱平台 - 项目结构

## 📂 项目目录结构

```
bridge-knowledge-platform/
├── backend/                    # FastAPI 后端服务
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 主应用
│   │   ├── api/               # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── documents.py   # 文档处理 API
│   │   │   ├── knowledge.py   # 知识图谱 API  
│   │   │   ├── export.py      # 语料导出 API
│   │   │   └── auth.py        # 认证 API
│   │   ├── core/              # 核心配置
│   │   │   ├── __init__.py
│   │   │   ├── config.py      # 配置管理
│   │   │   └── database.py    # 数据库连接
│   │   ├── models/            # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── document.py    # 文档模型
│   │   │   ├── knowledge.py   # 知识图谱模型
│   │   │   └── user.py        # 用户模型
│   │   ├── services/          # 业务逻辑服务
│   │   │   ├── __init__.py
│   │   │   ├── document_processor.py  # 文档处理服务
│   │   │   ├── graphiti_service.py    # Graphiti 集成服务
│   │   │   ├── bridge_ontology.py     # 桥梁工程本体
│   │   │   └── export_service.py      # 导出服务
│   │   └── utils/             # 工具函数
│   │       ├── __init__.py
│   │       ├── pdf_parser.py  # PDF 解析器
│   │       ├── cad_parser.py  # CAD 解析器  
│   │       └── bim_parser.py  # BIM 解析器
│   ├── requirements.txt       # Python 依赖
│   ├── Dockerfile            # Docker 配置
│   └── .env.example          # 环境变量示例
├── frontend/                  # SvelteKit 前端
│   ├── src/
│   │   ├── app.html
│   │   ├── routes/            # 路由页面
│   │   │   ├── +layout.svelte
│   │   │   ├── +page.svelte   # 首页
│   │   │   ├── upload/        # 文档上传页面
│   │   │   ├── graph/         # 图谱查看页面
│   │   │   └── export/        # 语料导出页面
│   │   ├── lib/               # 组件库
│   │   │   ├── components/    # 通用组件
│   │   │   ├── stores/        # 状态管理
│   │   │   └── utils/         # 工具函数
│   │   └── assets/            # 静态资源
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js     # TailwindCSS 配置
│   └── Dockerfile            # 前端 Docker 配置
├── docs/                      # 文档
│   ├── api.md                # API 文档
│   ├── deployment.md         # 部署文档
│   └── user-guide.md         # 用户指南
├── docker-compose.yml         # Docker Compose 配置
├── README.md                 # 项目说明
└── .gitignore                # Git 忽略文件
```

## 🛠️ 技术栈

### 后端
- **Framework**: FastAPI + Python 3.11+
- **知识图谱**: Graphiti Core (基于现有实现)
- **数据库**: Neo4j (图数据库) + PostgreSQL (元数据)
- **文档处理**: PyPDF, python-docx, CAD 解析库
- **AI 模型**: Ollama (本地) + OpenAI API (可选)

### 前端  
- **Framework**: SvelteKit + TypeScript
- **UI 组件**: Tailwind CSS + DaisyUI
- **图谱可视化**: D3.js 或 vis.js
- **状态管理**: Svelte Stores

### 部署
- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx
- **文件存储**: MinIO (兼容 S3)

## 🎯 核心功能模块

1. **文档处理引擎**: PDF/Word/CAD/BIM 文件解析
2. **知识图谱构建**: 基于 Graphiti 的智能实体关系抽取
3. **桥梁工程本体**: 专业领域知识表示
4. **可视化界面**: 交互式图谱展示和编辑
5. **语料导出**: 多格式训练数据生成
6. **批量处理**: 大规模文档处理支持 