.PHONY: install test test-unit test-smoke test-all test-agent-service test-contract-agent-service lint clean scrape demo serve serve-agent-service help

PYTHONPATH := packages/core:packages/adapters:packages/api:packages
export PYTHONPATH

install:
	uv sync

test:
	uv run pytest packages/core/pl_agent/core/__tests__/ tests/smoke/ -v

test-unit:
	uv run pytest packages/core/pl_agent/core/__tests__/ -v

test-smoke:
	uv run pytest tests/smoke/ -v

test-all:
	uv run pytest packages/adapters/adapters/paldb/__tests__/ packages/core/pl_agent/core/__tests__/ tests/smoke/ -v
	cd agent-service && uv run --with pytest --with pytest-asyncio pytest -q

test-agent-service:
	cd agent-service && uv run --with pytest --with pytest-asyncio pytest -q

test-contract-agent-service:
	cd agent-service && uv run --with pytest --with pytest-asyncio pytest tests/contract -q

test-api:
	uv run pytest packages/api/pl_agent/api/__tests__/ -v

scrape:
	uv run python packages/adapters/adapters/paldb/demo/run_scraper.py

demo:
	uv run python packages/core/demo/engine_demo.py

serve:
	uv run uvicorn pl_agent.api.main:app --reload --port 8000

serve-agent-service:
	cd agent-service && uv run uvicorn pl_agent_agent.app:app --reload --port 9000

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
	@echo "  make test         运行核心 + 冒烟测试"
	@echo "  make test-unit    仅单元测试"
	@echo "  make test-smoke   仅冒烟测试"
	@echo "  make test-all     全部测试"
	@echo "  make test-api     API 集成测试"
	@echo "  make test-agent-service   agent-service 全量测试"
	@echo "  make test-contract-agent-service   agent-service 契约测试"
	@echo "  make scrape       从 paldb.cc 抓取数据"
	@echo "  make demo         引擎功能演示"
	@echo "  make serve        启动 API 服务"
	@echo "  make serve-agent-service   启动 agent-service"
	@echo "  make lint         代码检查"
	@echo "  make format       自动格式化"
	@echo "  make clean        清理缓存"
	@echo "  make clean-all    清理所有 (含 venv)"
