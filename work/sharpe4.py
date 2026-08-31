import polars as pl
import numpy as np

# Tiedostopolut
input_path = r"C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\microstructure\merged_data.parquet"
output_path = r"C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\microstructure\sharpe_result.txt"

# 1. Luetaan data ja valitaan tarvittavat sarakkeet
df = pl.read_parquet(input_path).select(["timestamp", "mid_price"])

# 2. Muunnetaan timestamp datetime-muotoon ja lajitellaan
df = df.with_columns(
    pl.from_epoch("timestamp", time_unit="s").alias("dt")
).sort("dt")

# 3. Lasketaan logaritmiset tuotot
df = df.with_columns(
    (pl.col("mid_price") / pl.col("mid_price").shift(1)).log().alias("log_ret")
).drop_nulls()

# 4. Lasketaan Realized Volatility (RV) 5 minuutin ikkunoissa
rv_df = df.group_by_dynamic("dt", every="5m").agg([
    (pl.col("log_ret").pow(2).sum().sqrt()).alias("rv")
]).filter(pl.col("rv") > 0)

mu_rv = rv_df["rv"].mean()
std_rv = rv_df["rv"].std()
threshold = mu_rv + 1.5 * std_rv

# 5. Luodaan signaali RV-kynnyksen perusteella
rv_df = rv_df.with_columns(
    (pl.col("rv") > threshold).cast(pl.Int8).alias("signal")
)

# 6. Aggregoidaan 5 minuutin kokonaistuotot
df_5m = df.group_by_dynamic("dt", every="5m").agg([
    pl.col("log_ret").sum().alias("ret_5m")
])

# 7. Yhdistetään ja lasketaan strategian tuotot (signaali viiveellä t-1)
strat_df = rv_df.join(df_5m, on="dt", how="left").with_columns([
    (pl.col("signal").shift(1).fill_null(0) * pl.col("ret_5m")).alias("strat_ret")
])

# 8. Otetaan huomioon kulut kaupankäynnistä
FEE = 0.0025
trades = rv_df["signal"].diff().fill_null(0).abs()
strat_df = strat_df.with_columns([
    (pl.col("strat_ret") - (trades * FEE)).alias("strat_ret_net")
])

# 9. Lasketaan suorituskykymittarit ja annualisoitu Sharpe
mean_ret = strat_df["strat_ret_net"].mean()
std_ret = strat_df["strat_ret_net"].std()
sharpe = (mean_ret / std_ret) * np.sqrt(105120) if std_ret > 0 else 0.0

# 10. Tulostetaan tulokset
print(f"RV keskiarvo: {mu_rv:.6f}")
print(f"RV keskihajonta: {std_rv:.6f}")
print(f"Signaalien osuus: {rv_df['signal'].mean() * 100:.2f}%")
print(f"Keskituotto (5min): {mean_ret:.6f}")
print(f"Tuottojen std: {std_ret:.6f}")
print(f"SHARPE (annualisoitu): {sharpe:.4f}")

# 11. Tallennetaan tulokset tiedostoon
with open(output_path, "w", encoding="utf-8") as f:
    f.write(f"RV mean: {mu_rv:.6e}\n")
    f.write(f"RV std: {std_rv:.6e}\n")
    f.write(f"Signal %: {rv_df['signal'].mean() * 100:.2f}\n")
    f.write(f"Mean ret: {mean_ret:.6e}\n")
    f.write(f"Std ret: {std_ret:.6e}\n")
    f.write(f"Sharpe: {sharpe:.4f}\n")
