import os
import polars as pl
import glob

# Konfiguraatio
DATA_DIR = 'C:/Users/Jarmo/Documents/kode/trade/tradeBotEetu/data/microstructure/'  # Muuta tämä omaksi poluksi
SAVE_PATH = os.path.join(DATA_DIR, 'merged_data.parquet')
files = sorted(glob.glob(os.path.join(DATA_DIR, '*.parquet')))

# 1. Skeemojen tunnistus
skeemat = {}
for f in files:
    try:
        # Lue vain ensimmäiset 10 riviä skeeman tunnistamista varten
        temp = pl.read_parquet(f, n_rows=10)
        sarakkeet = tuple(temp.columns)
        skeemat.setdefault(sarakkeet, []).append(f)
    except Exception as e:
        print(f"Virhe tiedostossa {f}: {str(e)}")

# 2. Käytä vain 17-sarakkeesta skeemaa
valid_files = [f for files in skeemat.values() for f in files if len(pl.read_parquet(f, n_rows=1).columns) == 17]

# 3. Yhdistä pienissä erissä
dfs = []
BATCH_SIZE = 10  # Vältetään muistin ylikuormitusta
for i in range(0, len(valid_files), BATCH_SIZE):
    batch_files = valid_files[i:i+BATCH_SIZE]
    df_batch = pl.concat([pl.read_parquet(f) for f in batch_files])
    dfs.append(df_batch)
    print(f"Käsitelty {i+len(batch_files)}/{len(valid_files)} tiedostoa")

# 4. Yhdistä kaikki ja poista mahdolliset duplikaatit aikaleimojen osalta
final_df = pl.concat(dfs).unique('timestamp')

# 5. Tallenna yhdistetty tiedosto
final_df.write_parquet(SAVE_PATH)
print(f"Yhdistetty tiedosto tallennettu: {SAVE_PATH}")