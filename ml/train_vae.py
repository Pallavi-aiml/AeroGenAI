"""
β-VAE Training Script  (Phase 5)
==================================
Train a β-VAE on the UIUC processed coords.npy (1,606 airfoils × 400 floats).
Exports:
  ml/vae_model.onnx          — decoder for the FastAPI backend
  ml/vae_full.pt             — full checkpoint (encoder + decoder)
  ml/latent_stats.json       — per-dim mean/std for UI slider scaling

Usage:
  pip install torch torchvision onnx onnxruntime
  python ml/train_vae.py
  python ml/train_vae.py --epochs 200 --latent-dim 16 --beta 4

Architecture:
  Input  400  →  Encoder  →  z (16)
  z (16) →  Decoder  →  Output 400
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
COORDS_PATH = ROOT / "data" / "uiuc_airfoils" / "processed" / "coords.npy"
OUT_DIR     = ROOT / "ml"
OUT_DIR.mkdir(exist_ok=True)


# ── Model ─────────────────────────────────────────────────────────────────────

def build_model(input_dim: int, latent_dim: int):
    import torch
    import torch.nn as nn

    class Encoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 256), nn.LayerNorm(256), nn.GELU(),
                nn.Linear(256, 128),       nn.LayerNorm(128), nn.GELU(),
                nn.Linear(128, 64),        nn.GELU(),
            )
            self.mu     = nn.Linear(64, latent_dim)
            self.log_var = nn.Linear(64, latent_dim)

        def forward(self, x):
            h = self.net(x)
            return self.mu(h), self.log_var(h)

    class Decoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(latent_dim, 64),  nn.GELU(),
                nn.Linear(64, 128),         nn.LayerNorm(128), nn.GELU(),
                nn.Linear(128, 256),        nn.LayerNorm(256), nn.GELU(),
                nn.Linear(256, input_dim),  nn.Tanh(),
            )

        def forward(self, z):
            return self.net(z)

    class BetaVAE(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = Encoder()
            self.decoder = Decoder()

        def reparameterise(self, mu, log_var):
            if self.training:
                std = (0.5 * log_var).exp()
                return mu + std * torch.randn_like(std)
            return mu

        def forward(self, x):
            mu, lv = self.encoder(x)
            z      = self.reparameterise(mu, lv)
            recon  = self.decoder(z)
            return recon, mu, lv

    return BetaVAE()


# ── Loss ──────────────────────────────────────────────────────────────────────

def vae_loss(recon, x, mu, log_var, beta: float):
    import torch.nn.functional as F
    recon_loss = F.mse_loss(recon, x, reduction="mean")
    kld = -0.5 * (1 + log_var - mu.pow(2) - log_var.exp()).mean()
    return recon_loss + beta * kld, recon_loss, kld


# ── Training loop ─────────────────────────────────────────────────────────────

def train(args):
    try:
        import torch
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        log.error("PyTorch not installed. Run: pip install torch")
        return

    if not COORDS_PATH.exists():
        log.error("coords.npy not found — run data pipeline first")
        return

    # Load & normalise
    coords = np.load(COORDS_PATH).astype(np.float32)
    log.info("Loaded coords: %s", coords.shape)

    mu_data  = coords.mean(axis=0)
    std_data = coords.std(axis=0).clip(1e-6)
    coords_n = (coords - mu_data) / std_data

    X      = torch.tensor(coords_n)
    loader = DataLoader(TensorDataset(X), batch_size=args.batch_size, shuffle=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info("Device: %s", device)

    model     = build_model(coords.shape[1], args.latent_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)

    best_loss = float("inf")
    for epoch in range(1, args.epochs + 1):
        model.train()
        total = recon_t = kld_t = 0.0
        for (batch,) in loader:
            batch = batch.to(device)
            recon, mu, lv = model(batch)
            loss, rl, kl  = vae_loss(recon, batch, mu, lv, args.beta)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += loss.item()
            recon_t += rl.item()
            kld_t   += kl.item()
        scheduler.step()

        n = len(loader)
        if epoch % 10 == 0 or epoch == 1:
            log.info("Epoch %3d/%d  loss=%.5f  recon=%.5f  kld=%.5f",
                     epoch, args.epochs, total/n, recon_t/n, kld_t/n)

        if total < best_loss:
            best_loss = total
            torch.save({"model": model.state_dict(),
                        "mu_data": mu_data, "std_data": std_data,
                        "latent_dim": args.latent_dim,
                        "input_dim": coords.shape[1]},
                       OUT_DIR / "vae_full.pt")

    log.info("Training complete. Best loss: %.5f", best_loss)

    # ── Collect latent stats ──────────────────────────────────────────────────
    model.eval()
    import torch
    with torch.no_grad():
        X_dev = X.to(device)
        mu_z, _ = model.encoder(X_dev)
        mu_z    = mu_z.cpu().numpy()

    stats = {
        "mean": mu_z.mean(axis=0).tolist(),
        "std":  mu_z.std(axis=0).clip(0.1).tolist(),
    }
    (OUT_DIR / "latent_stats.json").write_text(json.dumps(stats, indent=2))
    log.info("Saved latent_stats.json")

    # ── Export decoder to ONNX ───────────────────────────────────────────────
    try:
        import torch.onnx
        decoder = model.decoder.eval().to("cpu")
        dummy   = torch.zeros(1, args.latent_dim)
        torch.onnx.export(
            decoder, dummy,
            str(OUT_DIR / "vae_model.onnx"),
            input_names=["latent"],
            output_names=["coords"],
            dynamic_axes={"latent": {0: "batch"}, "coords": {0: "batch"}},
            opset_version=17,
        )
        log.info("Exported vae_model.onnx")
    except Exception as e:
        log.warning("ONNX export failed: %s", e)

    log.info("All done! Files in %s/", OUT_DIR)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",     type=int,   default=100)
    parser.add_argument("--latent-dim", type=int,   default=16)
    parser.add_argument("--beta",       type=float, default=4.0)
    parser.add_argument("--batch-size", type=int,   default=64)
    parser.add_argument("--lr",         type=float, default=1e-3)
    args = parser.parse_args()
    train(args)
