import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

# --- Asetukset ---
DB_PATH = Path(r"C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\tradebot.db")
OUT_PATH = Path(r"C:\Users\Jarmo\Documents\kode\debate\work\threshold_optimization_extended.json")

Z_LEVELS = [2.0, 2.5, 3.0, 3.5]   # kaikki vertailun vuoksi
RV_WINDOW = 288 # ~24h (5min * 288)
Z_WINDOW = 2016                    # ~7 vrk baseline volatiliteetille
HOLD_BARS = 12 # 1h holding period
TAKER_FEE = 0.0025                 # 0.25 %
MAKER_FEE = 0.0015                 # 0.15 %
SLIPPAGE = 0.0005                  # 0.05 %


def load_ohlcv(db_path: Path) -> pd.DataFrame:
    """Lukee market_candles-taulun SQLite:stä."""
    con = sqlite3.connect(str(db_path))
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
    """Palauttaa signaalisarjan: +1 = osta dipistä, -1 = myy piikistä, 0 = ei mitään."""
    rv = df["log_ret"].rolling(rv_w).std()
    zscore = (rv - rv.rolling(z_w).mean()) / rv.rolling(z_w).std()

    # Mean-reversion: osta kun RV on paljon alle normaalin, myy kun paljon yli
    sig = pd.Series(0, index=df.index)
    sig[zscore > z] = -1     # korkea vol → myy (tai jää markkin)
    sig[zscore < -z] = +1    # matala vol → osta dipistä
    return sig


def simulate(df: pd.DataFrame, signal: pd.Series, hold: int, fee: float, slip: float):
    """Yksinkertainen T+1 -entry, hold -bars -exit, brutto/nettotuotot."""
    n = len(df)
    pos = np.zeros(n)
    sig_arr = signal.values
    fwd = df["log_ret"].shift(-1).fillna(0).values  # entry seuraavaan kynttilään

    for i in range(n - hold):
        if sig_arr[i] != 0 and pos[i] == 0:
            direction = sig_arr[i]
            entry = i + 1
            exit = min(entry + hold, n)
            for j in range(entry, exit):
                pos[j] = direction

    # Brutto: signaalin suunnan mukainen tuotto
    gross = pos * fwd
    # Nettokulut: aina kun positio vaihtuu 0:sta, kulu
    pos_change = (pos != 0) & (np.concatenate(([0], pos[:-1])) == 0)
    cost_per_trade = fee + slip
    net = gross - pos_change.astype(float) * cost_per_trade

    gross_series = pd.Series(gross, index=df.index)
    net_series = pd.Series(net, index=df.index)

    def sharpe(x):
        x = x.dropna()
        if x.std() == 0 or len(x) < 10:
            return float("nan")
        return x.mean() / x.std() * np.sqrt(365 * 24 * 12)  # 5min → vuosi

    n_trades = int(pos_change.sum())
    net_entry_returns = net_series[pos_change].dropna()
    wins = int((net_entry_returns > 0).sum())
    return {
        "n_trades": n_trades,
        "win_rate": wins / n_trades if n_trades > 0 else float("nan"),
        "gross_sharpe": float(sharpe(gross_series)),
        "net_sharpe": float(sharpe(net_series)),
        "avg_trade_return": float(net_entry_returns.mean()) if n_trades else float("nan"),
    }


def main():
    print("Ladataan OHLCV…")
    df = load_ohlcv(DB_PATH)
    print(f"  rivejä: {len(df):,}  alkaa: {df['timestamp'].iloc[0]}  loppuu: {df['timestamp'].iloc[-1]}")

    results = {}
    for z in Z_LEVELS:
        print(f"\n== z = {z} ==")
        sig = compute_signals(df, z, RV_WINDOW, Z_WINDOW)
        taker = simulate(df, sig, HOLD_BARS, TAKER_FEE, SLIPPAGE)
        maker = simulate(df, sig, HOLD_BARS, MAKER_FEE, SLIPPAGE)
        results[f"z_{z}"] = {"taker": taker, "maker": maker}
        print(f"  trades={taker['n_trades']}  win%={taker['win_rate']*100:.1f}  "
              f"GrossSharpe={taker['gross_sharpe']:.3f}  NetSharpe(taker)={taker['net_sharpe']:.3f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[OK] Tallennettu: {OUT_PATH}")


if __name__ == "__main__":
    main()