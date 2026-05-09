"""
Polar Evaluator & Explainability Layer
Two responsibilities:

  1. evaluate_polar()
     Takes raw XFoil polar data and computes summary metrics:
       - best L/D and the alpha at which it occurs
       - Cl and Cd at a target alpha
       - stall angle (where Cl starts dropping)
       - drag bucket width

  2. explain()
     Takes geometric features + polar metrics and returns
     a list of plain-English insight strings.
     Rule-based — no ML needed. Impressive to demonstrate.
"""

import logging

log = logging.getLogger(__name__)


# ── Polar evaluation ──────────────────────────────────────────────────────────

def evaluate_polar(polar: dict, target_alpha: float = 5.0) -> dict:
    """
    Compute summary metrics from a XFoil polar dict.

    Args:
        polar        : {"alpha":[], "cl":[], "cd":[], "ld":[]}
        target_alpha : angle of attack to report Cl/Cd/LD at

    Returns:
        dict with summary statistics
    """
    if not polar or not polar.get("alpha"):
        return {}

    alphas = polar["alpha"]
    cls    = polar["cl"]
    cds    = polar["cd"]
    lds    = polar["ld"]

    # Best L/D
    best_ld_idx   = max(range(len(lds)), key=lambda i: lds[i])
    best_ld       = lds[best_ld_idx]
    best_ld_alpha = alphas[best_ld_idx]

    # Max Cl (useful for stall estimation)
    max_cl_idx    = max(range(len(cls)), key=lambda i: cls[i])
    max_cl        = cls[max_cl_idx]
    stall_alpha   = alphas[max_cl_idx]

    # Metrics at target alpha (nearest available)
    def nearest(target, values):
        return min(range(len(values)), key=lambda i: abs(values[i] - target))

    idx_at_target = nearest(target_alpha, alphas)
    cl_at_target  = cls[idx_at_target]
    cd_at_target  = cds[idx_at_target]
    ld_at_target  = lds[idx_at_target]

    # Drag bucket width — range of alpha where Cd < 1.5 × min(Cd)
    min_cd = min(cds)
    bucket = [alphas[i] for i, cd in enumerate(cds) if cd < 1.5 * min_cd]
    drag_bucket_width = (max(bucket) - min(bucket)) if len(bucket) >= 2 else 0.0

    return {
        "best_ld":          round(best_ld, 2),
        "best_ld_alpha":    round(best_ld_alpha, 2),
        "max_cl":           round(max_cl, 4),
        "stall_alpha":      round(stall_alpha, 2),
        "cl_at_target":     round(cl_at_target, 4),
        "cd_at_target":     round(cd_at_target, 5),
        "ld_at_target":     round(ld_at_target, 2),
        "drag_bucket_width":round(drag_bucket_width, 2),
        "target_alpha":     target_alpha,
    }


# ── Explainability rules ──────────────────────────────────────────────────────

