"""
Airfoil Generator Service
Generates NACA 4-digit airfoils and searches the UIUC processed database.
"""

import json
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

N = 200  # output points

# Path to processed database (relative to project root)
_BASE = Path(__file__).parent.parent.parent
_META_PATH   = _BASE / "data" / "uiuc_airfoils" / "processed" / "metadata.json"
_COORDS_PATH = _BASE / "data" / "uiuc_airfoils" / "processed" / "coords.npy"

_metadata: list[dict] | None = None
_coords:   np.ndarray | None = None


def _load_database() -> bool:
    global _metadata, _coords
    if _metadata is not None:
        return True
    if not _META_PATH.exists():
        log.warning("metadata.json not found — run Phase 1 pipeline first")
        return False
    _metadata = json.loads(_META_PATH.read_text())
    if _COORDS_PATH.exists():
        _coords = np.load(_COORDS_PATH)
    log.info("Loaded UIUC database: %d airfoils", len(_metadata))
    return True


# ── NACA 4-digit ──────────────────────────────────────────────────────────────

def naca4(m: float, p: float, t: float, n: int = N):
    """Generate NACA 4-digit airfoil coordinates."""
    n_half = n // 2 + 1
    beta = np.linspace(0, np.pi, n_half)
    xc   = 0.5 * (1 - np.cos(beta))

    # Thickness
    yt = (t / 0.2) * (
        0.2969 * np.sqrt(xc)
        - 0.1260 * xc
        - 0.3516 * xc**2
        + 0.2843 * xc**3
        - 0.1015 * xc**4
    )

    # Camber
    if m > 0.0001:
        yc = np.where(xc < p,
            (m / p**2) * (2*p*xc - xc**2),
            (m / (1-p)**2) * ((1-2*p) + 2*p*xc - xc**2)
        )
        dyc = np.where(xc < p,
            (2*m / p**2) * (p - xc),
            (2*m / (1-p)**2) * (p - xc)
        )
    else:
        yc  = np.zeros_like(xc)
        dyc = np.zeros_like(xc)

    theta = np.arctan(dyc)
    xu = xc - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = xc + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    x = np.concatenate([xu[::-1], xl[1:]])[:n]
    y = np.concatenate([yu[::-1], yl[1:]])[:n]
    return x.astype(np.float32), y.astype(np.float32)


# ── Database search ───────────────────────────────────────────────────────────

def search_database(
    thickness_min: float = 0.06,
    thickness_max: float = 0.20,
    camber_min:    float = 0.0,
    camber_max:    float = 0.10,
    limit:         int   = 12,
) -> list[dict]:
    if not _load_database():
        return []
    results = []
    for m in _metadata:
        t = m.get("max_thickness", 0)
        c = abs(m.get("max_camber", 0))
        if thickness_min <= t <= thickness_max and camber_min <= c <= camber_max:
            results.append({
                "index":         m["index"],
                "name":          m["name"],
                "file":          m["file"],
                "max_thickness": round(t, 4),
                "max_camber":    round(c, 4),
                "is_symmetric":  m.get("is_symmetric", False),
            })
        if len(results) >= limit:
            break
    return results


def get_airfoil_coords(idx: int) -> dict | None:
    if not _load_database() or _coords is None:
        return None
    if idx < 0 or idx >= len(_coords):
        return None
    vec = _coords[idx]
    x   = vec[0::2].tolist()
    y   = vec[1::2].tolist()
    m   = _metadata[idx]
    return {
        "name":     m["name"],
        "x":        x,
        "y":        y,
        "features": {
            "max_thickness":   m.get("max_thickness", 0),
            "max_thickness_x": m.get("max_thickness_x", 0.3),
            "max_camber":      m.get("max_camber", 0),
            "max_camber_x":    m.get("max_camber_x", 0.4),
            "is_symmetric":    m.get("is_symmetric", False),
        }
    }


# ── Public entry point ────────────────────────────────────────────────────────

def generate_airfoil(params: dict) -> dict | None:
    mode = params.get("mode", "naca4")

    if mode == "naca4":
        m = float(np.clip(params.get("max_camber",    0.02), 0.0,  0.10))
        p = float(np.clip(params.get("camber_pos",    0.40), 0.1,  0.9))
        t = float(np.clip(params.get("max_thickness", 0.12), 0.06, 0.20))

        x, y = naca4(m=m, p=p, t=t)

        M = int(round(m * 100))
        P = int(round(p * 10))
        T = int(round(t * 100))
        name = f"NACA {M}{P}{T:02d}"

        return {
            "name": name,
            "x":    x.tolist(),
            "y":    y.tolist(),
            "features": {
                "max_thickness":   round(t, 4),
                "max_thickness_x": 0.30,
                "max_camber":      round(m, 4),
                "max_camber_x":    round(p, 4),
                "is_symmetric":    m < 0.002,
            }
        }

    elif mode == "uiuc_lookup":
        results = search_database(
            thickness_min=params.get("thickness_min", 0.08),
            thickness_max=params.get("thickness_max", 0.15),
        )
        if not results:
            return None
        return get_airfoil_coords(results[0]["index"])

    return None
