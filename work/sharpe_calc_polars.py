import polars as pl
import glob
import os
import numpy as np

DATA_DIR = r'C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\microstructure'
FEE = 0.0025
RV_WINDOW = '5min'
SIGNAL_MULT = 1.5
YEARLY_PERIODS = 105120

def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, '*.parquet')))
    print(f'Löytyi {len(files)} tiedostoa')
    
    # Polars käsittelee duplikaatit automaattisesti group_by_dynamic:ssa
    df = pl.concat([pl.read_parquet(f) for f in files])
    print(f'Yhdistetty: {df.shape[0]:,} riviä, {df.shape[1]} saraketta')
    
    # Aikaleimat - Polars käsittelee duplikaatit turvallisesti
    df = df.with_columns(
        pl.from_epoch('timestamp', time_unit='s').alias('dt')
    ).sort('dt')
    
    # Log-tuotot
    df = df.with_columns([
        (pl.col('mid_price') / pl.col('mid_price').shift(1)).log().alias('log_ret')
    ])
    
    # 5-min realized volatility (SUMMA LOG-TUOTOJEN NELIÖISTÄ)
    df_5m = df.group_by_dynamic('dt', every='5m').agg([
        (pl.col('log_ret').fill_null(0) ** 2).sum().alias('rv_sq_sum')
    ]).with_columns(
        pl.col('rv_sq_sum').sqrt().alias('rv')
    )
    
    # Signaali (5-min tasolla)
    mu_rv = df_5m['rv'].mean()
    std_rv = df_5m['rv'].std()
    print(f'RV: mean={mu_rv:.6f}, std={std_rv:.6f}')
    
    df_5m = df_5m.with_columns(
        (pl.col('rv') > (mu_rv + SIGNAL_MULT * std_rv)).cast(pl.Int8).alias('signal')
    )
    signal_pct = df_5m['signal'].mean() * 100
    print(f'Signaalien osuus: {signal_pct:.2f}%')
    
    # Vie signaali takaisin 1s tasolle (turvallisesti duplikaateille)
    signal_1s = df_5m.select(['dt', 'signal']).join(
        df.select(['dt']), 
        on='dt', 
        how='left'
    ).with_columns(
        pl.col('signal').fill_null(strategy='forward').alias('signal_ffill')
    )
    
    # Yhdistä log_ret kanssa
    strat = signal_1s.join(
        df.select(['dt', 'log_ret']), 
        on='dt', 
        how='left'
    ).with_columns([
        (pl.col('signal_ffill') * pl.col('log_ret')).alias('strat_log_ret')
    ])
    
    # Fee-käsittely: 5-min tasolla tapahtuvat vaihdot
    df_5m = df_5m.with_columns([
        pl.col('signal').diff().fill_null(0).abs().alias('trades_5min')
    ])
    
    # Aggregoi 1s-tuotot 5-min tasolle
    df_1s_agg = df.group_by_dynamic('dt', every='5m').agg([
        pl.col('log_ret').fill_null(0).sum().alias('log_ret_sum_5min')
    ])
    
    # Yhdistä signaali + aggregoitu tuotto
    df_5m = df_5m.join(df_1s_agg, on='dt', how='left').with_columns([
        (pl.col('signal').shift(1).fill_null(0) * pl.col('log_ret_sum_5min')).alias('strat_ret_5min')
    ])
    
    # Vähennä fee (kerran per 5-min vaihto)
    df_5m = df_5m.with_columns([
        (pl.col('strat_ret_5min') - pl.col('trades_5min') * FEE).alias('strat_ret_net')
    ])
    
    # Laske Sharpe
    mean_ret = df_5m['strat_ret_net'].mean()
    std_ret = df_5m['strat_ret_net'].std()
    sharpe = (mean_ret / std_ret) * np.sqrt(YEARLY_PERIODS) if std_ret != 0 else 0.0
    
    print(f'Keskituotto per 5 min: {mean_ret:.6f}')
    print(f'Std per 5 min:        {std_ret:.6f}')
    print(f'Sharpe (vuotuinen):   {sharpe:.3f}')
    
    # Tallenna tulos
    out_path = os.path.join(DATA_DIR, 'sharpe_result.txt')
    with open(out_path, 'w') as f:
        f.write(f'RV mean: {mu_rv:.6e}\n')
        f.write(f'RV std:  {std_rv:.6e}\n')
        f.write(f'Signal %: {signal_pct:.2f}\n')
        f.write(f'Mean ret: {mean_ret:.6e}\n')
        f.write(f'Std ret:  {std_ret:.6e}\n')
        f.write(f'Sharpe:   {sharpe:.3f}\n')
    print(f'Tulos kirjoitettu: {out_path}')

if __name__ == '__main__':
    main()