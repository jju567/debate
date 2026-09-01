import polars as pl
import numpy as np

# Ladataan data suoraan SQLite-tietokannasta
db_path = "data/tradebot.db"
query = """
SELECT timestamp, close, volume
FROM market_candles
WHERE symbol = 'BTCEUR' AND timestamp >= '2021-11-01'
"""

df = pl.read_database(query, f"sqlite:{db_path}")

# Muunnos ja volatiliteetin laskenta
df = df.with_columns(
    pl.col("timestamp").cast(pl.Datetime),
    pl.col("close").log().diff().alias("log_ret")
).with_columns(
    pl.col("log_ret").pow(2).rolling_sum(window_size=24, min_periods=1).sqrt().alias("rv_1d")
)

# Regime-segmentointi
mean_rv = df["rv_1d"].mean()
std_rv = df["rv_1d"].std()

df = df.with_columns(
    pl.when(pl.col("rv_1d") > mean_rv + 1.5 * std_rv)
      .then("HIGH_VOL")
    .when(pl.col("rv_1d") < mean_rv - 1.5 * std_rv)
      .then("LOW_VOL")
    .otherwise("NORMAL")
    .alias("regime")
)

# Tilastolliset tunnusluvut
regime_stats = df.group_by("regime").agg(
    pl.count().alias("n_obs"),
    pl.col("log_ret").mean().alias("mean_ret"),
    pl.col("log_ret").std().alias("volatility"),
    (pl.col("log_ret") > 0).mean().alias("win_rate")
)

# Tulosten tallennus
df.write_csv("work/regime_data_btceur.csv")
regime_stats.write_csv("work/regime_stats_btceur.csv")
print("Analyysi valmis! Tiedostot tallennettu.")