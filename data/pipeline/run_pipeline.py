"""
UIUC Airfoil Data Pipeline — Main Runner
==========================================
Orchestrates:
  1. Scrape .dat files from UIUC (or load from local cache)
  2. Parse each file (auto-detect Selig / Lednicer)
  3. Normalize + resample + extract features
  4. Save:
       processed/coords.npy      shape (N, 400) float32 — ML input
       processed/metadata.json   per-airfoil name, format, features
       processed/names.txt       index → filename mapping
       processed/stats.json      dataset-level statistics
       processed/skipped.json    failed files and reasons

Usage:
  python run_pipeline.py                  # download + process everything
  python run_pipeline.py --no-scrape      # skip download, use cached .dat files
  python run_pipeline.py --limit 30       # process first 30 (quick test)
  python run_pipeline.py --resume         # skip already-downloaded .dat files
"""

import json
import logging
import argparse
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "uiuc_airfoils" / "raw"
OUT_DIR = Path(__file__).parent.parent / "uiuc_airfoils" / "processed"


def run(scrape: bool = True, limit: int | None = None, resume: bool = False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Download ──────────────────────────────────────────────────────
    if scrape:
        log.info("=== STEP 1: Downloading .dat files from UIUC ===")
        from scraper import run as scrape_run
        scrape_run(limit=limit, resume=resume)
    else:
        log.info("=== STEP 1: Skipping download (--no-scrape) ===")

    dat_files = sorted(RAW_DIR.glob("*.dat"))
    if limit:
        dat_files = dat_files[:limit]
    log.info("Found %d .dat files in %s", len(dat_files), RAW_DIR)

    if not dat_files:
        log.error("No .dat files found in %s — run without --no-scrape first", RAW_DIR)
        return

    # ── Steps 2 & 3: Parse + Normalize ───────────────────────────────────────
    log.info("=== STEPS 2–3: Parsing and normalizing ===")
    from parser import parse_dat
    from normalizer import process, N_RESAMPLE

    vectors  = []
    metadata = []
    skipped  = []

    for i, dat_path in enumerate(dat_files):
        if i > 0 and i % 200 == 0:
            log.info("  Progress: %d / %d  (ok=%d skipped=%d)",
                     i, len(dat_files), len(vectors), len(skipped))

        airfoil = parse_dat(dat_path)
        if airfoil is None:
            skipped.append({"file": dat_path.name, "reason": "parse_failed"})
            continue

        processed = process(airfoil)
        if processed is None:
            skipped.append({"file": dat_path.name, "reason": "normalize_failed"})
            continue

        vectors.append(processed.vector)
        metadata.append({
            "index":        len(metadata),
            "name":         processed.name,
            "file":         dat_path.name,
            "format":       processed.fmt,
            "n_pts_raw":    airfoil.n_pts,
            **processed.features,
        })

    log.info(
        "Result: %d ok, %d skipped out of %d files",
        len(vectors), len(skipped), len(dat_files)
    )

    if not vectors:
        log.error("No airfoils processed — check your .dat files in %s", RAW_DIR)
        return

    # ── Step 4: Save outputs ──────────────────────────────────────────────────
    log.info("=== STEP 4: Saving outputs ===")

    # coords.npy — primary ML input
    coords = np.array(vectors, dtype=np.float32)
    np.save(OUT_DIR / "coords.npy", coords)
    log.info("  coords.npy     shape=%s  dtype=%s", coords.shape, coords.dtype)

    # metadata.json
    with open(OUT_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("  metadata.json  %d entries", len(metadata))

    # names.txt — human readable index
    with open(OUT_DIR / "names.txt", "w") as f:
        for m in metadata:
            f.write(f"{m['index']:04d}  {m['file']:<32s}  {m['name']}\n")

    # stats.json
    thick  = [m["max_thickness"] for m in metadata]
    camber = [m["max_camber"]    for m in metadata]
    stats  = {
        "n_airfoils":        len(metadata),
        "n_skipped":         len(skipped),
        "vector_dim":        int(2 * N_RESAMPLE),
        "n_points_per_foil": N_RESAMPLE,
        "thickness": {
            "mean": round(float(np.mean(thick)), 4),
            "std":  round(float(np.std(thick)),  4),
            "min":  round(float(np.min(thick)),  4),
            "max":  round(float(np.max(thick)),  4),
        },
        "camber": {
            "mean": round(float(np.mean(camber)), 4),
            "std":  round(float(np.std(camber)),  4),
            "min":  round(float(np.min(camber)),  4),
            "max":  round(float(np.max(camber)),  4),
        },
        "n_symmetric":      sum(1 for m in metadata if m["is_symmetric"]),
        "n_cambered":       sum(1 for m in metadata if not m["is_symmetric"]),
        "n_selig_format":   sum(1 for m in metadata if m["format"] == "selig"),
        "n_lednicer_format":sum(1 for m in metadata if m["format"] == "lednicer"),
    }
    with open(OUT_DIR / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    # skipped.json — for debugging
    if skipped:
        with open(OUT_DIR / "skipped.json", "w") as f:
            json.dump(skipped, f, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("=== Pipeline complete ===")
    log.info("  Airfoils processed : %d", stats["n_airfoils"])
    log.info("  Skipped            : %d", stats["n_skipped"])
    log.info("  Vector shape       : (%d, %d)", len(metadata), stats["vector_dim"])
    log.info("  Mean thickness t/c : %.3f", stats["thickness"]["mean"])
    log.info("  Symmetric          : %d  |  Cambered: %d",
             stats["n_symmetric"], stats["n_cambered"])
    log.info("  Output dir         : %s", OUT_DIR)

    return coords, metadata, stats


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="UIUC airfoil data pipeline")
    p.add_argument("--no-scrape", action="store_true", help="Skip download step")
    p.add_argument("--limit",  type=int, default=None, help="Process only first N files")
    p.add_argument("--resume", action="store_true",    help="Skip already-downloaded files")
    args = p.parse_args()
    run(scrape=not args.no_scrape, limit=args.limit, resume=args.resume)
