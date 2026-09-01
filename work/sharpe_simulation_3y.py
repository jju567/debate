"""Priority #3: Täydellinen Sharpe-laskenta ja simulaatio 3v 5min Binance-datalla (HAR-RV Mean-Reversion + Maker-Fee)."""
from pathlib import Path
import numpy as np
import polars as pl

BINANCE_DIR = Path("data/binance_5min")
OUT_DIR = Path("work")

print("=== SHARPE-SIMULAATIO (3v 5min BTCUSDT, HAR-RV Mean-Reversion) ===", flush=True)

# 1. Luetaan data
lf = pl.scan_parquet(BINANCE_DIR / "*.parquet")
df = lf.select(["timestamp", "open", "high", "low", "close", "volume"]).collect().sort("timestamp")
print(f"Kynttiloita ladattu: {df.height:,} kpl", flush=True)

# 2. Log-returns ja liukuvat volatiliteetit (1h, 1pv, 1vko, 1kk)
df = df.with_columns(
    (pl.col("close") / pl.col("close").shift(1)).log().fill_null(0.0).alias("log_ret")
)

df = df.with_columns([
    pl.col("log_ret").pow(2).rolling_sum(window_size=12).sqrt().alias("rv_1h"),
    pl.col("log_ret").pow(2).rolling_sum(window_size=288).sqrt().alias("rv_1d"),
    pl.col("log_ret").pow(2).rolling_sum(window_size=288 * 7).sqrt().alias("rv_1w"),
    pl.col("log_ret").pow(2).rolling_sum(window_size=288 * 30).sqrt().alias("rv_1m"),
])

# 3. HAR-RV Ennuste (käytetään OLS-parametreja)
alpha = 0.000014
beta_d = 0.9996
beta_w = -0.0002
beta_m = 0.0001

df = df.with_columns(
    (alpha + beta_d * pl.col("rv_1d").shift(1) + beta_w * pl.col("rv_1w").shift(1) + beta_m * pl.col("rv_1m").shift(1)).alias("rv_forecast")
)

# 4. Residuaalit ja residuaalien liukuva hajonta
df = df.with_columns(
    (pl.col("rv_1d") - pl.col("rv_forecast")).alias("residual")
).with_columns(
    pl.col("residual").rolling_std(window_size=288).alias("std_residual")
)

# 5. Signaalit (Mean-Reversion Volatility Crush)
# Osto: RV nousee voimakkaasti yli ennusteen JA edellinen 5m tuotto negatiivinen (myyntipaine loppuu)
# Myynti: RV laskee reilusti alle ennusteen JA edellinen 5m tuotto positiivinen
k = 1.5
df = df.with_columns(
    (pl.col("rv_1d") > pl.col("rv_forecast") + k * pl.col("std_residual")).cast(pl.Int8).alias("vol_spike")
)

df = df.with_columns([
    (pl.col("vol_spike") & (pl.col("log_ret").shift(1) < 0)).cast(pl.Int8).alias("signal_buy"),
    (pl.col("vol_spike") & (pl.col("log_ret").shift(1) > 0)).cast(pl.Int8).alias("signal_sell"),
])

# 6. Position (T+1 toteutus -> shift(1) estää Look-Ahead Biasin)
df = df.with_columns([
    pl.col("signal_buy").shift(1).fill_null(0).alias("pos_long"),
    pl.col("signal_sell").shift(1).fill_null(0).alias("pos_short"),
])

# 7. Tuottojen laskenta
df = df.with_columns([
    (pl.col("pos_long") * pl.col("log_ret")).alias("ret_long"),
    (-pl.col("pos_short") * pl.col("log_ret")).alias("ret_short"),
])

df = df.with_columns(
    (pl.col("ret_long") + pl.col("ret_short")).alias("strat_ret_gross")
)

# 8. Kustannukset (Maker 0.15% vs Taker 0.25%, spread 0.05%)
trades = df["pos_long"].diff().abs().fill_null(0) + df["pos_short"].diff().abs().fill_null(0)

MAKER_FEE = 0.0015
TAKER_FEE = 0.0025
SPREAD_HALF = 0.00025

df = df.with_columns([
    (pl.col("strat_ret_gross") - trades * (MAKER_FEE + SPREAD_HALF)).alias("ret_net_maker"),
    (pl.col("strat_ret_gross") - trades * (TAKER_FEE + SPREAD_HALF)).alias("ret_net_taker"),
])

# 9. Tilastot ja Sharpe
PERIODS_PER_YEAR = 105120  # 365 * 288

gross_mean = df["strat_ret_gross"].mean()
gross_std = df["strat_ret_gross"].std()
gross_sharpe = (gross_mean / gross_std) * np.sqrt(PERIODS_PER_YEAR) if gross_std > 0 else 0

maker_mean = df["ret_net_maker"].mean()
maker_std = df["ret_net_maker"].std()
maker_sharpe = (maker_mean / maker_std) * np.sqrt(PERIODS_PER_YEAR) if maker_std > 0 else 0

taker_mean = df["ret_net_taker"].mean()
taker_std = df["ret_net_taker"].std()
taker_sharpe = (taker_mean / taker_std) * np.sqrt(PERIODS_PER_YEAR) if taker_std > 0 else 0

total_trades = trades.sum()
signal_count = df.filter(pl.col("pos_long") == 1).height + df.filter(pl.col("pos_short") == 1).height

print(f"\n--- TULOKSET (3v 5min data, N={df.height:,}) ---", flush=True)
print(f"Signaalijaksoja (aktiivisia) : {signal_count:,} kpl ({(signal_count/df.height)*100:.2f} %)", flush=True)
print(f"Kauppoja yhteensa            : {total_trades:,} kpl", flush=True)
print(f"Bruttotuotto keskiarvo (5m)  : {gross_mean:.8f}", flush=True)
print(f"Gross Sharpe (Brutto)        : {gross_sharpe:.4f}", flush=True)
print(f"Net Sharpe (Maker 0.15% fee) : {maker_sharpe:.4f}", flush=True)
print(f"Net Sharpe (Taker 0.25% fee) : {taker_sharpe:.4f}", flush=True)

# Tallennetaan raportti
report_path = OUT_DIR / "sharpe_3v_report.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"SHARPE ANALYSIS REPORT (3-YEAR 5MIN BTCUSDT)\n")
    f.write(f"Observations: {df.height:,}\n")
    f.write(f"Active Signals: {signal_count:,} ({(signal_count/df.height)*100:.2f}%)\n")
    f.write(f"Total Trades: {total_trades:,}\n")
    f.write(f"Gross Sharpe: {gross_sharpe:.4f}\n")
    f.write(f"Maker Net Sharpe (0.15%): {maker_sharpe:.4f}\n")
    f.write(f"Taker Net Sharpe (0.25%): {taker_sharpe:.4f}\n")

print(f"\n[VALMIS] Raportti tallennettu: {report_path}", flush=True)
