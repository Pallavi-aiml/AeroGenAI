"""
Airfoil Normalizer & Feature Extractor
========================================
Takes a parsed Airfoil and produces:
  1. Normalized coordinates — chord=1.0, LE at (0,0)
  2. Resampled to 200 pts with cosine spacing
  3. Geometric features (thickness, camber, le_radius, etc.)
  4. Flat ML vector [x0,y0,...] shape (400,)

Key fix: auto-detects percent-chord files (x ~ 0..100) and scales to 0..1
before validation. This recovers GOE, RAF, Clark, Wortmann, USA, etc. families.
"""

import logging
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import CubicSpline

from parser import Airfoil

log = logging.getLogger(__name__)

N_RESAMPLE = 200


@dataclass
class ProcessedAirfoil:
    name:     str
    fmt:      str
    x:        np.ndarray
    y:        np.ndarray
    vector:   np.ndarray
    features: dict

    def to_dict(self) -> dict:
        return {"name": self.name, "format": self.fmt,
                "x": self.x.tolist(), "y": self.y.tolist(),
                "features": self.features}


# ── step 1: normalize ─────────────────────────────────────────────────────────

def _normalize_chord(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Normalize so chord = 1.0 and LE at (0, 0).
    Auto-detects percent-chord notation: if max(x) > 2.0, divides by 100 first.
    This recovers GOE, RAF, USA, Clark, Wortmann families stored as percent chord.
    """
    # Auto-scale percent-chord files (x ~ 0..100) → unit chord (x ~ 0..1)
    x_max = float(np.max(x))
    if x_max > 2.0:
        scale = x_max
        x = x / scale
        y = y / scale

    le_idx = int(np.argmin(x))
    x = x - x[le_idx]
    y = y - y[le_idx]

    te_x = 0.5 * (x[0] + x[-1])
    te_y = 0.5 * (y[0] + y[-1])
    chord = te_x if te_x > 1e-6 else float(np.max(x))
    if chord < 1e-6:
        raise ValueError("Cannot determine chord length")

    if abs(te_y) > 1e-4:
        angle = np.arctan2(te_y, te_x)
        ca, sa = np.cos(-angle), np.sin(-angle)
        x, y = x * ca - y * sa, x * sa + y * ca

    return x / chord, y / chord


# ── step 2: split surfaces ────────────────────────────────────────────────────

def _split_surfaces(x, y):
    le_idx = int(np.argmin(x))
    x_upper = x[:le_idx + 1][::-1].copy()
    y_upper = y[:le_idx + 1][::-1].copy()
    x_lower = x[le_idx:].copy()
    y_lower = y[le_idx:].copy()

    def monotonize(xv, yv):
        keep = [0]
        for i in range(1, len(xv)):
            if xv[i] > xv[keep[-1]] + 1e-8:
                keep.append(i)
        return xv[keep], yv[keep]

    return (*monotonize(x_upper, y_upper), *monotonize(x_lower, y_lower))


# ── step 3: cosine resample ───────────────────────────────────────────────────

def _cosine_resample(x_upper, y_upper, x_lower, y_lower, n=N_RESAMPLE):
    n_up = n // 2 + 1
    n_lo = n // 2

    def resample(xs, ys, n_pts):
        t = np.clip(0.5 * (1 - np.cos(np.linspace(0, np.pi, n_pts))), xs[0], xs[-1])
        return t, CubicSpline(xs, ys)(t)

    x_u, y_u = resample(x_upper, y_upper, n_up)
    x_l, y_l = resample(x_lower, y_lower, n_lo)

    x_out = np.concatenate([x_u[::-1], x_l[1:]])
    y_out = np.concatenate([y_u[::-1], y_l[1:]])
    assert len(x_out) == n
    return x_out, y_out


# ── step 4: geometric features ────────────────────────────────────────────────

def _extract_features(x_upper, y_upper, x_lower, y_lower) -> dict:
    x_grid = np.linspace(0.0, 1.0, 500)
    y_u = CubicSpline(x_upper, y_upper, extrapolate=False)(x_grid)
    y_l = CubicSpline(x_lower, y_lower, extrapolate=False)(x_grid)
    for arr in (y_u, y_l):
        mask = np.isnan(arr)
        if mask.any():
            arr[mask] = np.interp(x_grid[mask], x_grid[~mask], arr[~mask])

    thickness = y_u - y_l
    camber    = 0.5 * (y_u + y_l)
    i_t = int(np.argmax(thickness))
    i_c = int(np.argmax(np.abs(camber)))

    try:
        n = min(10, len(x_upper))
        cs = CubicSpline(x_upper[:n], y_upper[:n])
        dy, ddy = cs(x_upper[0], 1), cs(x_upper[0], 2)
        k = abs(ddy) / (1 + dy**2)**1.5
        le_radius = float(1.0 / k) if k > 1e-6 else 0.05
    except Exception:
        le_radius = float("nan")

    te_angle_deg = float(np.degrees(np.arctan2(float(y_u[-1]) - float(y_l[-1]), 0.02)))
    trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))

    return {
        "max_thickness":   float(np.max(thickness)),
        "max_thickness_x": float(x_grid[i_t]),
        "max_camber":      float(camber[i_c]),
        "max_camber_x":    float(x_grid[i_c]),
        "le_radius":       le_radius,
        "te_angle_deg":    te_angle_deg,
        "upper_area":      float(trapz(y_u, x_grid)),
        "lower_area":      float(trapz(y_l, x_grid)),
        "is_symmetric":    bool(float(np.max(np.abs(camber))) < 0.002),
    }


# ── validation (runs on NORMALIZED coords) ────────────────────────────────────

def _validate_normalized(x: np.ndarray, y: np.ndarray, name: str) -> tuple[bool, str]:
    """Validate after normalization — coordinates should be in 0..1 / -0.5..0.5 range."""
    if len(x) < 15:
        return False, f"too few points ({len(x)})"
    if np.any(np.isnan(x)) or np.any(np.isnan(y)):
        return False, "NaN in coordinates"
    if np.max(x) - np.min(x) < 0.5:
        return False, "chord range too small after normalization"
    if np.max(np.abs(y)) > 0.6:
        return False, f"y still out of range after normalization (max={np.max(np.abs(y)):.3f})"
    return True, ""


# ── public API ────────────────────────────────────────────────────────────────

def process(airfoil: Airfoil) -> "ProcessedAirfoil | None":
    """Full pipeline: auto-scale → normalize → split → resample → features → vector."""
    if len(airfoil.x) < 10:
        log.warning("Skipping %s: too few raw points (%d)", airfoil.name, len(airfoil.x))
        return None
    if np.any(np.isnan(airfoil.x)) or np.any(np.isnan(airfoil.y)):
        log.warning("Skipping %s: NaN in raw coords", airfoil.name)
        return None

    try:
        x_n, y_n = _normalize_chord(airfoil.x, airfoil.y)

        ok, reason = _validate_normalized(x_n, y_n, airfoil.name)
        if not ok:
            log.warning("Skipping %s: %s", airfoil.name, reason)
            return None

        x_up, y_up, x_lo, y_lo = _split_surfaces(x_n, y_n)
        if len(x_up) < 5 or len(x_lo) < 5:
            log.warning("Skipping %s: surface split failed", airfoil.name)
            return None

        x_rs, y_rs = _cosine_resample(x_up, y_up, x_lo, y_lo, n=N_RESAMPLE)
        features   = _extract_features(x_up, y_up, x_lo, y_lo)

        vector       = np.empty(2 * N_RESAMPLE, dtype=np.float32)
        vector[0::2] = x_rs
        vector[1::2] = y_rs

        return ProcessedAirfoil(name=airfoil.name, fmt=airfoil.fmt,
                                x=x_rs, y=y_rs, vector=vector, features=features)
    except Exception as e:
        log.warning("Error processing %s: %s", airfoil.name, e)
        return None
