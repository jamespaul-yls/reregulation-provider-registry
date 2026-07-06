"""Entrypoint: python -m pipeline.scrape

Runs all registered scrapers in sequence, writing snapshots to data/raw/
and persisting parsed rows to the dev database.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# Registered scrapers (add new sources here as they are built)
_REGISTERED = [
    "scrapers.arizona_abs.ArizonaAbsScraper",
    "scrapers.utah_sandbox.UtahSandboxScraper",
    "scrapers.arizona_lp.ArizonaLpScraper",
    "scrapers.utah_lpp.UtahLppScraper",
    "scrapers.colorado_llp.ColoradoLlpScraper",
    "scrapers.minnesota_lp.MinnesotaLpScraper",
    "scrapers.washington_lllt.WashingtonLlltScraper",
    "scrapers.texas_alp.TexasAlpScraper",
    "scrapers.california_lda.CaliforniaLdaScraper",
]


def main() -> None:
    logger.info("Registered scrapers: %s", _REGISTERED)
    logger.info(
        "Run individual pipeline scripts in scripts/ to execute each scraper. "
        "Full orchestration (parallel fetch, DB load, export) to be added in v2."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
