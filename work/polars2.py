import polars as pl
import glob
import os
import sys
import numpy as np

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
pl.Config.set_ascii_tables(True)

DATA_DIR = r'C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\microstructure'
FEE = 0.0025
SIGNAL_MULT = 1.5
YEARLY_PERIODS = 105120  # 5min * 365 * 24 * 12 = 105120

def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, '*.parquet')))
    print(f'Löytyi {len(files)} tiedostoa')
    
    # Lue kaikki tiedostot ja yhdistä (diagonal sallii erikokoiset sarakejoukot)
    df = pl.concat([pl.read_parquet(f) for f in files], how='diagonal')
    print(f'Yhdistetty: {df.shape[0]:,} riviä')
    
    # Aikaleimat
    df = df.with_columns(
        pl.from_epoch('timestamp', time_unit='s').alias('dt')
    )
    
    # Poista duplikaatit timestampin perusteella ja järjestä aikaleiman mukaan
    df = df.unique(subset=['timestamp'], keep='first').sort('dt')
    print(f'Uniikit rivit: {df.shape[0]:,} riviä')
    
    # Laske log-tuotot puhtaasta aikajärjestyksestä
    df = df.with_columns([
        (pl.col('mid_price') / pl.col('mid_price').shift(1)).log().alias('log_ret')
    ])

    # 5-min realized volatility (sum of squared returns)
    df_5m = df.group_by_dynamic('dt', every='5m').agg([
        (pl.col('log_ret').fill_null(0) ** 2).sum().alias('rv_sq_sum')
    ])
    print(f'5-min ryhmitelty: {df_5m.shape[0]:,} riviä')
    print(df_5m.head(5))
    
if __name__ == '__main__':
    main()