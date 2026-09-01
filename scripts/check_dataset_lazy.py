"""Yksinkertainen ja nopea datasetin validointi ja tilastojen tulostus."""
from pathlib import Path
import polars as pl

DIR = Path("data/binance_5min")
files = sorted(list(DIR.glob("*.parquet")))

print(f"Paivittaisia tiedostoja kansiossa: {len(files)}")
if files:
    print(f"Ensimmainen: {files[0].name}")
    print(f"Viimeisin:   {files[-1].name}")

lf = pl.scan_parquet(DIR / "*.parquet")
total_rows = lf.select(pl.len()).collect().item()
print(f"Kynttiloita yhteensa: {total_rows:,}")

unique_count = lf.select(pl.col("timestamp").n_unique()).collect().item()
print(f"Uniikkeja kynttiloita: {unique_count:,}")

min_ts = lf.select(pl.col("timestamp").min()).collect().item()
max_ts = lf.select(pl.col("timestamp").max()).collect().item()
min_dt = pl.from_epoch(pl.Series([min_ts]), time_unit="ms")[0]
max_dt = pl.from_epoch(pl.Series([max_ts]), time_unit="ms")[0]
print(f"Aikavali: {min_dt} -> {max_dt}")

nulls = lf.null_count().collect().to_dicts()[0]
print(f"Null-arvot: {nulls}")
print("\n[OK] Datasetin QA suoritettu onnistuneesti!")
