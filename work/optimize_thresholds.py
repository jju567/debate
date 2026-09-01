import pandas as pd
import numpy as np
import json
import sqlite3
import os

# Määritetään tietokannan polku
db_path = r'C:\Users\Jarmo\Documents\kode\trade\tradeBotEetu\data\tradebot.db'

# Ladataan Binance-data tietokannasta (timestamp millisekunteina)
import time
three_years_ago_ms = int((time.time() - (3 * 365 * 86400)) * 1000)
conn = sqlite3.connect(db_path)
query = f'SELECT timestamp, open, high, low, close, volume FROM market_candles WHERE timestamp >= {three_years_ago_ms} ORDER BY timestamp ASC'
market_data = pd.read_sql_query(query, conn)
if market_data.empty: # Jos 3v sitten ei ole dataa, ladataan kaikki
    query = 'SELECT timestamp, open, high, low, close, volume FROM market_candles ORDER BY timestamp ASC'
    market_data = pd.read_sql_query(query, conn)
conn.close()

if market_data.empty:
    print("Huomio: Tietokannassa ei ole kynttilöitä kyselyllä.")
else:
    # Lasketaan 5min tuotot ja seuraavan kynttilän profit kaupoille
    market_data['returns'] = market_data['close'].pct_change().fillna(0)
    market_data['profit'] = market_data['returns'].shift(-1).fillna(0)

    # Määritellään kynnysarvot, joita testataan
    thresholds = [2.0, 2.5, 3.0, 3.5]
    results = []

    mean = np.mean(market_data['returns'])
    std_dev = np.std(market_data['returns'])
    if std_dev > 0:
        market_data['z_score'] = (market_data['returns'] - mean) / std_dev
    else:
        market_data['z_score'] = 0

    for threshold in thresholds:
        signals = market_data[market_data['z_score'].abs() >= threshold].copy()

        total_trades = len(signals)
        win_rate = (signals['profit'] > 0).mean() * 100 if total_trades > 0 else 0

        profit_std = signals['profit'].std()
        periods_per_year = 252 * 288  # 5-minuutin kynttilät vuodessa
        gross_sharpe = (signals['profit'].mean() / profit_std) * np.sqrt(periods_per_year) if (profit_std and profit_std > 0) else 0

        # Maker ja taker kulut
        total_cost = total_trades * (0.0015 + 0.0025) * np.abs(signals['profit']).sum()
        net_sharpe = ((signals['profit'].sum() - total_cost) / profit_std) * np.sqrt(periods_per_year) if (profit_std and profit_std > 0) else 0

        results.append({
            'threshold': threshold,
            'total_trades': total_trades,
            'win_rate': round(float(win_rate), 2),
            'gross_sharpe': round(float(gross_sharpe), 4),
            'net_sharpe': round(float(net_sharpe), 4)
        })

    # Tallenna tulokset JSON-tiedostoon samassa kansiossa kuin skripti
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'threshold_optimization_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4)

    print("Tulokset on tallennettu: ", output_path)

