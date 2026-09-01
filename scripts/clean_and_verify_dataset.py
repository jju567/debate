"""Puhdistaa ja standardoi data/binance_5min Parquet-tiedostonimet ja varmistaa partitionoinnin."""
import os
import re
from pathlib import Path
import polars as pl

DIR = Path("data/binance_5min")
files = list(DIR.glob("*.parquet"))

print(f"Alkuperäisiä tiedostoja: {len(files)}")

# Korjataan tiedostojen nimet jos niissä on python-repr
for f in files:
    name = f.name
    # Etsitään datetime.date(2023, 8, 1) tyyliset
    match = re.search(r"datetime\.date\((\d+),\s*(\d+),\s*(\d+)\)", name)
    if match:
        y, m, d = match.groups()
        new_name = f"btcusdt_5m_{int(y):04d}-{int(m):02d}-{int(d):02d}.parquet"
        target_path = DIR / new_name
        if target_path.exists() and target_path != f:
            # Yhdistetään
            df1 = pl.read_parquet(f)
            df2 = pl.read_parquet(target_path)
            combined = pl.concat([df1, df2]).unique(subset=["timestamp"]).sort("timestamp")
            combined.write_parquet(target_path)
            f.unlink()
        else:
            f.rename(target_path)

cleaned_files = sorted(list(DIR.glob("*.parquet")))
print(f"Standardoidut tiedostot: {len(cleaned_files)}")
if cleaned_files:
    print(f"Esimerkki 1: {cleaned_files[0].name}")
    print(f"Esimerkki N: {cleaned_files[-1].name}")

# Validointi
df = pl.read_parquet("data/binance_5min/*.parquet")
print(f"Rivejä yhteensä: {df.height:,}")
print(f"Duplikaatteja: {df.filter(pl.col('timestamp').is_duplicated()).height}")
print(f"Null-arvoja: {df.null_count().to_dicts()[0]}")
