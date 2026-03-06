# CLAUDE.md - RAGFlow MCP 服务开发指南

## 项目概述

- **项目路径**: `/home/zxy/111/test/`
- **RAGFlow 主项目路径**: `/home/zxy/ragflow-main/`
- **目标**: 开发基于 RAGFlow 知识库检索和智能体对话的 MCP 服务

## 项目结构

```
/home/zxy/111/test/
├── ragflow_mcp_server.py   # MCP Server - RAGFlow 工具服务器
├── api_server.py            # Flask API - Web QA 服务
├── qa.html                  # 前端问答页面
├── .env                     # 环境变量配置
├── README.md                # 项目说明
└── CLAUDE.md               # 本文件 - Claude Code 开发指南
```

## RAGFlow 主项目依赖

**RAGFlow 主项目** (`/home/zxy/ragflow-main/`) 提供:
- 知识库管理 API (`api/apps/kb_app.py`)
- 对话服务 (`api/apps/dialog_app.py`)
- 文档处理 (`rag/deepdoc/`)
- Agent 系统 (`/agent/`)

## 快速开始

### 安装依赖

```bash
pip install ragflow-sdk mcp flask flask-cors python-dotenv
```

### 配置环境变量

在 `.env` 文件或系统环境变量中配置:
- `RAGFLOW_API_KEY`: RAGFlow API 密钥
- `RAGFLOW_BASE_URL`: RAGFlow 服务地址 (默认 http://localhost:9380)
- `RAGFLOW_CHAT_ID`: 可选，指定聊天会话

### 运行服务

```bash
# 启动 MCP Server
python ragflow_mcp_server.py

# 启动 Flask API 服务
python api_server.py
```

## MCP 工具说明

当前 MCP Server 提供以下工具:

| 工具名 | 功能 |
|--------|------|
| `retrieve_knowledge` | 从 RAGFlow 知识库检索内容 |
| `list_datasets` | 列出所有可用数据集 |

### retrieve_knowledge 参数

- `query`: 搜索关键词 (必填)
- `dataset_ids`: 数据集 ID 列表 (可选)
- `top_k`: 返回结果数量 (默认 5)

## Claude Desktop 集成配置

```json
{
  "mcpServers": {
    "ragflow": {
      "command": "python",
      "args": ["/home/zxy/111/test/ragflow_mcp_server.py"],
      "env": {
        "RAGFLOW_API_KEY": "<你的API密钥>",
        "RAGFLOW_BASE_URL": "http://localhost:9380"
      }
    }
  }
}
```

## 开发指南

### 代码风格
- Python 遵循 PEP 8
- 导入顺序: 标准库 → 第三方库 → 本地模块
- 使用类型提示标注函数参数和返回值

### 常用开发任务
- 新增 MCP 工具: 在 `list_tools()` 和 `call_tool()` 中扩展
- 新增 API 路由: 在 `api_server.py` 中添加 Flask 路由
- 前端定制: 修改 `qa.html`

### 调试建议
- 查看 RAGFlow 服务日志: `docker logs -f ragflow-server`
- MCP 通信调试: 使用 `python -m mcp debug ragflow_mcp_server.py`

## 环境变量说明

| 变量名 | 作用 | 默认值 |
|--------|------|--------|
| RAGFLOW_API_KEY | RAGFlow API 密钥 | 必填 |
| RAGFLOW_BASE_URL | RAGFlow 服务地址 | http://localhost:9380 |
| RAGFLOW_CHAT_ID | 指定会话 ID | 自动选择 |

## 常见问题

- **无法导入 mcp/ragflow-sdk**: 执行 `pip install mcp ragflow-sdk`
- **缺少 RAGFLOW_API_KEY**: 检查环境变量配置
- **MCP 未加载**: 确认配置文件路径和参数正确

## 安全建议

- 切勿将真实 API 密钥提交到仓库
- 使用 `.env` 文件管理敏感配置 (已配置 git 忽略)
- 生产环境添加鉴权和限流
