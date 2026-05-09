"""
XFoil Simulation Service — Windows silent mode (no graphics popup)
"""

import subprocess
import tempfile
import logging
import math
import os
from pathlib import Path

log = logging.getLogger(__name__)

XFOIL_BIN     = "C:\\xfoil\\xfoil.exe"
XFOIL_TIMEOUT = 30


def xfoil_available() -> bool:
    return _xfoil_available()


def _xfoil_available() -> bool:
    try:
        subprocess.run(
            [XFOIL_BIN],
            input="PLOP\nG F\n\nQUIT\n",
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _sanitize_coords(x, y):
    pts = []
    seen = set()
    for xi, yi in zip(x, y):
        xf, yf = float(xi), float(yi)
        key = (round(xf, 5), round(yf, 5))
        if key not in seen:
            seen.add(key)
            pts.append((xf, yf))
    return pts


def _write_dat(x, y, path: Path):
    pts = _sanitize_coords(x, y)
    with open(path, "w") as f:
        f.write("airfoil\n")
        for xf, yf in pts:
            f.write(f"  {xf:.6f}  {yf:.6f}\n")


def _build_commands(dat_path, polar_path, reynolds, alpha_start, alpha_end, alpha_step):
    dat_str   = str(dat_path).replace("\\", "/")
    polar_str = str(polar_path).replace("\\", "/")
    lines = [
        # ── Disable ALL graphics before doing anything ──
        "PLOP",
        "G F",
        "",
        # ── Load airfoil ──
        f"LOAD {dat_str}",
        "PANE",
        "OPER",
        f"VISC {int(reynolds)}",
        "ITER 100",
        "PACC",
        polar_str,
        "",
        f"ASEQ {alpha_start} {alpha_end} {alpha_step}",
        "",
        "PACC",
        "",
        "QUIT",
    ]
    return "\n".join(lines) + "\n"


def _parse_polar(polar_path: Path, alpha_start=-5.0, alpha_end=15.0) -> dict | None:
    if not polar_path.exists():
        return None

    alpha_list, cl_list, cd_list, ld_list = [], [], [], []
    header_passed = False

    with open(polar_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "alpha" in line.lower():
                header_passed = True
                continue
            if not header_passed:
                continue
            cols = line.split()
            if len(cols) < 3:
                continue
            try:
                a  = float(cols[0])
                cl = float(cols[1])
                cd = float(cols[2])
                if cd <= 0 or cd > 1.0:
                    continue
                alpha_list.append(round(a, 2))
                cl_list.append(round(cl, 5))
                cd_list.append(round(cd, 5))
                ld_list.append(round(cl / cd, 3) if cd > 0 else 0.0)
            except ValueError:
                continue

    if not alpha_list:
        return None

    n_req = round((alpha_end - alpha_start) / 1.0) + 1
    return {
        "alpha":     alpha_list,
        "cl":        cl_list,
        "cd":        cd_list,
        "ld":        ld_list,
        "converged": len(alpha_list) >= int(0.5 * n_req),
        "source":    "xfoil",
    }


def _physics_approximation(x, y, reynolds, alpha_start, alpha_end, alpha_step) -> dict:
    import numpy as np
    x_arr = np.array([float(v) for v in x])
    y_arr = np.array([float(v) for v in y])
    le_idx = int(np.argmin(x_arr))
    x_upper = x_arr[:le_idx + 1][::-1]
    y_upper = y_arr[:le_idx + 1][::-1]
    x_lower = x_arr[le_idx:]
    y_lower = y_arr[le_idx:]
    xg = np.linspace(0.01, 0.99, 100)
    try:
        yu = np.interp(xg, x_upper, y_upper)
        yl = np.interp(xg, x_lower, y_lower)
        thickness = float(np.max(yu - yl))
        camber    = float(np.mean(0.5 * (yu + yl)))
    except Exception:
        thickness, camber = 0.12, 0.02
    cd0      = 0.006 + 0.002 * thickness / 0.12
    k        = 0.008
    cl_alpha = 2 * math.pi
    alphas = []
    a = alpha_start
    while a <= alpha_end + 0.001:
        alphas.append(round(a, 1))
        a += alpha_step
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
    return {
        "alpha": alphas, "cl": cl_list, "cd": cd_list, "ld": ld_list,
        "converged": True, "source": "approximation",
    }


def run_xfoil(x, y, reynolds=500_000,
              alpha_start=-5.0, alpha_end=15.0, alpha_step=1.0) -> dict | None:

    if not _xfoil_available():
        log.info("XFoil not found — using physics approximation")
        return _physics_approximation(x, y, reynolds, alpha_start, alpha_end, alpha_step)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path   = Path(tmp)
        dat_path   = tmp_path / "airfoil.dat"
        polar_path = tmp_path / "polar.txt"

        _write_dat(x, y, dat_path)
        commands = _build_commands(
            dat_path, polar_path, reynolds, alpha_start, alpha_end, alpha_step
        )

        try:
            subprocess.run(
                [XFOIL_BIN],
                input=commands,
                capture_output=True,
                text=True,
                timeout=XFOIL_TIMEOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            log.warning("XFoil timed out")
            return _physics_approximation(x, y, reynolds, alpha_start, alpha_end, alpha_step)
        except Exception as e:
            log.error("XFoil error: %s", e)
            return _physics_approximation(x, y, reynolds, alpha_start, alpha_end, alpha_step)

        result = _parse_polar(polar_path, alpha_start, alpha_end)
        if result is None:
            return _physics_approximation(x, y, reynolds, alpha_start, alpha_end, alpha_step)

        log.info("XFoil success: %d alpha points", len(result["alpha"]))
        return result
