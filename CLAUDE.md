# CLAUDE.md - 在 Claude Code 中开发本项目的指南

## 概述

- 本项目提供两个主要入口：
  - ragflow_mcp_server.py：基于 MCP 协议的 RAGFlow 工具服务器
  - api_server.py：用于 Web QA 的 Flask API 服务
- 前端页面：qa.html
- 目标：在 Claude Code（Claude 开发环境）中快捷运行、调试与扩展以上能力

## 快速开始

- 安装依赖

```bash
pip install ragflow-sdk mcp flask flask-cors
```

- 配置环境变量（建议使用系统环境变量或 .env 文件）
  - RAGFLOW_API_KEY：RAGFlow 的 API 密钥
  - RAGFLOW_BASE_URL：RAGFlow 服务地址，默认 http://localhost:9380
  - RAGFLOW_CHAT_ID：可选，用于指定 API Server 绑定的聊天会话

- 运行 MCP Server

```bash
python ragflow_mcp_server.py
```

- 运行 API Server

```bash
python api_server.py
```

- 在 Windows/WSL 下查看项目文件
  - Windows：`dir /s`
  - WSL/Linux：`ls -R`

## 在 Claude Desktop 中集成 MCP

- 如果使用 Claude Desktop，可以在配置文件中添加如下 MCP 服务器配置：

```json
{
  "mcpServers": {
    "ragflow": {
      "command": "python",
      "args": ["<绝对路径>/ragflow_mcp_server.py"],
      "env": {
        "RAGFLOW_API_KEY": "<你的API密钥>",
        "RAGFLOW_BASE_URL": "http://localhost:9380"
      }
    }
  }
}
```

## 项目结构

- ragflow_mcp_server.py：MCP Server，实现对 RAGFlow 的知识检索等工具能力
- api_server.py：Flask API，用于 Web 问答，封装 RAGFlow 会话
- qa.html：网页端的问答界面
- README.md：项目简要说明
- CLAUDE.md：面向 Claude Code 的开发说明

## 在 Claude Code 中的工作流建议

- 使用命令面板运行与调试脚本：直接运行 ragflow_mcp_server.py 或 api_server.py
- 结合终端与编辑器：
  - 终端设置/查看环境变量（RAGFLOW_API_KEY、RAGFLOW_BASE_URL、RAGFLOW_CHAT_ID）
  - 实时查看日志与错误输出
- 典型任务提示语：
  - 为 MCP 服务器新增一个工具，用于根据 dataset_id 过滤检索结果
  - 在 api_server.py 增加一个路由，返回当前可用的 chats 列表
  - 为 qa.html 添加一个输入历史展示区，并支持清空

## 代码风格与质量

- Python 遵循 PEP 8
- 导入顺序：标准库  第三方库  本地模块
- 错误处理：对 `ragflow_sdk` 与 `mcp` 的 ImportError 做显式提示
- 类型提示：为函数与返回值添加类型标注（如：list[types.Tool]）
- 日志：使用标准输出即可，避免在代码中硬编码敏感信息

## 环境变量说明

| 变量名 | 作用 | 默认值 |
|-------|------|--------|
| RAGFLOW_API_KEY | RAGFlow 服务的 API 密钥 | 请使用你自己的密钥 |
| RAGFLOW_BASE_URL | RAGFlow 服务地址 | http://localhost:9380 |
| RAGFLOW_CHAT_ID | 指定 API Server 使用的聊天会话 | 空（自动选择） |

## 常见问题

- 无法导入 mcp 或 ragflow_sdk
  - 请确认已执行 `pip install mcp ragflow-sdk`
- 运行时提示缺少 RAGFLOW_API_KEY
  - 请在系统或启动命令中设置环境变量
- MCP Server 在 Claude Desktop 中未加载
  - 请检查配置文件路径、args 中脚本绝对路径与 env 变量是否正确

## 安全与配置建议

- 切勿将真实的 RAGFLOW_API_KEY 写入仓库
- 通过环境变量或安全配置管理工具注入密钥
- 对外暴露的 API 在生产环境中请增加鉴权与限流
