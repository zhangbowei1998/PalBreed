# syntax=docker/dockerfile:1
# ============================================================
# 幻兽帕鲁配种 Agent — agent-web 服务 (端口 9000)
# 依赖: pl_agent.agent + pl_agent.agent_web
# ============================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH="/app/packages/agent:/app/packages/agent-web:/app/packages"

WORKDIR /app

# 安装第三方依赖（阿里云 PyPI 镜像，避免大陆服务器访问国外源超时）
COPY scripts/docker-requirements-agent-web.txt /tmp/deps/requirements.txt
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r /tmp/deps/requirements.txt

# 复制源码
COPY packages/agent/pl_agent /app/packages/agent/pl_agent
COPY packages/agent-web/pl_agent /app/packages/agent-web/pl_agent

EXPOSE 9000

CMD ["uvicorn", "pl_agent.agent_web.app:app", "--host", "0.0.0.0", "--port", "9000"]
