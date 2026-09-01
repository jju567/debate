"""Datan laadun ja eheyden tarkistus Binance 5min Parquet -datasetille."""
import polars as pl
from pathlib import Path

OUT_DIR = Path("data/binance_5min")
files = sorted(list(OUT_DIR.glob("*.parquet")))

print(f"=== BINANCE 5MIN DATASET QA ===")
print(f"Päivittäisiä Parquet-tiedostoja: {len(files)}")
if files:
    print(f"Ensimmäinen tiedosto: {files[0].name}")
    print(f"Viimeisin tiedosto:   {files[-1].name}")

df = pl.read_parquet("data/binance_5min/*.parquet")
print(f"\nKynttilöitä (rivejä) yhteensä: {df.height:,}")
print(f"Sarakkeet ({len(df.columns)}): {df.columns}")

# Aikaleimatarkistukset
min_ts = df["timestamp"].min()
max_ts = df["timestamp"].max()
min_dt = pl.from_epoch(pl.Series([min_ts]), time_unit="ms")[0]
max_dt = pl.from_epoch(pl.Series([max_ts]), time_unit="ms")[0]
print(f"Aikaväli: {min_dt} -> {max_dt}")

# Duplikaatit ja puuttuvat
dups = df.filter(pl.col("timestamp").is_duplicated()).height
nulls = df.null_count().to_dicts()[0]
print(f"Duplikaattiaikaleimoja: {dups}")
print(f"Null-arvot sarakkeittain: {nulls}")

# OHLCV-loogisuus
invalid_ohlc = df.filter(
    (pl.col("high") < pl.col("low")) |
    (pl.col("open") > pl.col("high")) |
    (pl.col("open") < pl.col("low")) |
    (pl.col("close") > pl.col("high")) |
    (pl.col("close") < pl.col("low")) |
    (pl.col("volume") < 0)
).height
print(f"Epäloogisia OHLCV-rivejä: {invalid_ohlc}")

print("\n--- Esimerkkirivit alusta ---")
print(df.head(3))
print("\n--- Esimerkkirivit lopusta ---")
print(df.tail(3))
