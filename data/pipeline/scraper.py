"""
UIUC Airfoil Database Scraper
==============================
Downloads all ~1,650 .dat coordinate files from:
  https://m-selig.ae.illinois.edu/ads/coord_database.html

Usage:
  python scraper.py                  # download everything
  python scraper.py --limit 30       # first 30 only (for testing)
  python scraper.py --resume         # skip already-downloaded files
"""

import argparse
import time
import logging
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE_URL   = "https://m-selig.ae.illinois.edu/ads/"
INDEX_URL  = BASE_URL + "coord_database.html"
OUTPUT_DIR = Path(__file__).parent.parent / "uiuc_airfoils" / "raw"
DELAY_SEC  = 0.4   # polite delay — do not remove


def fetch_dat_links(session: requests.Session) -> list[tuple[str, str]]:
    """
    Parse the UIUC index page and return list of (name, url) tuples.
    The page lists .dat files as plain <a href="coord/xxxxx.dat"> links.
    """
    log.info("Fetching index: %s", INDEX_URL)
    resp = session.get(INDEX_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.endswith(".dat") and ("coord/" in href or not href.startswith("http")):
            full_url = urljoin(BASE_URL, href)
            stem = Path(href).stem   # e.g. "e168" from "coord/e168.dat"
            links.append((stem, full_url))

    log.info("Found %d .dat links", len(links))
    return links


def download_one(session: requests.Session, name: str, url: str, out_dir: Path) -> bool:
    """Download a single .dat file. Returns True on success."""
    dest = out_dir / f"{name}.dat"
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        dest.write_text(resp.text, encoding="utf-8")
        return True
    except requests.RequestException as e:
        log.warning("  FAILED %s: %s", name, e)
        return False


def run(limit: int | None = None, resume: bool = False):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = (
        "AeroGenAI-research/1.0 (student project; contact: your@email.com)"
    )

    links = fetch_dat_links(session)
    if limit:
        links = links[:limit]
        log.info("Limiting to first %d files", limit)

    ok, skipped, failed = 0, 0, 0

    for i, (name, url) in enumerate(links, 1):
        dest = OUTPUT_DIR / f"{name}.dat"

        if resume and dest.exists():
            skipped += 1
            continue

        log.info("[%d/%d] %s", i, len(links), name)
        if download_one(session, name, url, OUTPUT_DIR):
            ok += 1
        else:
            failed += 1

        time.sleep(DELAY_SEC)

    log.info("Done — ok: %d  skipped: %d  failed: %d", ok, skipped, failed)
    log.info("Files saved to: %s", OUTPUT_DIR)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit",  type=int, default=None, help="Max files to download")
    p.add_argument("--resume", action="store_true",    help="Skip already-downloaded files")
    args = p.parse_args()
    run(limit=args.limit, resume=args.resume)
