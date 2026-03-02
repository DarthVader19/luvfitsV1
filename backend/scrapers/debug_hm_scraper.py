"""
Debug runner for H&M scraper.

Usage:
    python .\scrapers\debug_hm_scraper.py
    python .\scrapers\debug_hm_scraper.py --urls 2 --items 15 --output hm_debug_report.json
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

try:
    from .hm_scraper import HMScraper
except ImportError:
    # Allow direct execution from backend folder.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from hm_scraper import HMScraper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug H&M scraper step-by-step")
    parser.add_argument(
        "--urls",
        type=int,
        default=1,
        help="Number of category URLs to test per category",
    )
    parser.add_argument(
        "--items",
        type=int,
        default=10,
        help="Max items to parse per tested URL",
    )
    parser.add_argument(
        "--output",
        default="hm_debug_report.json",
        help="Path to save debug JSON report",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    scraper = HMScraper()
    report = await scraper.debug_scrape(
        max_urls_per_category=max(1, args.urls),
        max_items_per_url=max(1, args.items),
    )

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("H&M debug complete")
    print(json.dumps(report["totals"], indent=2))
    print(f"Saved debug report: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
