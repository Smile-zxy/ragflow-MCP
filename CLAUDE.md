# CLAUDE.md - RAGFlow MCP 服务开发指南

<!--
{
  "permissions": {
    "acceptEdits": true,
    "allowEdits": true,
    "allowBash": true,
    "autoApprove": true,
    "allowSed": true
  }
}
-->

## 可用工具

- Bash: true
- Edit: true
- Write: true
- Read: true
- Glob: true
- Grep: true

## 项目概述

- **项目路径**: `/home/zxy/111/test/`
- **RAGFlow 主项目路径**: `/home/zxy/ragflow-main/`
- **目标**: 开发基于 RAGFlow 知识库检索和智能体对话的 MCP 服务

## 项目结构

```
/home/zxy/111/test/
├── web/
│   └── qa.html            # 前端问答页面
├── ragflow_mcp_server.py   # MCP Server - RAGFlow 工具服务器
├── api_server.py           # Flask API + 前端服务 (端口 5000)
├── .env                    # 环境变量配置
├── requirements.txt        # Python 依赖
├── README.md               # 项目说明
└── CLAUDE.md              # 本文件 - Claude Code 开发指南
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

在 `.env` 文件或系统环境变量中配置:
- `RAGFLOW_API_KEY`: RAGFlow API 密钥
- `RAGFLOW_BASE_URL`: RAGFlow 服务地址 (默认 http://localhost:9380)
- `RAGFLOW_CHAT_ID`: 可选，指定聊天会话

### 运行服务

```bash
cd /home/zxy/111/test
python api_server.py
```

启动后显示:
```
RAGFlow API Server starting...
RAGFlow Base URL: http://localhost:9380
Server IP: 192.168.x.x
Access the web UI at: http://192.168.x.x:5000/
```

### 前端页面访问

- **前端页面**: http://localhost:5000/ (本地访问)
- **API 端点**: http://localhost:5000/api/*

**注意**: Flask 服务同时提供前端页面和 API，无需单独启动 HTTP 服务。

**前端自动适配**:
- 本地访问 (localhost/127.0.0.1): 自动使用当前页面地址作为 API 地址
- 远程访问: 自动获取服务器 IP 并拼接 API 地址

## API 端点说明

### 知识库相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/datasets` | GET | 获取所有知识库列表 |
| `/api/chats/set` | POST | 设置当前使用的知识库 |

**`/api/datasets` 响应示例:**
```json
{
  "success": true,
  "data": [{"id": "xxx", "name": "名称"}]
}
```

### 智能体相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/canvas` | GET | 获取所有智能体列表 |
| `/api/canvas/set` | POST | 设置当前使用的智能体并创建会话 |
| `/api/chat` | POST | 发送对话消息 (支持智能体和知识库模式) |

**`/api/canvas/set` 请求:**
```json
{"agent_id": "智能体ID"}
```

**`/api/chat` 请求:**
```json
{"query": "问题内容", "new_session": false}
```

**`/api/chat` 响应:**
```json
{
  "success": true,
  "answer": "AI回答内容",
  "references": [{"source": "文档名", "content": "相关内容"}]
}
```

### 文档相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/datasets/<dataset_id>/documents` | GET | 获取知识库中的文件列表 |
| `/api/datasets/<dataset_id>/documents/<document_id>/download` | GET | 下载指定文件 |
| `/api/datasets/<dataset_id>/documents/<document_id>/content` | GET | 获取文档内容/片段 |

**文件下载实现方式:**

使用 RAGFlow SDK 的 `Document.download()` 方法:

```python
from ragflow_sdk import RAGFlow
from ragflow_sdk.modules.document import Document

client = RAGFlow(api_key=RAGFLOW_API_KEY, base_url=RAGFLOW_BASE_URL)

# 获取数据集
datasets = client.list_datasets()
target_dataset = next((ds for ds in datasets if ds.id == dataset_id), None)

# 获取文档
documents = target_dataset.list_documents()
target_doc = next((doc for doc in documents if doc.id == document_id), None)

# 下载文档内容
file_content = target_doc.download()
```

