# 桥梁工程知识图谱平台 (Bridge Engineering Knowledge Graph Platform)

## 项目简介

这是一个基于 Graphiti 框架和 DeepSeek API 构建的桥梁工程知识图谱平台，旨在将 PDF、Word、CAD、BIM 等非结构化工程数据转换为结构化知识图谱，并导出用于大语言模型训练的语料。

## 技术栈

### 后端
- **FastAPI** - Python Web 框架
- **Graphiti Core** - 知识图谱构建框架
- **Neo4j** - 图数据库
- **DeepSeek API** - 大语言模型服务
- **PyMuPDF** - PDF 解析
- **Tesseract OCR** - 光学字符识别

### 前端
- **SvelteKit** - 前端框架
- **TypeScript** - 类型安全的 JavaScript
- **TailwindCSS** - CSS 框架

## 核心功能

1. **文档上传与解析**
   - 支持 PDF、Word、CAD、BIM 文件
   - 自动 OCR 识别扫描版文档
   - 智能文本提取和清理

2. **知识图谱构建**
   - 基于 DeepSeek API 的实体识别
   - 自动关系抽取
   - 智能 Token 截断处理
   - 避免 API 调用限制

3. **图谱查询与可视化**
   - 全文搜索功能
   - 实体和关系浏览
   - 统计信息展示

4. **语料导出**
   - 支持 JSONL、TXT、CSV 格式
   - 适用于大模型训练
   - 结构化知识表示

## 项目结构

```
graphiti-test/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # API 路由
│   │   ├── core/              # 核心配置
│   │   ├── services/          # 业务服务
│   │   │   ├── deepseek_client.py      # DeepSeek API 客户端
│   │   │   ├── deepseek_embedder.py    # 自定义嵌入器
│   │   │   └── graphiti_service.py     # 知识图谱服务
│   │   └── utils/             # 工具函数
│   └── uploads/               # 文件上传目录
├── bridge-knowledge-platform/ # 前端应用
│   ├── frontend/              # SvelteKit 前端
│   └── backend/               # 备用后端
└── venv/                      # Python 虚拟环境
```

## 安装与运行

### 环境要求
- Python 3.11+
- Node.js 16+
- Neo4j 5.0+
- Tesseract OCR

### 后端启动
```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

### 前端启动
```bash
cd bridge-knowledge-platform/frontend
npm install
npm run dev
```

### 服务地址
- 后端 API: http://localhost:8000
- 前端界面: http://localhost:5173
- Neo4j Browser: http://localhost:7474

## 配置说明

### DeepSeek API 配置
```python
# backend/app/services/deepseek_client.py
API_KEY = "sk-0b26cde0319b451e984c38a0734353e7"
MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com/v1"
```

### Neo4j 配置
```python
# backend/app/core/config.py
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "bridge123"
```

## 核心特性

### Token 限制处理
- 自动检测 DeepSeek API token 限制 (65536)
- 智能消息截断算法
- 保留重要上下文信息
- 避免 API 调用失败

### 自定义嵌入器
- 避免 OpenAI API 依赖
- 哈希基础的向量生成
- 384 维固定长度向量
- 快速本地计算

### 知识图谱索引
- 全文搜索索引：`node_name_and_summary`
- 关系搜索索引：`edge_name_and_fact`
- 实体 UUID 索引
- 高效查询性能

## API 接口

### 文档管理
- `POST /api/v1/documents/upload` - 文档上传
- `POST /api/v1/documents/process/{file_id}` - 文档处理
- `GET /api/v1/documents/list` - 文档列表

### 知识图谱
- `POST /api/v1/knowledge/search` - 图谱搜索
- `GET /api/v1/knowledge/stats` - 统计信息
- `GET /api/v1/knowledge/health` - 健康检查

### 导出功能
- `POST /api/v1/export/corpus` - 语料导出

## 开发历程

### 主要里程碑
1. ✅ 项目架构设计和技术栈选择
2. ✅ DeepSeek API 集成和 OpenAI 替换
3. ✅ Token 限制问题解决
4. ✅ 知识图谱构建功能实现
5. ✅ Neo4j 索引优化
6. ✅ 前后端联调和功能测试

### 技术难点解决
- **Token 超限问题**: 实现智能截断算法
- **API 兼容性**: 自定义 DeepSeek 客户端
- **嵌入模型**: 哈希基础的本地嵌入器
- **数据库索引**: Neo4j 全文搜索优化

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

## 联系方式

- 项目维护者: leohan123123
- GitHub: https://github.com/leohan123123/graphiti-test

---

**注意**: 本项目为桥梁工程知识图谱研究项目，旨在探索 AI 技术在土木工程领域的应用。 