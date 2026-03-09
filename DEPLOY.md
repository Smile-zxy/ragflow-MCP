# 离线部署指南

## 文件说明

```
/home/zxy/111/test/
├── offline/                 # Python 离线依赖包（2.6MB）
│   ├── *.whl               # pip wheel 包
├── venv312/                # Python 3.12 虚拟环境
├── web/                    # 前端页面
│   └── qa.html
├── api_server.py           # Flask 服务
├── .env                    # 环境配置
├── requirements.txt        # 依赖列表
└── DEPLOY.md              # 本部署指南
```

## 服务器部署步骤

### 方式一：使用离线包（推荐）

服务器只需有 Python 3.12.x 即可。

```bash
# 1. 复制文件到服务器
scp -r offline/ requirements.txt web/ api_server.py .env user@服务器IP:/home/user/ragflow/

# 2. 创建虚拟环境
cd /home/user/ragflow
python -m venv venv
source venv/bin/activate

# 3. 离线安装依赖
pip install --no-index --find-links=./offline -r requirements.txt

# 4. 启动服务
python api_server.py
```

### 方式二：使用打包的虚拟环境

```bash
# 1. 复制文件到服务器
scp venv312.tar.gz web/ api_server.py .env user@服务器IP:/home/user/ragflow/

# 2. 解压
cd /home/user/ragflow
tar -xzvf venv312.tar.gz

# 3. 激活并启动
source venv312/bin/activate
python api_server.py
```

### 3. 配置环境变量

编辑 `.env` 文件，确保以下配置正确：
```
RAGFLOW_API_KEY=你的API密钥
RAGFLOW_BASE_URL=http://RAGFlow服务器IP:9380
FLASK_PORT=7737
```

### 4. 启动服务

```bash
python api_server.py
```

或以后台模式运行：
```bash
nohup python api_server.py > api.log 2>&1 &
```

### 5. 访问服务

- 前端页面：`http://服务器IP:7737/home`
- API 端点：`http://服务器IP:7737/api/*`

## 注意事项

1. 确保服务器能访问 `RAGFLOW_BASE_URL` 指定的地址
2. 防火墙开放 7737 端口
3. 如需开机自启，可使用 systemd 或 supervisor
4. Python 版本要求：3.12.x

## 故障排除

### 报错：找不到 flask 模块

```bash
# 检查 Python 版本
python --version  # 应该是 Python 3.12.x
```

### 服务器 Python 版本不匹配

如果服务器没有 Python 3.12.x，请使用离线包方式安装，只需：
1. 确保服务器有 Python 3.12.x
2. 按"方式一"步骤安装
