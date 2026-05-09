"""
UIUC Airfoil .dat File Parser - FIXED VERSION
Handles both Selig and Lednicer formats.

Key fix: Lednicer files use count header to split upper/lower blocks,
NOT a blank line. Both variants (with and without blank separator) are supported.
"""

import re
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Airfoil:
    name:  str
    fmt:   str
    x:     np.ndarray
    y:     np.ndarray

    @property
    def n_pts(self) -> int:
        return len(self.x)


def _strip_comments(lines: list[str]) -> list[str]:
    return [l for l in lines if not l.strip().startswith("#")]


def _parse_xy(line: str) -> tuple[float, float] | None:
    line = re.sub(r"\(([0-9.]+)\)", r"-\1", line)
    parts = line.split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def _is_lednicer_count_line(line: str) -> bool:
    """Second line of Lednicer files: two floats like '25.   25.'"""
    parts = line.strip().split()
    if len(parts) != 2:
        return False
    try:
        a, b = float(parts[0]), float(parts[1])
        return 5 <= a <= 500 and 5 <= b <= 500 and a == int(a) and b == int(b)
    except ValueError:
        return False


def _parse_selig(name: str, coord_lines: list[str]) -> 'Airfoil | None':
    coords = [_parse_xy(l) for l in coord_lines if l.strip()]
    coords = [c for c in coords if c is not None]
    if len(coords) < 10:
        log.warning("Selig %s: too few points (%d)", name, len(coords))
        return None
    x = np.array([c[0] for c in coords])
    y = np.array([c[1] for c in coords])
    return Airfoil(name=name, fmt="selig", x=x, y=y)


def _parse_lednicer(name: str, count_line: str, remaining_lines: list[str]) -> 'Airfoil | None':
    """
    Parse Lednicer format using the count header to split blocks.
    
    CRITICAL FIX: Real UIUC Lednicer files often have NO blank line between
    upper and lower surface blocks. We use n_upper from the count header
    to split the data — do NOT rely on blank lines.
    
    Supports both:
      - Files with blank line separator (collect all coords, split by count)
      - Files without blank line separator (split by count directly)
    """
    parts = count_line.strip().split()
    try:
        n_upper = int(float(parts[0]))
        n_lower = int(float(parts[1]))
    except (ValueError, IndexError):
        log.warning("Lednicer %s: bad count header: %r", name, count_line)
        return None

    # Collect ALL valid coordinate pairs from remaining lines (ignore blanks)
    # Skip any line that looks like the count header (two equal integers)
    all_coords = []
    for line in remaining_lines:
        if not line.strip():
            continue
        pt = _parse_xy(line)
        if pt is None:
            continue
        if pt[0] >= n_upper or pt[1] >= n_upper:
            continue
        all_coords.append(pt)

    total_expected = n_upper + n_lower
    if len(all_coords) < total_expected:
        # Try with tolerance: accept if we have at least 80% of expected
        if len(all_coords) < max(10, int(0.8 * total_expected)):
            log.warning(
                "Lednicer %s: too few points (got=%d expected=%d)",
                name, len(all_coords), total_expected
            )
            return None
        # Use what we have, split proportionally
        n_upper = round(n_upper * len(all_coords) / total_expected)

    # Split by count: first n_upper = upper surface (LE→TE), rest = lower (LE→TE)
    upper = all_coords[:n_upper]
    lower = all_coords[n_upper:n_upper + n_lower]

    if len(upper) < 5 or len(lower) < 5:
        log.warning(
            "Lednicer %s: too few points after split (upper=%d lower=%d)",
            name, len(upper), len(lower)
        )
        return None

    # Convert to Selig: TE→upper(reversed)→LE + LE→lower→TE (skip shared LE)
    combined = list(reversed(upper)) + lower[1:]
    x = np.array([c[0] for c in combined])
    y = np.array([c[1] for c in combined])
    return Airfoil(name=name, fmt="lednicer", x=x, y=y)


def parse_dat(filepath: Path) -> 'Airfoil | None':
    try:
        raw = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        log.error("Cannot read %s: %s", filepath, e)
        return None

    if not raw:
        return None

    # First non-blank, non-comment line = airfoil name
    name, name_idx = "", 0
    for i, line in enumerate(raw):
        s = line.strip()
        if s and not s.startswith("#"):
            name, name_idx = s, i
            break

    after_name = _strip_comments(raw[name_idx + 1:])
    non_blank  = [l for l in after_name if l.strip()]

    if not non_blank:
        return None

    # Format detection
    if _is_lednicer_count_line(non_blank[0]):
        # Pass count line + all remaining lines (including blanks for compat)
        return _parse_lednicer(name, non_blank[0], after_name[1:])
    else:
        return _parse_selig(name, non_blank)
