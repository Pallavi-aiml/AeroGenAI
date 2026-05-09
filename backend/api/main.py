
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="AeroGenAI API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ───────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    mode: str = "naca4"
    max_camber:    float = Field(0.02, ge=0.0,  le=0.10)
    camber_pos:    float = Field(0.40, ge=0.1,  le=0.9)
    max_thickness: float = Field(0.12, ge=0.06, le=0.20)

class SimulateRequest(BaseModel):
    x: list[float]
    y: list[float]
    reynolds:    float = Field(500_000, ge=50_000, le=5_000_000)
    alpha_start: float = Field(-5.0)
    alpha_end:   float = Field(15.0)
    alpha_step:  float = Field(1.0)

class CompareRequest(BaseModel):
    """P4: side-by-side comparison of two airfoils"""
    airfoil_a: dict  # {x, y, name}
    airfoil_b: dict  # {x, y, name}
    reynolds:  float = Field(500_000, ge=50_000, le=5_000_000)

class LatentRequest(BaseModel):
    """P5: decode latent vector → airfoil coordinates"""
    latent: list[float]  # 16-dim

class OptimizeRequest(BaseModel):
    """P5: generate → simulate → keep best L/D loop"""
    n_candidates: int  = Field(20, ge=5,  le=100)
    target:       str  = "best_ld"          # best_ld | max_cl | min_cd
    reynolds:     float = Field(500_000)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    from services.vae import vae_available
    from services.simulation import xfoil_available
    return {
        "status":  "ok",
        "version": "3.0.0",
        "xfoil":   xfoil_available(),
        "vae":     vae_available(),
    }


# ── Phase 2: Generate & Simulate ─────────────────────────────────────────────

@app.post("/api/generate")
def generate(req: GenerateRequest):
    from services.generator import generate_airfoil
    result = generate_airfoil(req.model_dump())
    if result is None:
        raise HTTPException(400, "Failed to generate airfoil")
    return result


@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    from services.simulation import run_xfoil
    result = run_xfoil(
        x=req.x, y=req.y,
        reynolds=req.reynolds,
        alpha_start=req.alpha_start,
        alpha_end=req.alpha_end,
        alpha_step=req.alpha_step,
    )
    if result is None:
        raise HTTPException(422, "Simulation failed — try different parameters")
    return result


# ── Phase 2: Database ─────────────────────────────────────────────────────────

@app.get("/api/database")
def database_search(
    thickness_min: float = 0.06,
    thickness_max: float = 0.20,
    camber_min:    float = 0.0,
    camber_max:    float = 0.10,
    limit:         int   = 12,
):
    from services.generator import search_database
    results = search_database(thickness_min, thickness_max, camber_min, camber_max, limit)
    return {"results": results, "count": len(results)}


@app.get("/api/database/{index}")
def get_airfoil_by_index(index: int):
    from services.generator import get_airfoil_coords
    result = get_airfoil_coords(index)
    if result is None:
        raise HTTPException(404, f"Airfoil index {index} not found")
    return result


# ── Phase 4: Compare two airfoils ────────────────────────────────────────────

@app.post("/api/compare")
def compare(req: CompareRequest):
    from services.simulation import run_xfoil
    from services.evaluator  import evaluate_polar

    def sim(af):
        return run_xfoil(
            x=af["x"], y=af["y"],
            reynolds=req.reynolds,
            alpha_start=-5.0, alpha_end=15.0, alpha_step=1.0,
        )

    polar_a = sim(req.airfoil_a)
    polar_b = sim(req.airfoil_b)

    if polar_a is None or polar_b is None:
        raise HTTPException(422, "One or both simulations failed")

    return {
        "a": {"name": req.airfoil_a.get("name", "Airfoil A"), "polar": polar_a,
              "metrics": evaluate_polar(polar_a)},
        "b": {"name": req.airfoil_b.get("name", "Airfoil B"), "polar": polar_b,
              "metrics": evaluate_polar(polar_b)},
    }


# ── Phase 5: β-VAE latent decode ─────────────────────────────────────────────

@app.post("/api/vae/decode")
def vae_decode(req: LatentRequest):
    from services.vae import decode_latent
    if len(req.latent) != 16:
        raise HTTPException(400, "Latent vector must be 16-dimensional")
    result = decode_latent(req.latent)
    if result is None:
        raise HTTPException(503, "VAE model not loaded — run ml/train_vae.py first")
    return result


@app.get("/api/vae/status")
def vae_status():
    from services.vae import vae_available, get_latent_stats
    return {"available": vae_available(), "stats": get_latent_stats()}


# ── Phase 5: Optimization loop ────────────────────────────────────────────────

@app.post("/api/optimize")
def optimize(req: OptimizeRequest):
    from services.optimizer import run_optimization
    results = run_optimization(
        n_candidates=req.n_candidates,
        target=req.target,
        reynolds=req.reynolds,
    )
    return {"candidates": results, "count": len(results)}