def explain(features: dict, metrics: dict) -> list[dict]:
    """
    Generate plain-English insights from geometric features + polar metrics.
    Returns list of {"label": str, "insight": str, "type": "positive"|"warning"|"tradeoff"}

    These are rule-based — simple threshold comparisons.
    Honest, accurate, and impressive in a demo.
    """
    insights = []

    t  = features.get("max_thickness",   0)
    tx = features.get("max_thickness_x", 0)
    c  = features.get("max_camber",      0)
    cx = features.get("max_camber_x",    0)
    le = features.get("le_radius",       0)
    sym = features.get("is_symmetric",   False)

    best_ld  = metrics.get("best_ld",     0)
    stall_a  = metrics.get("stall_alpha", 0)
    buck_w   = metrics.get("drag_bucket_width", 0)
    cl_t     = metrics.get("cl_at_target", 0)

    # ── Camber insights ───────────────────────────────────────────────────────
    if c < 0.005:
        insights.append({
            "label":   "Symmetric / low camber",
            "insight": "Near-zero camber → symmetric lift curve. Good for aerobatic "
                       "or reversible-flow applications but lower cruise Cl.",
            "type":    "tradeoff",
        })
    elif c < 0.02:
        insights.append({
            "label":   "Mild camber",
            "insight": f"Camber f/c = {c:.3f} generates moderate lift at low drag. "
                       "Typical for general-aviation cruise airfoils.",
            "type":    "positive",
        })
    elif c < 0.05:
        insights.append({
            "label":   "Moderate camber",
            "insight": f"Camber f/c = {c:.3f} → higher cruise Cl. Pressure recovery "
                       "becomes more demanding — watch trailing-edge separation.",
            "type":    "positive",
        })
    else:
        insights.append({
            "label":   "High camber",
            "insight": f"Camber f/c = {c:.3f} gives high Cl but increases pitching "
                       "moment and may cause early stall. Good for low-speed / high-lift.",
            "type":    "warning",
        })

    # ── Thickness insights ────────────────────────────────────────────────────
    if t < 0.08:
        insights.append({
            "label":   "Very thin airfoil",
            "insight": f"Thickness t/c = {t:.3f} minimizes drag at high speed but "
                       "gives very little room for a wing spar — structural concern.",
            "type":    "warning",
        })
    elif t < 0.12:
        insights.append({
            "label":   "Thin-to-moderate thickness",
            "insight": f"Thickness t/c = {t:.3f} — good balance of drag and structural depth. "
                       "Common in sailplane and drone airfoils.",
            "type":    "positive",
        })
    elif t < 0.16:
        insights.append({
            "label":   "Moderate thickness",
            "insight": f"Thickness t/c = {t:.3f} provides good structural depth for "
                       "a wing spar. Drag penalty is manageable at subsonic speeds.",
            "type":    "positive",
        })
    else:
        insights.append({
            "label":   "Thick airfoil",
            "insight": f"Thickness t/c = {t:.3f} — strong structural section but "
                       "pressure drag rises. Typical of low-Reynolds-number sections.",
            "type":    "tradeoff",
        })

    # ── Thickness position ────────────────────────────────────────────────────
    if tx < 0.25:
        insights.append({
            "label":   "Forward thickness peak",
            "insight": f"Max thickness at x/c = {tx:.2f} — turbulent transition occurs "
                       "early. Higher drag but more docile stall behavior.",
            "type":    "tradeoff",
        })
    elif tx < 0.40:
        insights.append({
            "label":   "Thickness peak at ~30%",
            "insight": f"Max thickness at x/c = {tx:.2f} — typical of laminar-flow "
                       "sections. Laminar boundary layer can extend to 30–40% chord.",
            "type":    "positive",
        })
    else:
        insights.append({
            "label":   "Aft thickness peak",
            "insight": f"Max thickness at x/c = {tx:.2f} — extended laminar run "
                       "possible, but adverse pressure gradient near TE is steep.",
            "type":    "tradeoff",
        })

    # ── L/D insights ──────────────────────────────────────────────────────────
    if best_ld > 80:
        insights.append({
            "label":   "Excellent L/D",
            "insight": f"Peak L/D = {best_ld:.1f} — high-performance sailplane territory. "
                       "Ensure Re is realistic for your application.",
            "type":    "positive",
        })
    elif best_ld > 50:
        insights.append({
            "label":   "Good L/D",
            "insight": f"Peak L/D = {best_ld:.1f} — solid aerodynamic efficiency. "
                       "Typical of well-optimized GA and UAV airfoils.",
            "type":    "positive",
        })
    elif best_ld > 30:
        insights.append({
            "label":   "Moderate L/D",
            "insight": f"Peak L/D = {best_ld:.1f} — acceptable for thick / low-Re sections. "
                       "Consider reducing camber or thickness to improve.",
            "type":    "tradeoff",
        })
    else:
        insights.append({
            "label":   "Low L/D",
            "insight": f"Peak L/D = {best_ld:.1f} — this shape is underperforming. "
                       "Check for geometry issues or try the optimizer.",
            "type":    "warning",
        })

    # ── Stall behavior ────────────────────────────────────────────────────────
    if stall_a > 14:
        insights.append({
            "label":   "High stall angle",
            "insight": f"Stall at α = {stall_a:.1f}° — gentle stall onset. "
                       "Good for aircraft that need high-α capability.",
            "type":    "positive",
        })
    elif stall_a > 10:
        insights.append({
            "label":   "Normal stall angle",
            "insight": f"Stall at α = {stall_a:.1f}° — typical for subsonic airfoils.",
            "type":    "positive",
        })
    else:
        insights.append({
            "label":   "Early stall",
            "insight": f"Stall at α = {stall_a:.1f}° — limited angle-of-attack range. "
                       "May indicate sharp leading edge or too much camber.",
            "type":    "warning",
        })

    # ── Drag bucket ───────────────────────────────────────────────────────────
    if buck_w > 6:
        insights.append({
            "label":   "Wide drag bucket",
            "insight": f"Drag bucket spans ~{buck_w:.1f}° — efficient over a wide "
                       "operating range. Good for cruise applications.",
            "type":    "positive",
        })
    elif buck_w > 3:
        insights.append({
            "label":   "Moderate drag bucket",
            "insight": f"Drag bucket spans ~{buck_w:.1f}° — efficient near design α "
                       "but Cd rises quickly off-design.",
            "type":    "tradeoff",
        })

    return insights
