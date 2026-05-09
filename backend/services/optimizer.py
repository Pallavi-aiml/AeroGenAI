"""
Optimization Service (Phase 5)
Uses physics approximation for candidate ranking .
XFoil is only used for the final top-3 verification.
"""
from __future__ import annotations
import logging
import random
import math
import numpy as np

log = logging.getLogger(__name__)

LATENT_DIM = 16


def _fast_evaluate(x, y, reynolds=500_000) -> dict | None:
    """
    Fast physics-based evaluator for ranking candidates.
    No XFoil subprocess — no popup windows.
    """
    try:
        x_arr = np.array([float(v) for v in x])
        y_arr = np.array([float(v) for v in y])

        if len(x_arr) < 10:
            return None

        le_idx = int(np.argmin(x_arr))
        x_upper = x_arr[:le_idx + 1][::-1]
        y_upper = y_arr[:le_idx + 1][::-1]
        x_lower = x_arr[le_idx:]
        y_lower = y_arr[le_idx:]

        xg = np.linspace(0.01, 0.99, 100)
        yu = np.interp(xg, x_upper, y_upper)
        yl = np.interp(xg, x_lower, y_lower)

        thickness = float(np.max(yu - yl))
        camber    = float(np.mean(0.5 * (yu + yl)))

        if thickness < 0.01 or thickness > 0.35:
            return None

        cd0      = 0.006 + 0.002 * thickness / 0.12
        k        = 0.008
        cl_alpha = 2 * math.pi

        alphas = [round(a, 1) for a in np.arange(-5, 15.1, 1.0)]
        cl_list, cd_list, ld_list = [], [], []

        for a_deg in alphas:
            a_rad = math.radians(a_deg)
            cl = cl_alpha * (a_rad + 2 * camber)
            cl = max(-1.8, min(1.8, cl))
            if abs(a_deg) > 12:
                cl *= max(0.3, 1 - 0.08 * (abs(a_deg) - 12))
            cd = max(0.005, cd0 + k * cl ** 2)
            cl_list.append(round(cl, 4))
            cd_list.append(round(cd, 5))
            ld_list.append(round(cl / cd, 2))

        polar = {
            "alpha": alphas, "cl": cl_list, "cd": cd_list, "ld": ld_list,
            "converged": True, "source": "approximation",
        }

        best_ld_idx = ld_list.index(max(ld_list))
        idx5 = min(range(len(alphas)), key=lambda i: abs(alphas[i] - 5.0))

        metrics = {
            "best_ld":       round(max(ld_list), 1),
            "best_ld_alpha": alphas[best_ld_idx],
            "max_cl":        round(max(cl_list), 3),
            "stall_alpha":   alphas[cl_list.index(max(cl_list))],
            "cl_at_target":  round(cl_list[idx5], 4),
            "cd_at_target":  round(cd_list[idx5], 5),
            "ld_at_target":  round(ld_list[idx5], 1),
        }
        return {"polar": polar, "metrics": metrics}
    except Exception as e:
        log.warning("Fast evaluate failed: %s", e)
        return None


def run_optimization(
    n_candidates: int = 20,
    target: str = "best_ld",
    reynolds: float = 500_000,
) -> list[dict]:

    from services.vae      import vae_available, decode_latent, get_latent_stats
    from services.generator import generate_airfoil

    candidates = []

    if vae_available():
        stats  = get_latent_stats()
        z_mean = np.array(stats.get("mean", [0.0] * LATENT_DIM))
        z_std  = np.array(stats.get("std",  [1.0] * LATENT_DIM))
        for _ in range(n_candidates):
            z = (z_mean + z_std * np.random.randn(LATENT_DIM)).tolist()
            airfoil = decode_latent(z)
            if airfoil:
                candidates.append({"airfoil": airfoil, "latent": z})
    else:
        for _ in range(n_candidates):
            m = round(random.uniform(0.0, 0.09), 3)
            p = round(random.uniform(0.2, 0.8),  2)
            t = round(random.uniform(0.06, 0.20), 3)
            airfoil = generate_airfoil(
                {"mode": "naca4", "max_camber": m, "camber_pos": p, "max_thickness": t}
            )
            if airfoil:
                candidates.append({"airfoil": airfoil, "latent": None})

    results = []
    for c in candidates:
        af  = c["airfoil"]
        out = _fast_evaluate(af["x"], af["y"], reynolds)
        if out is None:
            continue
        results.append({
            "name":     af["name"],
            "x":        af["x"],
            "y":        af["y"],
            "features": af.get("features", {}),
            "polar":    out["polar"],
            "metrics":  out["metrics"],
            "latent":   c["latent"],
        })

    key_map = {
        "best_ld": lambda r: r["metrics"].get("best_ld", 0),
        "max_cl":  lambda r: r["metrics"].get("max_cl", 0),
        "min_cd":  lambda r: -r["metrics"].get("cd_at_target", 9999),
    }
    key_fn = key_map.get(target, key_map["best_ld"])
    results.sort(key=key_fn, reverse=True)

    log.info("Optimization complete: %d valid candidates, returning top %d",
             len(results), min(10, len(results)))
    return results[:10]
