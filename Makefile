.PHONY: install sync setup shell info sql ingest report mcp-check mcp-config clean debug

UV ?= uv
PYTHON ?= $(UV) run python
ROOT := $(shell pwd)

install:
	$(UV) sync --all-extras

sync: install

setup: install
	$(PYTHON) scripts/mcp_server.py --check
	@$(MAKE) debug

shell:
	$(UV) run ipython

info:
	$(PYTHON) -m src.cli info

sql:
	@test -n "$(QUERY)" || (echo "Usage: make sql QUERY='SELECT 1'"; exit 1)
	$(PYTHON) -m src.cli sql "$(QUERY)"

ingest:
	@test -n "$(FILE)" || (echo "Usage: make ingest FILE=data/landing/foo.csv TABLE=foo"; exit 1)
	@test -n "$(TABLE)" || (echo "Usage: make ingest FILE=data/landing/foo.csv TABLE=foo"; exit 1)
	$(PYTHON) scripts/ingest.py "$(FILE)" "$(TABLE)"

report:
	@test -n "$(TABLE)" || (echo "Usage: make report TABLE=my_table"; exit 1)
	$(PYTHON) scripts/stat_report.py "$(TABLE)"

mcp-check:
	$(PYTHON) scripts/mcp_server.py --check

mcp-config:
	$(PYTHON) scripts/configure_mcp.py

clean:
	rm -rf .venv reports/*.md __pycache__ src/__pycache__ scripts/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

debug:
	@echo "=== Environment ==="
	@$(UV) --version 2>/dev/null || echo "uv not found — install: curl -LsSf https://astral.sh/uv/install.sh | sh"
	@echo "=== Paths ==="
	@echo "  ROOT=$(ROOT)"
	@echo "=== Database ==="
	@$(PYTHON) -m src.cli info 2>/dev/null || echo "Run 'make install' first"
	@echo "=== MCP launcher ==="
	@test -x scripts/run_mcp.sh && echo "  scripts/run_mcp.sh (executable)" || echo "  chmod +x scripts/run_mcp.sh"
	@echo "=== DuckDB CLI (optional) ==="
	@duckdb --version 2>/dev/null || echo "duckdb CLI not installed (optional)"