前端使用 fetch + Blob 方式实现直接下载:

```javascript
fetch(downloadUrl)
    .then(response => response.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = docName;
        a.click();
        window.URL.revokeObjectURL(url);
    });
```

### 检索相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/retrieve` | POST | 直接检索知识库内容 (不经过 AI) |
| `/api/retrieve-with-summary` | POST | 检索知识库内容并使用 AI 总结 |

**`/api/retrieve` 请求:**
```json
{"query": "关键词", "dataset_ids": ["ID1"], "top_k": 5}
```

**`/api/retrieve-with-summary` 请求:**
```json
{"query": "关键词", "dataset_ids": ["ID1"], "top_k": 5}
```

**`/api/retrieve-with-summary` 响应:**
```json
{
  "success": true,
  "data": [{"source": "文档名", "content": "相关内容"}],
  "answer": "检索到的原始内容",
  "summary": "AI 总结后的回答"
}
```

### FAQ 管理相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/faqs` | GET | 获取 FAQ 数据 |
| `/api/faqs` | POST | 保存 FAQ 数据 |

**FAQ 数据结构:**
```json
{
  "agent_xxx": [
    {"question": "问题", "answer": "答案（支持HTML，如<img>）"}
  ]
}
```

### 服务配置

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/server-ip` | GET | 获取服务器 IP 地址 |

**`/api/server-ip` 响应:**
```json
{"success": true, "ip": "192.168.x.x"}
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
- 前端定制: 修改 `web/qa.html`

### 调试建议
- 查看 RAGFlow 服务日志: `docker logs -f ragflow-server`
- MCP 通信调试: 使用 `python -m mcp debug ragflow_mcp_server.py`
- 前端调试: 打开浏览器控制台 (F12) 查看网络请求和日志

## 环境变量说明

| 变量名 | 作用 | 默认值 |
|--------|------|--------|
| RAGFLOW_API_KEY | RAGFlow API 密钥 | 必填 |
| RAGFLOW_BASE_URL | RAGFlow 服务地址 | http://localhost:9380 |
| RAGFLOW_CHAT_ID | 指定会话 ID | 自动选择 |

## 部署说明

### 服务器部署

1. 启动 Flask 服务:
   ```bash
   python api_server.py
   ```

2. 确保防火墙开放 5000 端口

3. 通过云桌面访问: `http://服务器IP:5000/`

### 前端适配机制

`web/qa.html` 启动时会:
1. 检测访问地址是否为 localhost/127.0.0.1
2. 如果是本地访问，直接使用当前页面地址作为 API 地址
3. 如果是远程访问，调用 `/api/server-ip` 获取服务器 IP
4. 如果获取失败，回退到使用当前页面地址

## 前端功能说明

### FAQ 管理功能
- 支持设置智能体的常见问题
- 答案支持 HTML 标签（如 `<img src="图片链接">`）
- 点击 FAQ 问题直接在聊天中显示答案（不调用 AI）

### 文件检索功能
- 点击知识库文件可触发检索
- 支持检索 + AI 总结（调用 `/api/retrieve-with-summary`）
- 检索结果自动添加到问答历史

### UI 调整
- 智能体/知识库下拉框：减小尺寸和字体
- 刷新按钮：鼠标悬停显示手指光标和旋转动画
- 左侧导航栏：减小尺寸和字体

## 常见问题

- **无法导入 mcp/ragflow-sdk**: 执行 `pip install -r requirements.txt`
- **缺少 RAGFLOW_API_KEY**: 检查环境变量配置
- **MCP 未加载**: 确认配置文件路径和参数正确
- **云桌面无法连接 API**: 确保防火墙开放 5000 端口，服务器能访问外网（用于获取 IP）

## 安全建议

- 切勿将真实 API 密钥提交到仓库
- 使用 `.env` 文件管理敏感配置 (已配置 git 忽略)
- 生产环境添加鉴权和限流
