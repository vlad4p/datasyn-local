.PHONY: install sync shell info sql ingest report clean debug

UV ?= uv
PYTHON ?= $(UV) run python

install:
	$(UV) sync --all-extras

sync: install

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

boletin:
	@test -n "$(FECHA)" || (echo "Usage: make boletin FECHA=2026-06-02"; exit 1)
	$(PYTHON) scripts/scrape_boletin.py "$(FECHA)" --save

boletin-semana:
	$(PYTHON) scripts/scrape_boletin.py --ultimos 7 --ingest

boletin-merge:
	$(PYTHON) -c "from src.boletin_oficial import merge_boletin_into_main; print('Filas:', merge_boletin_into_main())"

clean:
	rm -rf .venv reports/*.md __pycache__ src/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

debug:
	@echo "=== Environment ==="
	@$(UV) --version 2>/dev/null || echo "uv not found — install: curl -LsSf https://astral.sh/uv/install.sh | sh"
	@echo "=== Database ==="
	@$(PYTHON) -m src.cli info 2>/dev/null || echo "Run 'make install' first"
	@echo "=== DuckDB CLI (optional) ==="
	@duckdb --version 2>/dev/null || echo "duckdb CLI not installed (optional)"
