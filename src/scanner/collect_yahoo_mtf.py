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
# LOAD CONFIG
# 설정 파일 로드
# =========================================

with open("config/symbols.json", "r", encoding="utf-8") as f:
    stock_symbols = json.load(f)

with open("config/market_symbols.json", "r", encoding="utf-8") as f:
    market_symbols = json.load(f)

SYMBOLS = stock_symbols + market_symbols


# =========================================
# UTILS
# 보조 함수
# =========================================


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def to_unix(date_str):
    return int(pd.Timestamp(date_str, tz="UTC").timestamp())


def now_unix():
    return int(datetime.now(timezone.utc).timestamp())


def safe_symbol_name(symbol):
    return symbol.replace("^", "").replace("=", "-").replace("/", "-").replace(".", "-")


def build_url(symbol):
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def get_candle_start(date_str):
    return pd.Timestamp(date_str, tz="UTC")


def get_candle_end(date_str, interval):
    start = get_candle_start(date_str)

    if interval == "1d":
        return start.replace(hour=23, minute=59, second=59)

    if interval == "1wk":
        weekday = start.weekday()
        days_to_friday = 4 - weekday

        if days_to_friday < 0:
            days_to_friday += 7

        return (start + pd.Timedelta(days=days_to_friday)).replace(
            hour=23, minute=59, second=59
        )

    if interval == "1mo":
        month_end = start + pd.offsets.MonthEnd(0)
        return month_end.replace(hour=23, minute=59, second=59)

    return start


def is_complete_candle(date_str, interval):
    now = pd.Timestamp.utcnow()
    candle_end = get_candle_end(date_str, interval)
    return now > candle_end


def timestamp_to_date(ts):
    return pd.to_datetime(ts, unit="s", utc=True).strftime("%Y-%m-%d")


def safe_float(value, digits=4):
    if value is None:
        return None
    return round(float(value), digits)


def safe_int(value):
    if value is None:
        return 0
    return int(value)


# =========================================
# YAHOO FETCH
# 야후 데이터 수집
# =========================================


def fetch_yahoo(symbol, interval):
    url = build_url(symbol)

    params = {
        "period1": to_unix(START_DATE),
        "period2": now_unix(),
        "interval": interval,
        "events": "history,div,splits",
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

    if response.status_code != 200:
        raise RuntimeError(f"Yahoo status error: {response.status_code}")

    data = response.json()

    error = data.get("chart", {}).get("error")
    if error:
        raise RuntimeError(f"Yahoo chart error: {error}")

    result = data.get("chart", {}).get("result", [None])[0]
    if not result:
        raise RuntimeError("No Yahoo result")

    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    adjclose = result.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

    events = result.get("events", {})
    dividends = events.get("dividends", {})
    splits = events.get("splits", {})

    dividend_by_date = {}
    for _, event in dividends.items():
        event_date = timestamp_to_date(event.get("date"))
        dividend_by_date[event_date] = event.get("amount", 0)

    split_by_date = {}
    for _, event in splits.items():
        event_date = timestamp_to_date(event.get("date"))
        numerator = event.get("numerator")
        denominator = event.get("denominator")

        if numerator and denominator:
            split_by_date[event_date] = float(numerator) / float(denominator)
        else:
            split_by_date[event_date] = None

    candles = []

    for i, ts in enumerate(timestamps):
        date = timestamp_to_date(ts)

        open_price = quote.get("open", [None])[i]
        high_price = quote.get("high", [None])[i]
        low_price = quote.get("low", [None])[i]
        close_price = quote.get("close", [None])[i]

        if (
            open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
        ):
            continue

        candle_start = get_candle_start(date)
        candle_end = get_candle_end(date, interval)

        candles.append(
            {
                "date": date,
                "candleStart": candle_start.strftime("%Y-%m-%d"),
                "candleEnd": candle_end.strftime("%Y-%m-%d"),
                "open": safe_float(open_price),
                "high": safe_float(high_price),
                "low": safe_float(low_price),
                "close": safe_float(close_price),
                "adjClose": safe_float(
                    adjclose[i] if i < len(adjclose) else close_price
                ),
                "volume": safe_int(quote.get("volume", [0])[i]),
                "dividend": safe_float(dividend_by_date.get(date, 0)),
                "splitRatio": split_by_date.get(date),
                "isComplete": is_complete_candle(date, interval),
            }
        )

    # =========================================

    # REMOVE DUPLICATE PARTIAL CANDLES
    # 같은 주/월 진행중 봉 중복 제거
    # =========================================

    dedup = {}

    for candle in candles:
        date = candle["date"]

        if interval == "1wk":
            key = pd.Timestamp(date).strftime("%Y-%W")

        elif interval == "1mo":
            key = pd.Timestamp(date).strftime("%Y-%m")

        else:
            key = date

        dedup[key] = candle

    return list(dedup.values())


# =========================================
# SAVE
# JSON 저장
# =========================================


def save_json(symbol, timeframe_name, rows):
    folder = os.path.join(RAW_DATA_PATH, timeframe_name)
    ensure_dir(folder)

    file_path = os.path.join(folder, f"{safe_symbol_name(symbol)}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    return file_path


# =========================================
# BUILD ROW
# 저장 row 생성
# =========================================


def build_row(symbol_info, interval, candle):
    symbol = symbol_info["symbol"]
    now_iso = datetime.now(timezone.utc).isoformat()

    return {
        "symbol": symbol,
        "timeframe": interval,
        "assetType": symbol_info.get("assetType"),
        "sector": symbol_info.get("sector"),
        "themes": symbol_info.get("themes", []),
        "betaType": symbol_info.get("betaType"),
        "marketCapGroup": symbol_info.get("marketCapGroup"),
        "role": symbol_info.get("role"),
        "date": candle["date"],
        "candleStart": candle["candleStart"],
        "candleEnd": candle["candleEnd"],
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "adjClose": candle["adjClose"],
        "volume": candle["volume"],
        "dividend": candle["dividend"],
        "splitRatio": candle["splitRatio"],
        "isComplete": candle["isComplete"],
        "source": "yahoo",
        "dataVersion": DATA_VERSION,
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }


# =========================================
# MAIN
# 실행부
# =========================================


def main():
    print("=================================")
    print("🚀 ALPHA-FLOW V2 MTF RAW SCANNER")
    print("=================================")
    print(f"START_DATE: {START_DATE}")
    print(f"symbols: {len(SYMBOLS)}")
    print("")

    for symbol_info in tqdm(SYMBOLS):
        symbol = symbol_info["symbol"]

        for timeframe_name, interval in TIMEFRAMES.items():
            try:
                candles = fetch_yahoo(symbol, interval)
                rows = [build_row(symbol_info, interval, candle) for candle in candles]

                file_path = save_json(symbol, timeframe_name, rows)

                complete_count = sum(1 for row in rows if row["isComplete"])
                live_count = len(rows) - complete_count

                print("")
                print(f"✅ {symbol} | {interval}")
                print(f"rows: {len(rows)}")
                print(f"complete: {complete_count}")
                print(f"live: {live_count}")
                print(f"saved: {file_path}")

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
