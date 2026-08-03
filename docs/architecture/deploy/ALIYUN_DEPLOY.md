# 阿里云 ECS 部署指南 — pl-agent

> 目标：把 4 个 Docker 服务（postgres / api / agent-web / web）部署到一台全新阿里云 ECS 上。
> 适用：Ubuntu 22.04 / 24.04 LTS（推荐）、CentOS 7.9+。

---

## 0. 前置信息（先确认）

| 项 | 说明 |
|----|------|
| 公网 IP | 控制台 ECS 实例页可见，例如 `47.98.xx.xx` |
| 操作系统 | 建议 **Ubuntu 22.04 LTS**（Docker 支持最好） |
| 登录账号 | 默认 `root`（Ubuntu 镜像 root 可直接登录） |
| 密码/密钥 | 购买时设置或后续重置 |
| 本机 | macOS（已有 Docker 环境，代码在 `~/Desktop/pl-agent`） |

> 如果你的系统是 CentOS，把下面命令里的 `apt` 换成 `yum`，`ubuntu` 用户名换成 `root` 即可。

---

## 1. 阿里云控制台 — 安全组放行端口 ⚠️ 最重要

新购服务器默认安全组**只放行 22**，不放行端口浏览器打不开。

1. 登录 [阿里云控制台](https://ecs.console.aliyun.com/) → ECS 实例 → 点击你的实例
2. 左侧 **安全组** → **配置规则** → **入方向** → **手动添加**
3. 添加以下规则：

| 协议 | 端口范围 | 授权对象 | 说明 |
|------|---------|---------|------|
| TCP | 22 | 0.0.0.0/0 | SSH 登录 |
| TCP | 8080 | 0.0.0.0/0 | ⭐ 前端入口（必须放行） |
| TCP | 80 | 0.0.0.0/0 | 可选：后面配域名/HTTPS |
| TCP | 443 | 0.0.0.0/0 | 可选：后面配 HTTPS |

> **不要**放行 8000 / 9000 / 5432 —— 这些是容器内网服务，由 nginx 统一反代，不需要对外暴露，更安全。

---

## 2. 本机 SSH 登录服务器

```bash
ssh root@<你的公网IP>
```

首次连接会提示确认指纹，输入 `yes`，然后输入密码。

> 本机 macOS 若不想每次输密码，可配置密钥免密登录（可选，见文末附录）。

---

## 3. 服务器初始化（安装 Docker + Compose）

在服务器终端里执行（一键脚本，已帮你写好）：

```bash
curl -fsSL https://gitee.com/mirrors/docker-ce/raw/master/install.sh -o /tmp/docker-install.sh || true
# 上面这行如果网络慢可跳过，直接用官方源：
curl -fsSL https://get.docker.com | sh
```

> 中国大陆服务器访问 `get.docker.com` 偶尔不稳定，失败就多试一次，或改用国内镜像源（见附录）。

### 如果你的系统是 CentOS / Alibaba Cloud Linux（yum 系）

直接用阿里云镜像源安装 docker-ce（含 compose 插件）：

```bash
# 1. 装 yum-utils（提供 yum-config-manager）
sudo yum install -y yum-utils

# 2. 添加阿里云 docker-ce 源
sudo yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 3. 若系统是 Alibaba Cloud Linux 3，需要把 $releasever 换成 8（CentOS 7 请跳过这行）
grep -q 'VERSION_ID="3"' /etc/os-release && sudo sed -i 's/$releasever/8/g' /etc/yum.repos.d/docker-ce.repo

# 4. 安装
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 5. 开机自启 + 立即启动
sudo systemctl enable --now docker
```

安装完验证：

```bash
sudo docker --version
sudo docker compose version
```

把当前用户加入 docker 组（免 sudo），然后**重新登录一次**：

```bash
sudo usermod -aG docker $USER
exit   # 重新 ssh 进来
```

---

## 4. 上传项目代码

### 方式 A：scp 直接上传（推荐，保证是本地最新代码）

在**你 Mac 的终端**执行（不是服务器）：

```bash
scp -r /Users/mingri/Desktop/pl-agent root@<你的公网IP>:/opt/pl-agent
```

> 会传一会儿（含 data/ 数据文件）。若中途断线可重试，或用 `rsync`（可断点续传）：
> ```bash
> rsync -avz --partial /Users/mingri/Desktop/pl-agent/ root@<IP>:/opt/pl-agent/
> ```

### 方式 B：git clone（需先把本地代码推到 GitHub）

```bash
# 在 Mac 上：把本地领先的提交推上去
cd /Users/mingri/Desktop/pl-agent
git push origin main

# 在服务器上：
sudo mkdir -p /opt
cd /opt
git clone https://github.com/zhangbowei1998/PalBreed.git pl-agent
```

---

## 5. 配置环境变量 `.env`

在服务器上：

```bash
cd /opt/pl-agent
cp .env.example .env
vim .env   # 或 nano .env
```

填入真实值：

```bash
# DeepSeek LLM（必填）—— 到 https://platform.deepseek.com 申请 API Key
LLM_API_KEY=sk-你的真实DeepSeek密钥
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# token 签名密钥（生产必须改成随机长字符串）
AUTH_SECRET=<随机字符串>
```

生成随机 `AUTH_SECRET`：

```bash
openssl rand -hex 32
```

> `.env` 已被 .gitignore 排除，不会被提交，放心填写。

---

## 6. 构建并启动

```bash
cd /opt/pl-agent
docker compose up -d --build
```

查看状态（等待 healthcheck 变 healthy，约 1-2 分钟）：

```bash
docker compose ps
```

第一次构建要拉取镜像 + 编译前端，可能 5-15 分钟，耐心等待。

---

## 7. 验证部署

```bash
# 服务器上自测
curl -s http://localhost:8080 | head -5
curl -s http://localhost:8000/health
curl -s http://localhost:9000/health
```

然后**在浏览器**打开：

```
http://<你的公网IP>:8080
```

- 前端页面应能正常加载
- 配种查询（走 `/api/`）应能返回结果
- Agent 对话（走 `/agent/`）应能回复

---

## 8.（可选）域名 + HTTPS

1. 域名解析：在阿里云 DNS 加一条 A 记录指向公网 IP
2. 申请免费证书：阿里云控制台 → SSL 证书 → 免费证书
3. 安全组放行 80 / 443
4. 在服务器上用 **Caddy** 一键 HTTPS 反代（推荐，自动续期）：

   ```bash
   # 安装 Caddy（或用 docker 跑 caddy）
   curl -fsSL https://caddyserver.com/api/download?os=linux&arch=amd64 -o /usr/local/bin/caddy
   chmod +x /usr/local/bin/caddy
   ```

   编辑 `/etc/caddy/Caddyfile`：

   ```caddyfile
   pal.example.com {
       reverse_proxy 127.0.0.1:8080
   }
   ```

   > 由于容器映射端口时用了 `0.0.0.0`，Caddy 反代到宿主机 8080 即可。

---

## 9. 日常运维

```bash
# 查看所有容器状态
docker compose ps

# 看日志（哪个服务出问题就盯哪个）
docker compose logs -f api
docker compose logs -f agent-web
docker compose logs -f web

# 更新代码后重新部署
cd /opt/pl-agent
git pull          # 或重新 scp
docker compose up -d --build

# 重启/停止
docker compose restart
docker compose down
```

---

## 10. 常见问题排查

| 症状 | 排查 |
|------|------|
| 浏览器打不开 8080 | ① 安全组是否放行 8080；② `docker compose ps` 是否 healthy；③ 服务器 `curl localhost:8080` |
| api 一直 unhealthy | `docker compose logs api`，常见是数据库连接或灌数据失败 |
| agent-web 启动失败 | 检查 `.env` 里 `LLM_API_KEY` 是否填对 |
| 服务器内存不足 | 建议 2C4G 起步；可加 2G swap（见附录） |
| 容器内无法联网（拉镜像慢） | 配置 Docker 国内镜像加速（见附录） |

---

## 11. GitHub Actions 自动部署（可选）⭐

推送到 `main` 分支后，自动把代码同步到服务器并 `docker compose up -d --build`，从此不用手动 scp。

### 原理

```
git push main → GitHub Actions → SSH 连服务器 → rsync 同步 /opt/pl-agent → 生成 .env → docker compose up -d --build
```

workflow 文件在 `.github/workflows/deploy.yml`，已随本项目提供。

### 前置条件

1. 服务器已按第 3 步装好 Docker
2. 安全组已放行 22（SSH 密钥登录需要）
3. 代码已推送到 GitHub 仓库（`git push origin main`）

### 配置步骤

**① 生成部署专用密钥对**（在你的 Mac 终端执行）：

```bash
ssh-keygen -t ed25519 -f ~/.ssh/aliyun_deploy -C "github-actions"
cat ~/.ssh/aliyun_deploy.pub   # 复制输出的公钥内容
```

**② 把公钥加到服务器**（在 Workbench 终端执行）：

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "粘贴上一步的公钥内容" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

> 验证：在 Mac 执行 `ssh -i ~/.ssh/aliyun_deploy root@<IP> echo ok`，能输出 `ok` 就通了。

**③ 配置 GitHub Secrets**（5 个）

GitHub 仓库 → **Settings → Secrets and variables → Actions** → New repository secret：

| Secret 名 | 值 |
|-----------|-----|
| `SERVER_HOST` | 服务器公网 IP |
| `SERVER_USER` | `root` |
| `SERVER_SSH_KEY` | `~/.ssh/aliyun_deploy` 私钥全文（含 `-----BEGIN...` 到 `END...` 全部行） |
| `LLM_API_KEY` | DeepSeek API Key |
| `AUTH_SECRET` | 随机长字符串（`openssl rand -hex 32` 生成） |

> 之后 `.env` 无需再手动维护，CI 会用 `LLM_API_KEY` / `AUTH_SECRET` 自动生成。

**④ 推送 workflow 并触发**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: 添加阿里云自动部署"
git push origin main
```

push 会自动触发；也可以到 GitHub → **Actions** → `Deploy to Aliyun ECS` → **Run workflow** 手动触发一次验证。

### 日常使用

```bash
git add . && git commit -m "更新功能"
git push origin main     # 剩下的交给 CI
```

### 注意事项

- 数据库数据存在 docker 卷 `pgdata`，重新部署**不会丢数据**
- `.env` 由 CI 生成、不进仓库；服务器上手动改的 `.env` 会被 CI 覆盖（属正常）
- 首次构建较慢（拉镜像 + 编译前端），之后增量很快
- 排查：GitHub → Actions → 点失败的 run 看日志；或服务器执行 `docker compose logs api`
- 如果服务器不想用 root，可改用有 sudo 权限的普通用户，并在脚本里加 `sudo`

---

## 附录

### A. Docker 国内镜像加速（中国大陆服务器拉镜像慢时）

编辑 `/etc/docker/daemon.json`：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com"
  ]
}
```

然后：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### B. 给服务器加 Swap（内存不够用时）

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h   # 验证
```

### C. 本机配置 SSH 密钥免密登录（可选）

```bash
# Mac 上执行
ssh-keygen -t ed25519
ssh-copy-id root@<你的公网IP>
ssh root@<你的公网IP>   # 之后免密
```
