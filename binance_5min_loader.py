"""Binance 5min klines -datan lataus ja tallennus Parquet-formaattiin."""
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import time
import httpx
import polars as pl

BASE = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "5m"
LIMIT = 1000
OUT_DIR = Path("data/binance_5min")
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_chunk(client: httpx.AsyncClient, start_ms: int, end_ms: int, max_retries: int = 5):
    """Hakee kynttilächunkin Binance REST API:sta retry-logiikalla."""
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LIMIT,
        "startTime": start_ms,
        "endTime": end_ms,
    }
    for attempt in range(1, max_retries + 1):
        try:
            r = await client.get(BASE, params=params, timeout=30.0)
            if r.status_code == 429:
                wait_time = int(r.headers.get("Retry-After", 10))
                print(f"[429 Rate Limit] Odotetaan {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt == max_retries:
                raise e
            wait_time = 2 ** attempt
            print(f"[Retry {attempt}/{max_retries}] Virhe: {e}. Odotetaan {wait_time}s...")
            await asyncio.sleep(wait_time)
    return []


def flush_buffer_to_parquet(buffer: list) -> int:
    """Kirjoittaa kerätyn puskurin tiedot päivittäin partitionoituihin Parquet-tiedostoihin."""
    if not buffer:
        return 0

    df = pl.DataFrame(
        buffer,
        schema=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ],
        orient="row",
    )

    df = df.select([
        pl.col("open_time").cast(pl.Int64).alias("timestamp"),
        pl.col("open").cast(pl.Float64),
        pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64),
        pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
        pl.col("quote_vol").cast(pl.Float64),
        pl.col("trades").cast(pl.Int64),
        pl.col("taker_buy_base").cast(pl.Float64),
        pl.col("taker_buy_quote").cast(pl.Float64),
    ])

    df = df.with_columns(
        pl.from_epoch(pl.col("timestamp"), time_unit="ms").dt.date().alias("date")
    )

    for (date_val,), group_df in df.group_by("date"):
        date_str = str(date_val)
        file_path = OUT_DIR / f"btcusdt_5m_{date_str}.parquet"
        save_df = group_df.drop("date")

        if file_path.exists():
            existing_df = pl.read_parquet(file_path)
            combined_df = pl.concat([existing_df, save_df]).unique(subset=["timestamp"]).sort("timestamp")
            combined_df.write_parquet(file_path)
        else:
            save_df.sort("timestamp").write_parquet(file_path)

    return df.height


async def main():
    # 2023-08-01 00:00:00 UTC -> 2026-08-31 23:59:59 UTC
    start_dt = datetime(2023, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc)

    start = int(start_dt.timestamp() * 1000)
    end = int(end_dt.timestamp() * 1000)

    print(f"Aloitetaan Binance 5min datan haku ({SYMBOL}): {start_dt.date()} -> {end_dt.date()}", flush=True)
    print(f"Tallennuskansio: {OUT_DIR.resolve()}", flush=True)

    step_ms = LIMIT * 5 * 60 * 1000
    total_candles = 0
    buffer = []
    start_perf = time.perf_counter()

    async with httpx.AsyncClient(timeout=30.0) as client:
        current = start
        while current < end:
            chunk_end = min(current + step_ms - 1, end)
            data = await fetch_chunk(client, current, chunk_end)

            if not data:
                print(f"Ei dataa välille {current} - {chunk_end}, siirrytään eteenpäin...", flush=True)
                current = chunk_end + 1
                continue

            buffer.extend(data)
            total_candles += len(data)

            # Tallennetaan levylle aina 10 000 kynttilän (~35 päivää) välein
            if len(buffer) >= 10000:
                flush_buffer_to_parquet(buffer)
                buffer.clear()

            last_ts = data[-1][0]
            last_date = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            progress_pct = min(100.0, ((last_ts - start) / (end - start)) * 100.0)

            print(f"[{progress_pct:5.1f}%] Ladattu {len(data)} kynttilaa (Viimeisin: {last_date}) | Yhteensa: {total_candles}", flush=True)

            current = last_ts + (5 * 60 * 1000)
            await asyncio.sleep(0.03)

        if buffer:
            flush_buffer_to_parquet(buffer)
            buffer.clear()

    elapsed = time.perf_counter() - start_perf
    print(f"\n[VALMIS] Ladattu yhteensa {total_candles} kynttilaa ajassa {elapsed:.1f}s.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
