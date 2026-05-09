# AeroGenAI — Full 5-Phase Project

AI-driven airfoil design and optimisation platform.

## Project Structure

```
Aerogenai/
├── backend/
│   ├── api/main.py              ← FastAPI app (all endpoints)
│   └── services/
│       ├── generator.py         ← NACA-4 + UIUC database
│       ├── simulation.py        ← XFoil wrapper + physics fallback
│       ├── evaluator.py         ← Polar metrics + explainability
│       ├── vae.py               ← β-VAE / PCA inference
│       └── optimizer.py         ← Generate → Simulate → Rank loop
├── data/
│   ├── pipeline/
│   │   ├── scraper.py           ← Scrape UIUC website
│   │   ├── parser.py            ← Parse .dat files
│   │   ├── normalizer.py        ← Resample to 200 pts
│   │   └── run_pipeline.py      ← One-shot pipeline runner
│   └── uiuc_airfoils/
│       ├── processed/           ← coords.npy + metadata.json (Phase 1 output)
│       └── raw/                 ← .dat files
├── frontend/
│   └── src/
│       ├── App.tsx              ← Main app (4 tabs)
│       ├── components/
│       │   ├── AirfoilCanvas.tsx
│       │   ├── ParameterPanel.tsx   ← P2: NACA-4 sliders
│       │   ├── DatabasePanel.tsx    ← P2: UIUC search
│       │   ├── PolarChart.tsx       ← P4: polar + drag bucket + compare
│       │   ├── MetricsPanel.tsx     ← P4: metrics table
│       │   ├── ComparePanel.tsx     ← P4: side-by-side comparison
│       │   └── VaePanel.tsx         ← P5: latent sliders + optimizer
│       ├── services/api.ts      ← All API calls
│       └── types/airfoil.ts     ← TypeScript interfaces
└── ml/
    ├── train_vae.py             ← P5: β-VAE training script
    └── vae_model.onnx           ← (generated after training)
```

## Quick Start

### Phase 1 — Data Pipeline 
```
pip install requests beautifulsoup4 numpy scipy
python data/pipeline/run_pipeline.py
# Output: data/uiuc_airfoils/processed/coords.npy + metadata.json
```

### Phase 2 — Backend + Frontend

**Backend:**
```bash
pip install fastapi uvicorn pydantic numpy scipy
cd Aerogenai
uvicorn backend.api.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### Phase 3 — XFoil Integration

Install the XFoil binary (backend auto-detects it):

| Platform | Command |
|----------|---------|
| Mac      | `brew install xfoil` |
| Ubuntu   | `sudo apt install xfoil` |
| Windows  | Download `xfoil.exe` → add to PATH |

The backend falls back to thin-airfoil-theory approximation if XFoil is not found.

### Phase 4 — Visualization Upgrade (included ✓)
- Real polar charts: Cl vs α, Cd vs α, L/D vs α
- Drag bucket plot (Cd vs Cl scatter)
- Side-by-side airfoil comparison with overlaid polars
- Results table with winner highlighting

Use the **Compare** tab in the UI.

### Phase 5 — β-VAE Training

```bash
pip install torch onnx onnxruntime
python ml/train_vae.py
# Options:
python ml/train_vae.py --epochs 200 --latent-dim 16 --beta 4
# Output:
#   ml/vae_model.onnx        (for backend inference)
#   ml/vae_full.pt           (full checkpoint)
#   ml/latent_stats.json     (slider scaling)
```

While waiting for training, the **β-VAE** tab uses a PCA surrogate automatically — latent sliders work immediately.

### Optimization Loop

In the **β-VAE** tab → "Auto-Optimization Loop":
1. Choose objective: Best L/D / Max Cl / Min Cd
2. Set number of candidates (5–50)
3. Click "Run Optimization"
4. Top 10 results ranked, click any to load into workspace

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/health`        | Status + XFoil/VAE availability |
| POST | `/api/generate`      | NACA-4 / UIUC lookup |
| POST | `/api/simulate`      | XFoil polar simulation |
| GET  | `/api/database`      | Search UIUC airfoil database |
| GET  | `/api/database/{i}`  | Get airfoil by index |
| POST | `/api/compare`       | Simulate and compare two airfoils |
| POST | `/api/vae/decode`    | Decode 16-dim latent → airfoil |
| GET  | `/api/vae/status`    | VAE model availability |
| POST | `/api/optimize`      | Run optimization loop |
