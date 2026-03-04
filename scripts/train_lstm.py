"""
Nivo FX — LSTM Training Script
================================
Trains the CPUOptimizedLSTM from nivo_cortex.py on downloaded OANDA data.
Saves trained model weights as .pth files per pair.

Prerequisites:
    python3 scripts/download_oanda_data.py  (run first!)

Usage (run from project root on Linux server):
    cd /home/diego/nivo_fx
    source .venv/bin/activate
    python3 scripts/train_lstm.py

Output:
    scripts/data/lstm_EUR_USD.pth
    scripts/data/lstm_GBP_USD.pth
    scripts/data/lstm_USD_JPY.pth
    scripts/data/lstm_AUD_USD.pth
"""

import os
import sys
import numpy as np
import pandas as pd

# Ensure project root is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
PAIRS      = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]

# ─── Hyperparameters ──────────────────────────────────────────────────────────
SEQ_LEN    = 60    # Use 60 hours of history to predict next direction
HIDDEN     = 64
LAYERS     = 2
EPOCHS     = 30
BATCH      = 32
LR         = 0.001
TRAIN_SPLIT = 0.85


# ─── Reuse model from nivo_cortex.py ────────────────────────────────────────
class CPUOptimizedLSTM(nn.Module):
    """Same architecture as the one in src/nivo_cortex.py."""
    def __init__(self, input_size=5, hidden_size=64, num_layers=2, output_size=1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, output_size)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.sigmoid(self.fc(out[:, -1, :]))


# ─── Data Preparation ────────────────────────────────────────────────────────
def prepare_sequences(df: pd.DataFrame):
    """
    Creates (X, y) sequences for LSTM training.
    X: [open_ret, high_ret, low_ret, close_ret, vol_norm] for SEQ_LEN candles
    y: 1 if next close > current close else 0 (direction classification)
    """
    # Normalize with returns instead of raw prices
    df = df.copy()
    df["open_r"]  = df["Open"].pct_change()
    df["high_r"]  = df["High"].pct_change()
    df["low_r"]   = df["Low"].pct_change()
    df["close_r"] = df["Close"].pct_change()
    df["vol_n"]   = (df["Volume"] - df["Volume"].mean()) / (df["Volume"].std() + 1e-8)
    df = df.dropna()

    features = df[["open_r", "high_r", "low_r", "close_r", "vol_n"]].values.astype(np.float32)
    closes   = df["Close"].values

    X, y = [], []
    for i in range(SEQ_LEN, len(features) - 1):
        X.append(features[i - SEQ_LEN:i])
        y.append(1.0 if closes[i + 1] > closes[i] else 0.0)

    return np.array(X), np.array(y, dtype=np.float32)


# ─── Training Loop ───────────────────────────────────────────────────────────
def train_pair(pair: str):
    csv_path = os.path.join(DATA_DIR, f"{pair}_H1.csv")
    if not os.path.exists(csv_path):
        print(f"  ⚠️  {csv_path} not found. Run download_oanda_data.py first.")
        return

    print(f"\n🧠 Training LSTM for {pair}...")
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    print(f"   Loaded {len(df)} candles")

    X, y = prepare_sequences(df)
    split = int(len(X) * TRAIN_SPLIT)

    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    train_ds = TensorDataset(torch.tensor(X_train), torch.tensor(y_train).unsqueeze(1))
    val_ds   = TensorDataset(torch.tensor(X_val),   torch.tensor(y_val).unsqueeze(1))
    train_dl = DataLoader(train_ds, batch_size=BATCH, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=BATCH)

    model     = CPUOptimizedLSTM(input_size=5, hidden_size=HIDDEN, num_layers=LAYERS)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    best_val_loss = float("inf")
    best_weights  = None

    for epoch in range(1, EPOCHS + 1):
        # Training
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        # Validation
        model.eval()
        val_loss = 0.0
        correct  = 0
        total    = 0
        with torch.no_grad():
            for xb, yb in val_dl:
                pred = model(xb)
                val_loss += criterion(pred, yb).item()
                correct  += ((pred > 0.5) == yb.bool()).sum().item()
                total    += len(yb)

        avg_train = train_loss / len(train_dl)
        avg_val   = val_loss   / len(val_dl)
        acc       = correct / total * 100

        if epoch % 5 == 0 or epoch == EPOCHS:
            print(f"   Epoch {epoch:2d}/{EPOCHS} | Train: {avg_train:.4f} | Val: {avg_val:.4f} | Acc: {acc:.1f}%")

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            best_weights  = {k: v.clone() for k, v in model.state_dict().items()}

    # Save best weights
    out_path = os.path.join(DATA_DIR, f"lstm_{pair}.pth")
    torch.save(best_weights, out_path)
    print(f"   ✅ Saved best weights → {out_path}  (val_loss={best_val_loss:.4f})")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("\n🚀 Nivo FX — LSTM Training Pipeline")
    print(f"   Pairs: {', '.join(PAIRS)}")
    print(f"   Sequence length: {SEQ_LEN}h | Epochs: {EPOCHS} | Hidden: {HIDDEN}\n")

    for pair in PAIRS:
        train_pair(pair)

    print("\n✅ All models trained!")
    print("   Next step: restart the bot so NivoCortex loads the new weights:")
    print("   sudo systemctl restart nivo-sentinel.timer nivo-bot.service")


if __name__ == "__main__":
    main()
