# sharpe_calc.py (KORJATTU)
import pandas as pd
import numpy as np
import glob
import os
import sys

# ----------------- Konfigurointi -----------------
DATA_DIR = r'C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\microstructure'
FEE = 0.0025               # 0.25 % taker-fee per trade
RV_WINDOW = '5min'         # realized volatility window
SIGNAL_MULT = 1.5          # mu_k + mult * sigma_k
YEARLY_PERIODS = 105120    # 5‑min jaksoa vuodessa
# -------------------------------------------------

def process_file(fp):
    """Lukee yhden parquet‑tiedoston ja palauttaa (RV-summa-aikasarja, log-return Series)."""
    df = pd.read_parquet(fp)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.set_index('timestamp').sort_index()

    df['log_ret'] = np.log(df['mid_price'] / df['mid_price'].shift(1))
    df = df.dropna(subset=['log_ret'])

    rv_series = df['log_ret'].resample(RV_WINDOW).apply(
        lambda x: (x**2).sum() if not x.empty else 0.0
    )
    return rv_series, df['log_ret']   # Palautetaan Series, EI indeksiä


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, '*.parquet')))
    if not files:
        sys.exit('No parquet files found')

    rv_sums = [] # lista 5‑min RV-summia
    logret_parts = []   # lista log-return-Sarjoja

    for f in files:
        print(f'Processing {os.path.basename(f)}...', flush=True)
        try:
            rv_sum, logret = process_file(f)
            rv_sums.append(rv_sum)
            logret_parts.append(logret)
        except Exception as e:
            print(f'  ⚠️  Virhe tiedostossa {os.path.basename(f)}: {e}', flush=True)
            continue

    # ---- Yhdistä ----
    rv_all = pd.concat(rv_sums).sort_index()
    logret_all = pd.concat(logret_parts).sort_index()

    rv = np.sqrt(rv_all).replace([np.inf, -np.inf], np.nan).dropna()
    if rv.empty:
        sys.exit('RV laskenta tyhjä – tarkista data.')

    mu_rv, std_rv = rv.mean(), rv.std()
    print(f'RV: mean={mu_rv:.6f}, std={std_rv:.6f}', flush=True)

    signal = (rv > mu_rv + SIGNAL_MULT * std_rv).astype(int)
    print(f'Signaalien osuus: {signal.mean()*100:.2f}%', flush=True)

    # ---- Strategian tuotot ----
    # TÄRKEÄÄ: signaali on 5‑min tasolla, logret on 1s tasalla → käytetään reindex + ffill
    sig_5min = signal.reindex(logret_all.index, method='ffill').fillna(0)
    sig_shifted = sig_5min.shift(1).fillna(0)

    strat_ret = sig_shifted * logret_all

    # Vähennä fee jokaisesta signaalin vaihdosta 5‑min tasolla
    trades_5min = signal.diff().abs().fillna(0)
    # Laske fee vaikutus per 1s logret-aikaväli: jaetaan 5‑min jakson pituudella (300s)
    trades_per_sec = trades_5min.reindex(logret_all.index, method='ffill').fillna(0) / 300.0
    strat_ret -= trades_per_sec * FEE

    strat_ret = strat_ret.dropna()
    if strat_ret.empty:
        sys.exit('Strategian tuotot tyhjä.')

    mean_ret, std_ret = strat_ret.mean(), strat_ret.std()
    sharpe = (mean_ret / std_ret) * np.sqrt(YEARLY_PERIODS) if std_ret != 0 else 0.0

    print(f'Keskituotto per 5 min: {mean_ret:.6f}', flush=True)
    print(f'Std per 5 min:        {std_ret:.6f}', flush=True)
    print(f'Sharpe (vuotuinen):   {sharpe:.3f}', flush=True)

    # ---- Tallenna tulos ----
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