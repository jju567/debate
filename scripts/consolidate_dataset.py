"""Siivoaa tyhjät tiedostot, yhdistää datan ja luo puhtaat päivittäiset Parquetit."""
from pathlib import Path
import polars as pl

DIR = Path("data/binance_5min")
all_files = list(DIR.glob("*.parquet"))

# Poistetaan 0-kokoiset tai korruptoituneet tiedostot
valid_files = []
for f in all_files:
    if f.stat().st_size < 100:
        f.unlink()
    else:
        valid_files.append(f)

print(f"Validit tiedostot: {len(valid_files)} kpl")

# Luetaan jokainen validi tiedosto yksitellen ja kootaan lista
dfs = []
for f in valid_files:
    try:
        sub_df = pl.read_parquet(f)
        if sub_df.height > 0:
            dfs.append(sub_df)
    except Exception as e:
        print(f"Ohitetaan virheellinen tiedosto {f.name}: {e}")
        f.unlink()

print(f"Onnistuneesti luetut erät: {len(dfs)}")
full_df = pl.concat(dfs).unique(subset=["timestamp"]).sort("timestamp")
print(f"Koko datasetin kynttilät (uniikit): {full_df.height:,}")

# Lisätään date-sarake
full_df = full_df.with_columns(
    pl.from_epoch(pl.col("timestamp"), time_unit="ms").dt.date().alias("date")
)

# Poistetaan kaikki olemassa olevat tiedostot ja kirjoitetaan standardoidut
for f in DIR.glob("*.parquet"):
    f.unlink()

print("Kirjoitetaan puhtaat päiväkohtaiset tiedostot...")
for (date_val,), group_df in full_df.group_by("date"):
    date_str = str(date_val)
    file_path = DIR / f"btcusdt_5m_{date_str}.parquet"
    group_df.drop("date").write_parquet(file_path)

final_files = sorted(list(DIR.glob("*.parquet")))
print(f"\n[VALMIS] Luotu {len(final_files)} kpl puhtaita päiväkohtaisia tiedostoja.")
print(f"Ensimmäinen: {final_files[0].name}")
print(f"Viimeisin:   {final_files[-1].name}")

# Validoidaan lopputulos
check_df = pl.read_parquet(DIR / "*.parquet")
print(f"Kokonaisrivimäärä: {check_df.height:,}")
print(f"Duplikaatit: {check_df.filter(pl.col('timestamp').is_duplicated()).height}")
print(f"Null-arvot: {check_df.null_count().to_dicts()[0]}")
