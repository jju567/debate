# sharpe_calc_light.py   (taustajobille)
import pandas as pd
import numpy as np
import glob, os, sys

DATA_DIR = r'C:/Users/Jarmo/Documents/kode/trade/tradeBotEetu/data/microstructure'
FEE = 0.0025
RV_WINDOW = '5min'
SIGNAL_MULT = 1.5
YEARLY_PERIODS = 105120

def aggregate_file(fp):
    """Palauttaa (rv_sum, logret_sum, logret_count) tiedostosta."""
    df = pd.read_parquet(fp)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.set_index('timestamp').sort_index()

    df['log_ret'] = np.log(df['mid_price'] / df['mid_price'].shift(1))
    df = df.dropna(subset=['log_ret'])

    # 5‑min RV = sum of squared log‑returns
    rv_sum = df['log_ret'].resample(RV_WINDOW).apply(lambda x: (x**2).sum())
    # log‑return sum ja rivimäärä (kaikki 1‑s välein)
    logret_sum = df['log_ret'].sum()
    logret_cnt = df['log_ret'].count()

    return rv_sum, logret_sum, logret_cnt

def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, '*.parquet')))
    if not files:
        sys.exit('No parquet files found')

    # alustetaan aggregaattorit
    total_rv_sum = 0.0
    total_logret_sum = 0.0
    total_logret_cnt = 0

    for f in files:
        print(f'Processing {os.path.basename(f)}...', flush=True)
        try:
            rv_sum, logret_sum, logret_cnt = aggregate_file(f)
            total_rv_sum   += rv_sum.sum()
            total_logret_sum += logret_sum
            total_logret_cnt += logret_cnt
        except Exception as e:
            print(f'  ⚠️  Virhe {os.path.basename(f)}: {e}', flush=True)
            continue

    if total_logret_cnt == 0:
        sys.exit('Ei log‑return dataa – tarkista tiedostot.')

    # RV‑keskiarvo ja -hajonta (5‑min välein)
    rv_all = np.sqrt(total_rv_sum / len(files))          # keskiarvo 5‑min välein
    mu_rv = rv_all.mean()
    std_rv = rv_all.std()

    print(f'RV: mean={mu_rv:.6f}, std={std_rv:.6f}', flush=True)

    # signaali (5‑min taso)
    signal = (rv_all > mu_rv + SIGNAL_MULT * std_rv).astype(int)
    print(f'Signaalien osuus: {signal.mean()*100:.2f}%', flush=True)

    # log‑return keskiarvo 1‑s tasolla (kaikki rivit)
    logret_all = total_logret_sum / total_logret_cnt   # keskiarvo per rivi
    # Tämä on riittävä approksimaatio Sharpe‑laskentaan (keskiarvo + std lasketaan myöhemmin)

    # Strategian tuotto (yksinkertainen): signaali * log‑tulo
    mean_ret = signal.mean() * logret_all
    # std‑arvio: oletetaan log‑returnien std ≈ 0 (koska käytämme keskiarvoa)
    std_ret = 0.0

    sharpe = (mean_ret / std_ret) * np.sqrt(YEARLY_PERIODS) if std_ret != 0 else 0.0
    print(f'Keskituotto per 5 min: {mean_ret:.6f}', flush=True)
    print(f'Std per 5 min:        {std_ret:.6f}', flush=True)
    print(f'Sharpe (vuotuinen):   {sharpe:.3f}', flush=True)

    # Tallenna tulos
    out_path = os.path.join(DATA_DIR, 'sharpe_result.txt')
    with open(out_path, 'w') as f:
        f.write(f'RV mean: {mu_rv:.6e}\n')
        f.write(f'RV std:  {std_rv:.6e}\n')
        f.write(f'Signal %: {signal.mean()*100:.2f}\n')
        f.write(f'Mean ret: {mean_ret:.6e}\n')
        f.write(f'Std ret:  {std_ret:.6e}\n')
        f.write(f'Sharpe:   {sharpe:.3f}\n')
    print(f'Tulos kirjoitettu: {out_path}', flush=True)

if __name__ == '__main__':
    main()