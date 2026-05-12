import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

from config.scanner_config import (
    DATA_VERSION,
    START_DATE,
    RAW_DATA_PATH,
    TIMEFRAMES,
)

# =========================================
# LOAD SYMBOL CONFIG
# =========================================

with open("config/symbols.json", "r", encoding="utf-8") as f:
    stock_symbols = json.load(f)

with open("config/market_symbols.json", "r", encoding="utf-8") as f:
    market_symbols = json.load(f)

SYMBOLS = stock_symbols + market_symbols

# =========================================
# UTILS
# =========================================


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def to_unix(date_str):
    return int(pd.Timestamp(date_str).timestamp())


def now_unix():
    return int(datetime.now().timestamp())


def build_url(symbol):
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def get_candle_end(date_str, interval):
    d = pd.Timestamp(date_str, tz="UTC")

    if interval == "1d":
        return d.replace(hour=23, minute=59, second=59)

    if interval == "1wk":
        weekday = d.weekday()
        days_to_friday = 4 - weekday
        return (
            d + pd.Timedelta(days=days_to_friday)
        ).replace(hour=23, minute=59, second=59)

    if interval == "1mo":
        next_month = d + pd.offsets.MonthEnd(0)
        return next_month.replace(hour=23, minute=59, second=59)

    return d


def is_complete_candle(date_str, interval):
    now = pd.Timestamp.utcnow()

    candle_end = get_candle_end(date_str, interval)

    return now > candle_end


# =========================================
# FETCH
# =========================================


def fetch_yahoo(symbol, interval):
    url = build_url(symbol)

    params = {
        "period1": to_unix(START_DATE),
        "period2": now_unix(),
        "interval": interval,
        "events": "history",
        "includeAdjustedClose": "true",
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30,
    )

    data = response.json()

    result = data["chart"]["result"][0]

    timestamps = result.get("timestamp", [])

    quote = result["indicators"]["quote"][0]

    adjclose = (
        result.get("indicators", {})
        .get("adjclose", [{}])[0]
        .get("adjclose", [])
    )

    candles = []

    for i, ts in enumerate(timestamps):
        try:
            open_price = quote["open"][i]
            high_price = quote["high"][i]
            low_price = quote["low"][i]
            close_price = quote["close"][i]

            if (
                open_price is None
                or high_price is None
                or low_price is None
                or close_price is None
            ):
                continue

            volume = quote.get("volume", [0])[i] or 0

            date = (
                pd.to_datetime(ts, unit="s", utc=True)
                .strftime("%Y-%m-%d")
            )

            candles.append(
                {
                    "date": date,
                    "open": round(float(open_price), 4),
                    "high": round(float(high_price), 4),
                    "low": round(float(low_price), 4),
                    "close": round(float(close_price), 4),
                    "adjClose": round(
                        float(adjclose[i]) if i < len(adjclose) else float(close_price),
                        4,
                    ),
                    "volume": int(volume),
                }
            )

        except Exception:
            continue

    return candles


# =========================================
# SAVE
# =========================================


def save_json(symbol, timeframe_name, candles):
    folder = os.path.join(
        RAW_DATA_PATH,
        timeframe_name,
    )

    ensure_dir(folder)

    safe_symbol = (
        symbol.replace("^", "")
        .replace("=", "-")
        .replace("/", "-")
    )

    path = os.path.join(folder, f"{safe_symbol}.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            candles,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return path


# =========================================
# MAIN
# =========================================


def main():
    print("=================================")
    print("🚀 ALPHA FLOW V2 RAW SCANNER")
    print("=================================")
    print(f"📅 START_DATE: {START_DATE}")
    print(f"📦 symbols: {len(SYMBOLS)}")
    print("")

    for symbol_info in tqdm(SYMBOLS):
        symbol = symbol_info["symbol"]

        for tf_name, interval in TIMEFRAMES.items():
            try:
                candles = fetch_yahoo(symbol, interval)

                rows = []

                for c in candles:
                    row = {
                        "symbol": symbol,
                        "timeframe": interval,
                        "assetType": symbol_info.get("assetType"),
                        "sector": symbol_info.get("sector"),
                        "themes": symbol_info.get("themes", []),
                        "betaType": symbol_info.get("betaType"),
                        "marketCapGroup": symbol_info.get("marketCapGroup"),
                        "role": symbol_info.get("role"),
                        "date": c["date"],
                        "open": c["open"],
                        "high": c["high"],
                        "low": c["low"],
                        "close": c["close"],
                        "adjClose": c["adjClose"],
                        "volume": c["volume"],
                        "isComplete": is_complete_candle(
                            c["date"],
                            interval,
                        ),
                        "source": "yahoo",
                        "dataVersion": DATA_VERSION,
                        "createdAt": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        "updatedAt": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }

                    rows.append(row)

                file_path = save_json(
                    symbol,
                    tf_name,
                    rows,
                )

                complete_count = len(
                    [x for x in rows if x["isComplete"]]
                )

                live_count = len(rows) - complete_count

                print("")
                print(f"✅ {symbol} | {interval}")
                print(f"📄 rows: {len(rows)}")
                print(f"✅ complete: {complete_count}")
                print(f"⚡ live: {live_count}")
                print(f"💾 {file_path}")

            except Exception as e:
                print("")
                print(f"❌ FAIL {symbol} | {interval}")
                print(str(e))

    print("")
    print("=================================")
    print("✅ RAW COLLECTION COMPLETE")
    print("=================================")


if __name__ == "__main__":
    main()