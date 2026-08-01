# syntax=docker/dockerfile:1
# ============================================================
# 幻兽帕鲁配种 Agent — Web 前端 (构建产物由 nginx 服务)
# ============================================================
FROM node:20-alpine AS build

WORKDIR /app

# 复制依赖清单并安装（利用缓存）
COPY packages/web/package.json packages/web/package-lock.json* /app/packages/web/
WORKDIR /app/packages/web
RUN npm ci --ignore-scripts --cache /tmp/npm-cache

# 复制源码并构建
COPY packages/web/ /app/packages/web/
# 构建期注入后端地址：默认同源（由 nginx 反代），避免跨域；可被 ARG 覆盖
ARG VITE_AGENT_SERVICE_BASE_URL=""
ARG VITE_API_BASE_URL=""
ENV VITE_AGENT_SERVICE_BASE_URL=$VITE_AGENT_SERVICE_BASE_URL \
    VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ── nginx 服务层 ──
FROM nginx:1.27-alpine
COPY --from=build /app/packages/web/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
