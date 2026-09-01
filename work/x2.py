import json, sqlite3, numpy as np, pandas as pd
from pathlib import Path
from tqdm import tqdm   # tarvitsee tqdm‑kirjaston

DB_PATH   = Path(r"C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\tradebot.db")
OUT_PATH  = Path(r"C:\Users\Jarmo\Documents\kode\debate\work\walk_forward_results.json")

# 5‑min OHLCV → 288 riviä per vuosi, 3 vuotta ≈ 1 051 200 riviä
# Jaetaan 6 tasapainoiseen windowiin (noin 175 200 riviä / window)
WINDOW_SIZE = 175_200
N_WINDOWS   = 6

def load_ohlcv(p: Path) -> pd.DataFrame:
    con = sqlite3.connect(str(p))
    df = pd.read_sql_query(
        "SELECT timestamp, open, high, low, close, volume FROM market_candles ORDER BY timestamp",
        con,
    )
    con.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", errors="ignore")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    return df

def compute_signals(df: pd.DataFrame, z: float, rv_w: int, z_w: int) -> pd.Series:
    rv = df["log_ret"].rolling(rv_w).std()
    zscore = (rv - rv.rolling(z_w).mean()) / rv.rolling(z_w).std()
    sig = pd.Series(0, index=df.index)
    sig[zscore > z] = -1
    sig[zscore < -z] = 1
    return sig

def simulate(df: pd.DataFrame, signal: pd.Series, hold: int, fee: float, slip: float):
    n = len(df)
    pos = np.zeros(n)
    sig_arr = signal.values
    fwd = df["log_ret"].shift(-1).fillna(0).values

    for i in range(n - hold):
        if sig_arr[i] != 0 and pos[i] == 0:
            direction = sig_arr[i]
            entry = i + 1
            exit = min(entry + hold, n)
            pos[entry:exit] = direction

    gross = pos * fwd
    pos_change = (pos != 0) & (np.concatenate(([0], pos[:-1])) == 0)
    cost = fee + slip
    net = gross - pos_change.astype(float) * cost

    gross_series = pd.Series(gross, index=df.index)
    net_series = pd.Series(net, index=df.index)

    def sharpe(x):
        x = x.dropna()
        if x.std() == 0 or len(x) < 10:
            return np.nan
        return x.mean() / x.std() * np.sqrt(365 * 24 * 12)

    n_trades = int(pos_change.sum())
    net_entry_returns = net_series[pos_change].dropna()
    wins = int((net_entry_returns > 0).sum())
    return {
        "n_trades": n_trades,
        "win_rate": wins / n_trades if n_trades else np.nan,
        "gross_sharpe": float(sharpe(gross_series)),
        "net_sharpe": float(sharpe(net_series)),
        "avg_trade_return": float(net_entry_returns.mean()) if n_trades else np.nan,
    }

def walk_forward(df: pd.DataFrame):
    results = {}
    for w in range(N_WINDOWS):
        train_end = (w + 1) * WINDOW_SIZE
        train = df.iloc[:train_end]
        test  = df.iloc[train_end:train_end + WINDOW_SIZE]

        # optimoi z‑tason window‑trainilla (kokeilla 2.0, 2.5, 3.0, 3.5)
        best_z = None
        best_metrics = {}
        for z in [2.0, 2.5, 3.0, 3.5]:
            sig = compute_signals(train, z, rv_w=288, z_w=2016)
            metrics = simulate(train, sig, hold=12, fee=0.0025, slip=0.0005)
            metrics["z"] = z
            best_metrics[z] = metrics
            if best_z is None or metrics["net_sharpe"] > best_metrics[best_z]["net_sharpe"]:
                best_z = z

        # testataan valitulla z‑kynnyksellä
        sig_test = compute_signals(test, best_z, rv_w=288, z_w=2016)
        test_metrics = simulate(test, sig_test, hold=12, fee=0.0025, slip=0.0005)
        results[f"window_{w+1}"] = test_metrics

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[OK] Walk-forward-tulokset tallennettu: {OUT_PATH}")

if __name__ == "__main__":
    df = load_ohlcv(DB_PATH)
    print(f"Data: {len(df):,} riviä, alkaen {df['timestamp'].iloc[0]}, loppuu {df['timestamp'].iloc[-1]}")
    walk_forward(df)