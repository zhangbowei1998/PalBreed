# syntax=docker/dockerfile:1
# ============================================================
# 幻兽帕鲁配种 Agent — API 服务 (端口 8000)
# 依赖: pl_agent.core + pl_agent.api (+ adapters 用于 seed)
# ============================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH="/app/packages/core:/app/packages/adapters:/app/packages/api:/app/packages"

WORKDIR /app

# 安装第三方依赖（阿里云 PyPI 镜像，避免大陆服务器访问国外源超时）
COPY scripts/docker-requirements-api.txt /tmp/deps/requirements.txt
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r /tmp/deps/requirements.txt

# 复制源码
COPY packages/core/pl_agent /app/packages/core/pl_agent
COPY packages/api/pl_agent /app/packages/api/pl_agent
COPY packages/adapters/adapters /app/packages/adapters/adapters

# seed 数据与脚本
COPY data/processed/ /app/data/processed/
COPY data/tc-imba/ /app/data/tc-imba/
COPY data/sql/003_tcimba_extend.sql /app/data/sql/003_tcimba_extend.sql
COPY scripts/seed_docker.py /app/scripts/seed_docker.py
COPY scripts/seed_tcimba_full.py /app/scripts/seed_tcimba_full.py
COPY scripts/seed_breeding_rules.py /app/scripts/seed_breeding_rules.py

EXPOSE 8000

CMD ["uvicorn", "pl_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
