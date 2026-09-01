import polars as pl
import numpy as np

# Ladataan data
df = pl.read_parquet(r"C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\microstructure\merged_data.parquet")

# Tarkistetaan duplikaattien määrä
duplicates = df.filter(pl.col("timestamp").is_duplicated()).height

# Luodaan dt ja log_ret esikäsittelyssä
df = df.with_columns(
    pl.from_epoch("timestamp", time_unit="s").alias("dt")
).sort("dt")

df = df.with_columns(
    (pl.col("mid_price") / pl.col("mid_price").shift(1)).log().alias("log_ret")
)

# Tarkistetaan NaN/Null-arvot log-returneissa
nan_logret = df.filter(pl.col("log_ret").is_nan() | pl.col("log_ret").is_null()).height

# Tarkistetaan RV-laskennan oikeellisuus
rv_check = df.drop_nulls(subset=["log_ret"]).group_by_dynamic("dt", every="5m").agg(
    pl.col("log_ret").pow(2).sum().sqrt().alias("rv")
)
rv_zero = rv_check.filter(pl.col("rv") == 0).height

# Tarkistetaan strategian tuottojen jakauma
strat_check = df.drop_nulls(subset=["log_ret"]).group_by_dynamic("dt", every="5m").agg(
    pl.col("log_ret").sum().alias("ret_5m")
)
negative_returns = strat_check.filter(pl.col("ret_5m") < 0).height / strat_check.height if strat_check.height > 0 else 0.0

print(f"Duplikaattien määrä: {duplicates}")
print(f"NaN-arvoja log-returneissa: {nan_logret}")
print(f"5-min ikkunoita joissa RV=0: {rv_zero}/{rv_check.height} ({rv_zero/rv_check.height:.2%})")
print(f"Negatiiviset 5-min tuotot: {negative_returns:.2%}")

# Tallennetaan diagnostiikka UTF-8-enkoodauksella
diagnostics = {
    "duplicates": duplicates,
    "nan_logret": nan_logret,
    "rv_zero": rv_zero,
    "total_rv_windows": rv_check.height,
    "negative_returns_pct": negative_returns
}

pl.DataFrame(diagnostics).write_csv("diagnostics.csv")