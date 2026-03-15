# RAGFlow MCP Server (Test Implementation)

这是一个基于 MCP (Model Context Protocol) 的 RAGFlow 服务实现，允许外部工具通过 MCP 协议检索 RAGFlow 知识库。

## 功能

- `retrieve_knowledge`: 根据查询语句检索知识库内容。
- `list_datasets`: 列出所有可用的数据集。

## 依赖

确保已安装以下 Python 包：

```bash
pip install mcp ragflow-sdk
```

## 配置

在运行之前，请设置环境变量：

- `RAGFLOW_API_KEY`: ragflow-Y0NTFkZTQ2OWFkZjExZjA4Y2NiMTJkM2  // <你的本地ragflow API密钥>
- `RAGFLOW_BASE_URL`: http://localhost:9380

## 运行

使用 `uv` 或直接运行 Python 脚本：

```bash
# 直接运行 (Stdio 模式)
export RAGFLOW_API_KEY="your-api-key"
python ragflow_mcp_server.py
```

或者在 Claude Desktop 配置文件中添加：

```json
{
  "mcpServers": {
    "ragflow": {
      "command": "python",
      "args": ["/absolute/path/to/ragflow_mcp_server.py"],
      "env": {
        "RAGFLOW_API_KEY": "your-api-key",
        "RAGFLOW_BASE_URL": "http://localhost:9380"
      }
    }
  }
}
```
