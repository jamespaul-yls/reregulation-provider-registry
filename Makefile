.PHONY: lint test scrape export reproduce audit install sync completeness

# ── dev setup ────────────────────────────────────────────────────────────────

install:
	uv sync --dev
	uv run playwright install chromium
	uv run pre-commit install

sync:
	uv sync --dev

# ── quality ──────────────────────────────────────────────────────────────────

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

test-slow:
	uv run pytest -m slow

# ── pipeline ─────────────────────────────────────────────────────────────────

# Run all scrapers (reads pyproject [tool.registry] for source list)
scrape:
	uv run python -m pipeline.scrape

# Diff latest snapshots → provider_status_event rows
diff:
	uv run python -m pipeline.diff

# Export dev DB → data/release/ CSV + Parquet + datapackage.json
export:
	uv run python -m pipeline.export

# Full reproducible rebuild from raw/ → DB → release/
# Does NOT re-fetch live URLs; works entirely from immutable snapshots.
# Runs provenance audit internally; exits non-zero on any violation.
reproduce:
	uv run python -m pipeline.reproduce

# Stand-alone provenance audit (also embedded in reproduce).
# Checks every published row has source_url, retrieved_at, and a
# resolvable source_snapshot; verifies every blob exists + sha256 matches.
audit:
	uv run python -m pipeline.audit

# Reproducible completeness audit: frame reconciliation against external
# program inventories (+ legislative-scan / within-program checks, once built).
# Writes validation/completeness.md and validation/residual_gaps.csv.
completeness:
	uv run python -m completeness.frame_reconcile
