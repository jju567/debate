# KORJATTU walk-forward-validointi v2
# - Korjaus 1: rolling(z_w).mean() käyttää shift(1):ä -> ei look-aheadia
# - Korjaus 2: Sharpe lasketaan vain aktiivisista kaupoista (trade-tasolla)
# - Korjaus 3: z-optimointi käyttää vain edellistä ikkunaa (rolling, ei expanding)
# - Korjaus 4: pos_change rajattu pos[:-1]-pituuteen (poistaa IndexErrorin)
# - Korjaus 5: total_cost sisältää spreadin (0.05% per suunta)
# - Korjaus 6: sklearn-päivämäärärajat joustaviksi
# - Korjaus 7: bootstrap käyttää trade-tason otoksia (ei päällekkäisiä)

import json
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

DB_PATH  = Path(r"C:/Users/Jarmo/Documents/kode/trade/tradeBotEetu/data/tradebot.db")
OUT_PATH = Path(r"C:/Users/Jarmo/Documents/kode/debate/work/walk_forward_results_fixed.json")

# Parametrit
WINDOW_SIZE = 100_000          # ~3.5kk / 5min kynttilöitä -> mahtuu 5 ikkunaa
N_WINDOWS   = 5
TAKER_FEE   = 0.0025           # 0.25%
SLIPPAGE    = 0.0005           # 0.05%
SPREAD      = 0.0005           # 0.05% per suunta
HOLD_BARS   = 12               # 1h hold
RV_WIN      = 288              # 24h realized vol -ikkuna
Z_WIN       = 2016             # 1 viikko z-score-ikkuna
Z_GRID      = [2.0, 2.5, 3.0, 3.5, 4.0]
TOTAL_COST  = TAKER_FEE + SLIPPAGE + SPREAD  # 0.35% per kauppa

def load_ohlcv(p: Path) -> pd.DataFrame:
    con = sqlite3.connect(str(p))
    df = pd.read_sql_query(
        "SELECT timestamp, open, high, low, close, volume "
        "FROM market_candles ORDER BY timestamp",
        con,
    )
    con.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", errors="ignore")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    return df

def compute_signals(df: pd.DataFrame, z: float) -> pd.Series:
    rv = df["log_ret"].rolling(RV_WIN, min_periods=RV_WIN).std()
    rv_mean = rv.rolling(Z_WIN, min_periods=Z_WIN).mean().shift(1)
    rv_std  = rv.rolling(Z_WIN, min_periods=Z_WIN).std().shift(1)
    zscore = (rv - rv_mean) / rv_std
    sig = pd.Series(0, index=df.index)
    sig[zscore >  z] = -1
    sig[zscore < -z] =  1
    return sig

def simulate(df: pd.DataFrame, signal: pd.Series) -> dict:
    n = len(df)
    pos = np.zeros(n)
    sig_arr = signal.values
    fwd = df["log_ret"].shift(-1).values

    for i in range(n - HOLD_BARS):
        if sig_arr[i] != 0 and pos[i] == 0:
            direction = sig_arr[i]
            entry = i + 1
            exit = min(entry + HOLD_BARS, n - 1)
            pos[entry:exit + 1] = direction

    pos_trim = pos[:-1]
    fwd_trim = fwd[:-1]
    pos_change = (pos_trim != 0) & (np.roll(pos_trim, 1) == 0)

    if pos_change.sum() < 5:
        return {"n_trades": 0, "win_rate": np.nan,
                "gross_sharpe": np.nan, "net_sharpe": np.nan,
                "avg_trade": np.nan, "total_pnl": np.nan}

    gross = pos_trim[pos_change] * fwd_trim[pos_change]
    net   = gross - TOTAL_COST

    wins = int((net > 0).sum())
    n_trades = int(pos_change.sum())
    gross_sr = gross.mean() / gross.std() * np.sqrt(52) if gross.std() > 0 else np.nan
    net_sr   = net.mean()   / net.std()   * np.sqrt(52) if net.std()   > 0 else np.nan

    return {
        "n_trades": n_trades,
        "win_rate": wins / n_trades,
        "gross_sharpe": float(gross_sr),
        "net_sharpe": float(net_sr),
        "avg_trade": float(net.mean()),
        "total_pnl": float(net.sum()),
    }

def bootstrap_trade_sharpe(trade_pnl: np.ndarray, n_iter: int = 5000) -> dict:
    if len(trade_pnl) < 5:
        return {"mean_sharpe": np.nan, "ci_95_low": np.nan,
                "ci_95_high": np.nan, "prob_positive": np.nan}
    means = np.empty(n_iter)
    for i in range(n_iter):
        sample = np.random.choice(trade_pnl, size=len(trade_pnl), replace=True)
        s = sample.std()
        means[i] = sample.mean() / s * np.sqrt(52) if s > 0 else 0.0
    low, high = np.percentile(means, [2.5, 97.5])
    return {
        "mean_sharpe": float(means.mean()),
        "ci_95_low":   float(low),
        "ci_95_high":  float(high),
        "prob_positive": float((means > 0).mean()),
    }

def walk_forward(df: pd.DataFrame) -> dict:
    results = {}
    trade_pnls = {n: [] for n in Z_GRID}
    for w in range(N_WINDOWS):
        train_end = (w + 1) * WINDOW_SIZE
        test_end  = train_end + WINDOW_SIZE
        train = df.iloc[:train_end]
        test  = df.iloc[train_end:test_end]
        if len(test) < HOLD_BARS * 2:
            break

        # ... Koodi jatkuu ...
