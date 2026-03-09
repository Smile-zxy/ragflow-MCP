FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 7737

# 设置环境变量
ENV RAGFLOW_API_KEY=ragflow-Y0NTFkZTQ2OWFkZjExZjA4Y2NiMTJkM2
ENV RAGFLOW_BASE_URL=http://host.docker.internal:9380
ENV FLASK_PORT=7737

# 启动服务
CMD ["python", "api_server.py"]
