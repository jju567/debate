import dask.dataframe as dd
import glob

# Määrittele tiedostopolku
directory = 'C:/Users/Jarmo/Documents/kode/trade/tradeBotEetu/data/microstructure/*.parquet'
files = glob.glob(directory)

# Lue kaikki tiedostot Dask DataFrameen
ddf = dd.read_parquet(files)

# Esikatsele nopeasti ensimmäiset 5 riviä (ei lataa kaikkea muistiin)
print("--- Ensimmäiset 5 riviä ---")
print(ddf.head(5))

# Luetaan vain ensimmäinen partitio testiksi
print("\n--- Ensimmäisen partition tiedot ---")
p0 = ddf.get_partition(0).compute()
print(f"Rivejä ensimmäisessä partitiossa: {len(p0)}")
print(p0.info())