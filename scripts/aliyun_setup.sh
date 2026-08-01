#!/usr/bin/env bash
# ============================================================
# 阿里云 ECS 一键初始化脚本 — pl-agent
# 用途: 在新购阿里云服务器上安装 Docker / Compose / 加 Swap
# 用法: sudo bash scripts/aliyun_setup.sh
# 注意: 大陆服务器若官方源拉取失败，脚本会自动回退国内镜像
# ============================================================
set -euo pipefail

echo "==> [1/4] 更新系统包索引"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
elif command -v yum >/dev/null 2>&1; then
  yum makecache -y
fi

echo "==> [2/4] 安装 Docker（兼容 Ubuntu / CentOS / Alibaba Cloud Linux）"
if ! command -v docker >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    # Debian / Ubuntu 系：官方脚本
    if curl -fsSL https://get.docker.com -o /tmp/get-docker.sh 2>/dev/null; then
      sh /tmp/get-docker.sh
    elif curl -fsSL https://get.daocloud.io/docker -o /tmp/get-docker.sh 2>/dev/null; then
      sh /tmp/get-docker.sh
    else
      echo "!! Docker 安装脚本下载失败，请手动安装，参考 docs/architecture/ALIYUN_DEPLOY.md"
      exit 1
    fi
  elif command -v yum >/dev/null 2>&1; then
    # CentOS / Alibaba Cloud Linux 系：阿里云 docker-ce 镜像源（国内可达）
    yum install -y yum-utils
    yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
    if grep -qi 'alibaba cloud linux' /etc/os-release && grep -q 'VERSION_ID="3"' /etc/os-release; then
      # Alibaba Cloud Linux 3 基于 RHEL 8，把 $releasever 换成 8 才有可用源
      sed -i 's/$releasever/8/g' /etc/yum.repos.d/docker-ce.repo
    fi
    yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  fi
fi
systemctl enable --now docker || true
echo "    docker: $(docker --version 2>/dev/null)"
echo "    compose: $(docker compose version 2>/dev/null)"

echo "==> [3/4] 将当前用户加入 docker 组（免 sudo）"
usermod -aG docker "${SUDO_USER:-$USER}" || true

echo "==> [4/4] 添加 2G Swap（内存不够用时的缓冲）"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
free -h

echo ""
echo "============================================================"
echo " 初始化完成！请【重新登录】使 docker 组生效（exit 后重新 ssh）"
echo " 下一步: scp 上传代码 → 配 .env → docker compose up -d --build"
echo " 详见:   docs/architecture/ALIYUN_DEPLOY.md"
echo "============================================================"
