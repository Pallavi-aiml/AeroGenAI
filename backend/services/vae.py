"""
β-VAE Service  (Phase 5)
========================
Loads the trained VAE from  ml/vae_model.onnx  (exported by ml/train_vae.py).
Falls back to a PCA-based morphing method if the ONNX model is not present,
so the latent sliders still work immediately even before training.

Latent space: 16 dimensions.
Output:       200-point airfoil (x interleaved with y, total 400 floats).
"""

from __future__ import annotations
import json
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_BASE       = Path(__file__).parent.parent.parent
_MODEL_PATH = _BASE / "ml" / "vae_model.onnx"
_META_PATH  = _BASE / "data" / "uiuc_airfoils" / "processed" / "metadata.json"
_COORDS_PATH= _BASE / "data" / "uiuc_airfoils" / "processed" / "coords.npy"
_STATS_PATH = _BASE / "ml" / "latent_stats.json"

_session    = None   # ONNX runtime session
_pca_model  = None   # fallback PCA

LATENT_DIM = 16
N_POINTS   = 200


# ── ONNX loader ───────────────────────────────────────────────────────────────

def _load_onnx():
    global _session
    if _session is not None:
        return True
    if not _MODEL_PATH.exists():
        return False
    try:
        import onnxruntime as ort
        _session = ort.InferenceSession(str(_MODEL_PATH))
        log.info("VAE ONNX model loaded from %s", _MODEL_PATH)
        return True
    except Exception as e:
        log.warning("Could not load ONNX model: %s", e)
        return False


# ── PCA fallback ──────────────────────────────────────────────────────────────

def _load_pca():
    """Build a simple PCA model from coords.npy as a VAE surrogate."""
    global _pca_model
    if _pca_model is not None:
        return True
    if not _COORDS_PATH.exists():
        return False
    try:
        coords = np.load(_COORDS_PATH).astype(np.float32)  # (N, 400)
        # Normalise
        mean = coords.mean(axis=0)
        X    = coords - mean
        # Thin SVD — keep LATENT_DIM components
        U, S, Vt = np.linalg.svd(X, full_matrices=False)
        components = Vt[:LATENT_DIM]          # (16, 400)
        # Project each sample to latent space to get range stats
        Z = U[:, :LATENT_DIM] * S[:LATENT_DIM]
        z_mean = Z.mean(axis=0)
        z_std  = Z.std(axis=0).clip(0.1)
        _pca_model = {
            "mean":       mean,
            "components": components,
            "z_mean":     z_mean,
            "z_std":      z_std,
        }
        log.info("PCA VAE surrogate built from %d airfoils", len(coords))
        return True
    except Exception as e:
        log.warning("PCA fallback failed: %s", e)
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def vae_available() -> bool:
    return _MODEL_PATH.exists() or _COORDS_PATH.exists()


def get_latent_stats() -> dict:
    """Return per-dimension mean/std so the UI can scale sliders sensibly."""
    if _STATS_PATH.exists():
        return json.loads(_STATS_PATH.read_text())
    if _load_pca() and _pca_model:
        return {
            "mean": _pca_model["z_mean"].tolist(),
            "std":  _pca_model["z_std"].tolist(),
        }
    return {"mean": [0.0] * LATENT_DIM, "std": [1.0] * LATENT_DIM}


def decode_latent(latent: list[float]) -> dict | None:
    z = np.array(latent, dtype=np.float32).reshape(1, LATENT_DIM)

    # ── Try real ONNX decoder first ───────────────────────────────────────────
    if _load_onnx() and _session is not None:
        try:
            input_name = _session.get_inputs()[0].name
            out = _session.run(None, {input_name: z})[0]   # (1, 400)
            coords = out[0]
        except Exception as e:
            log.warning("ONNX decode failed: %s — falling back to PCA", e)
            return _pca_decode(z)
    else:
        return _pca_decode(z)

    return _coords_to_response(coords, source="vae")


def _pca_decode(z: np.ndarray) -> dict | None:
    if not _load_pca() or _pca_model is None:
        return None
    m    = _pca_model
    # Un-standardise
    z_unscaled = z[0] * m["z_std"] + m["z_mean"]
    coords = m["mean"] + (z_unscaled @ m["components"])
    return _coords_to_response(coords, source="pca")


def _coords_to_response(coords: np.ndarray, source: str) -> dict:
    coords = np.clip(coords, -1.0, 1.0)
    x = coords[0::2].tolist()
    y = coords[1::2].tolist()

    # Geometric features
    x_arr = np.array(x)
    y_arr = np.array(y)
    le = int(np.argmin(x_arr))
    x_upper = x_arr[:le + 1][::-1]
    y_upper = y_arr[:le + 1][::-1]
    x_lower = x_arr[le:]
    y_lower = y_arr[le:]
    xg = np.linspace(0.01, 0.99, 100)
    try:
        yu = np.interp(xg, x_upper, y_upper)
        yl = np.interp(xg, x_lower, y_lower)
        max_thickness = float(np.max(yu - yl))
        camber_line   = 0.5 * (yu + yl)
        max_camber    = float(np.max(np.abs(camber_line)))
        idx_t         = int(np.argmax(yu - yl))
        idx_c         = int(np.argmax(np.abs(camber_line)))
        max_thickness_x = float(xg[idx_t])
        max_camber_x    = float(xg[idx_c])
    except Exception:
        max_thickness = 0.12; max_camber = 0.02
        max_thickness_x = 0.30; max_camber_x = 0.40

    return {
        "name": f"VAE-Generated ({source})",
        "x": x,
        "y": y,
        "source": source,
        "features": {
            "max_thickness":   round(max_thickness, 4),
            "max_thickness_x": round(max_thickness_x, 4),
            "max_camber":      round(max_camber, 4),
            "max_camber_x":    round(max_camber_x, 4),
            "is_symmetric":    max_camber < 0.005,
        },
    }
