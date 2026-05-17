# Makefile — gannon-storm-rtk-analysis
#
# Reproducible end-to-end run. Targets:
#   make all       — fetch indices, fetch RINEX, compute solutions, write
#                    figures + results/quantitative.md (~5-10 min cold cache,
#                    <30 s warm cache).
#   make fetch     — fetch only (CORS RINEX + GFZ Kp + Kyoto Dst).
#   make analyze   — run analysis assuming data is cached.
#   make plot      — regenerate figures only (assumes data is cached).
#   make test      — run pytest with coverage.
#   make typecheck — mypy on src/.
#   make lint      — ruff check + format check.
#   make clean     — remove caches but NOT data/ or results/.
#   make distclean — also remove data/ caches.

PYTHON ?= python
DATA_DIR ?= data
RESULTS_DIR ?= results
FIGURES_DIR ?= $(RESULTS_DIR)/figures

.PHONY: all fetch analyze plot test typecheck lint clean distclean help

help:
	@grep -E '^##' Makefile | sed -e 's/^## //'

## all       — Full pipeline: fetch + analyze + plot + write quantitative.md
all: fetch analyze plot

## fetch     — Download CORS RINEX and SWPC indices into $(DATA_DIR)/.
fetch:
	$(PYTHON) -c "from pathlib import Path; from gannon_analysis.fetch import fetch_window; from gannon_analysis.stations import stations_in_corridor; import httpx; \
client = httpx.Client(timeout=60.0); \
[fetch_window(s, Path('$(DATA_DIR)'), client=client) for s in stations_in_corridor()]; \
client.close()"
	$(PYTHON) -c "from pathlib import Path; from gannon_analysis.swpc import fetch_kp, fetch_dst; \
fetch_kp(cache_path=Path('$(DATA_DIR)/swpc/kp.txt')); \
fetch_dst(cache_path=Path('$(DATA_DIR)/swpc'))"

## analyze   — Run positioning + aggregates, write results/quantitative.md.
analyze:
	$(PYTHON) -c "from pathlib import Path; from gannon_analysis.analysis import run_analysis, write_quantitative_md; from gannon_analysis.stations import stations_in_corridor; \
b = run_analysis(stations_in_corridor(), data_dir=Path('$(DATA_DIR)')); \
write_quantitative_md(b, Path('$(RESULTS_DIR)/quantitative.md')); \
print(b['headline'].sentence())"

## plot      — Regenerate every figure under results/figures/.
plot:
	$(PYTHON) -c "from pathlib import Path; from gannon_analysis.analysis import run_analysis; from gannon_analysis.plotting import plot_regional_error_vs_time, plot_per_station_error_grid, plot_threshold_crossings_bars, plot_station_map; from gannon_analysis.stations import stations_in_corridor; \
b = run_analysis(stations_in_corridor(), data_dir=Path('$(DATA_DIR)')); \
out = Path('$(FIGURES_DIR)'); \
plot_regional_error_vs_time(b, out_path=out/'fig-01-regional-error-vs-time.png'); \
plot_per_station_error_grid(b, out_path=out/'fig-02-per-station-grid.png'); \
plot_threshold_crossings_bars(b, out_path=out/'fig-03-station-hours-over-threshold.png'); \
plot_station_map(b, out_path=out/'fig-04-station-map-peak-severity.png'); \
print('figures written to', out)"

## test      — pytest + coverage.
test:
	pytest

## typecheck — mypy --strict.
typecheck:
	mypy

## lint      — ruff check + format check.
lint:
	ruff check src tests
	ruff format --check src tests

## clean     — remove .pytest_cache, .mypy_cache, .ruff_cache, __pycache__.
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find src tests -type d -name __pycache__ -exec rm -rf {} +

## distclean — clean + remove data/ cache.
distclean: clean
	rm -rf $(DATA_DIR)/cors $(DATA_DIR)/swpc
