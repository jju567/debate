import polars as pl

# Lataa yhdistetty data
input_path = r"C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\microstructure\merged_data.parquet"

# Lataa data vain yhdelle riville
df = pl.read_parquet(input_path, n_rows=1)

# Tulosta sarakkeet
print(df.columns)