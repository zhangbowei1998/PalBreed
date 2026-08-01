.PHONY: install install-web test test-unit test-smoke test-all test-agent test-agent-web test-web lint clean scrape demo serve serve-agent-service serve-web build-web help

PYTHONPATH := packages/core:packages/adapters:packages/api:packages/agent:packages/agent-web:packages
export PYTHONPATH

install:
	uv sync

install-web:
	cd packages/web && npm_config_cache=.npm-cache npm install

test:
	uv run pytest packages/core/pl_agent/core/__tests__/ tests/smoke/ -v

test-unit:
	uv run pytest packages/core/pl_agent/core/__tests__/ -v

test-smoke:
	uv run pytest tests/smoke/ -v

test-all:
	uv run pytest packages/adapters/adapters/paldb/__tests__/ packages/core/pl_agent/core/__tests__/ tests/smoke/ -v
	uv run pytest packages/agent/pl_agent/agent/__tests__/ packages/agent-web/tests/ -q
	cd packages/web && npm_config_cache=.npm-cache npm install && npm run build

test-agent:
	uv run pytest packages/agent/pl_agent/agent/__tests__/ packages/agent/pl_agent/agent/intent/__tests__/ packages/agent/pl_agent/agent/llm/__tests__/ -q

test-agent-web:
	uv run pytest packages/agent-web/tests -q

test-web:
	cd packages/web && npm_config_cache=.npm-cache npm install && npm run build

test-api:
	uv run pytest packages/api/pl_agent/api/__tests__/ -v

scrape:
	uv run python packages/adapters/adapters/paldb/demo/run_scraper.py

demo:
	uv run python packages/core/demo/engine_demo.py

serve:
	uv run uvicorn pl_agent.api.main:app --reload --port 8000

serve-agent-service:
	uv run uvicorn pl_agent.agent_web.app:app --reload --port 9000

serve-web:
	cd packages/web && npm_config_cache=.npm-cache npm install && npm run dev

build-web:
	cd packages/web && npm_config_cache=.npm-cache npm install && npm run build

lint:
	uv run ruff check packages/

format:
	uv run ruff format packages/
	uv run ruff check --fix packages/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name '*.pyc' -delete 2>/dev/null; true
	rm -rf .pytest_cache .ruff_cache dist/ *.egg-info

clean-all: clean
	rm -rf .venv

help:
	@echo "pl-agent 常用命令"
	@echo ""
	@echo "  make install      安装依赖"
	@echo "  make install-web  安装 web 依赖"
	@echo "  make test         运行核心 + 冒烟测试"
	@echo "  make test-unit    仅单元测试"
	@echo "  make test-smoke   仅冒烟测试"
	@echo "  make test-all     全部测试"
	@echo "  make test-api     API 集成测试"
	@echo "  make test-agent   agent 模块测试"
	@echo "  make test-agent-web   agent-web 服务测试"
	@echo "  make test-web     web 构建校验"
	@echo "  make scrape       从 paldb.cc 抓取数据"
	@echo "  make demo         引擎功能演示"
	@echo "  make serve        启动 API 服务"
	@echo "  make serve-agent-service   启动 agent-web 服务（端口 9000）"
	@echo "  make serve-web    启动 web 前端"
	@echo "  make build-web    构建 web 前端"
	@echo "  make lint         代码检查"
	@echo "  make format       自动格式化"
	@echo "  make clean        清理缓存"
	@echo "  make clean-all    清理所有 (含 venv)"
