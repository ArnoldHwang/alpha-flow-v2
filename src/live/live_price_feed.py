# src/live/live_price_feed.py

import json
import time
from pathlib import Path
from datetime import datetime, timezone

import requests

ROOT = Path(__file__).resolve().parents[2]

RAW_DAILY_DIR = ROOT / "data" / "raw" / "daily"
LIVE_FEED_DIR = ROOT / "data" / "live_feed"
OUTPUT_PATH = LIVE_FEED_DIR / "live_quotes.json"

BATCH_SIZE = 20
REQUEST_SLEEP_SEC = 5
TIMEOUT_SEC = 15

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_symbols():
    symbols = []

    if RAW_DAILY_DIR.exists():
        for path in RAW_DAILY_DIR.glob("*.json"):
            symbol = path.stem.strip()
            if symbol:
                symbols.append(symbol)

    symbols = sorted(set(symbols))

    if not symbols:
        raise RuntimeError(f"no symbols found: {RAW_DAILY_DIR}")

    return symbols


def load_previous_quotes():
    if not OUTPUT_PATH.exists():
        return {}

    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", data) if isinstance(data, dict) else data

        if isinstance(items, list):
            return {
                row.get("symbol"): row
                for row in items
                if isinstance(row, dict) and row.get("symbol")
            }

        if isinstance(items, dict):
            return items

    except Exception:
        return {}

    return {}


def calc_pct(current, base):
    current = safe_float(current, None)
    base = safe_float(base, None)

    if current is None or base is None or base == 0:
        return None

    return round(((current / base) - 1) * 100, 4)


def calc_close_position(price, low, high):
    price = safe_float(price, None)
    low = safe_float(low, None)
    high = safe_float(high, None)

    if price is None or low is None or high is None or high == low:
        return None

    return round((price - low) / (high - low), 4)


def normalize_quote(q):
    symbol = q.get("symbol")
    price = q.get("regularMarketPrice")
    prev_close = q.get("regularMarketPreviousClose")
    open_price = q.get("regularMarketOpen")
    high = q.get("regularMarketDayHigh")
    low = q.get("regularMarketDayLow")
    volume = q.get("regularMarketVolume")
    avg_volume = q.get("averageDailyVolume3Month") or q.get("averageDailyVolume10Day")

    day_change_pct = q.get("regularMarketChangePercent")
    if day_change_pct is None:
        day_change_pct = calc_pct(price, prev_close)

    intraday_from_open_pct = calc_pct(price, open_price)

    volume_ratio = None
    if avg_volume and safe_float(avg_volume) > 0:
        volume_ratio = round(safe_float(volume) / safe_float(avg_volume), 4)

    close_position = calc_close_position(price, low, high)

    status = "OK" if price is not None else "ERROR"

    return {
        "symbol": symbol,
        "yahooSymbol": symbol,
        "status": status,
        "marketState": q.get("marketState"),
        "currency": q.get("currency"),
        "exchangeName": q.get("fullExchangeName") or q.get("exchange"),
        "instrumentType": q.get("quoteType"),
        "regularMarketPrice": price,
        "regularMarketPreviousClose": prev_close,
        "regularMarketOpen": open_price,
        "regularMarketDayHigh": high,
        "regularMarketDayLow": low,
        "regularMarketVolume": volume,
        "averageDailyVolume": avg_volume,
        "dayChangePct": (
            round(safe_float(day_change_pct), 4) if day_change_pct is not None else None
        ),
        "intradayFromOpenPct": intraday_from_open_pct,
        "volumeRatio": volume_ratio,
        "closePosition": close_position,
        "liveBreakoutHint": bool(
            day_change_pct is not None
            and safe_float(day_change_pct) >= 2
            and close_position is not None
            and close_position >= 0.7
        ),
        "liveRejectionHint": bool(
            day_change_pct is not None
            and safe_float(day_change_pct) <= -2
            and close_position is not None
            and close_position <= 0.35
        ),
        "fetchedAtUtc": now_utc(),
    }


def fetch_batch(symbols):
    params = {
        "symbols": ",".join(symbols),
        "fields": ",".join(
            [
                "symbol",
                "regularMarketPrice",
                "regularMarketPreviousClose",
                "regularMarketOpen",
                "regularMarketDayHigh",
                "regularMarketDayLow",
                "regularMarketVolume",
                "regularMarketChangePercent",
                "averageDailyVolume3Month",
                "averageDailyVolume10Day",
                "marketState",
                "currency",
                "exchange",
                "fullExchangeName",
                "quoteType",
            ]
        ),
    }

    response = requests.get(
        YAHOO_QUOTE_URL,
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT_SEC,
    )

    if response.status_code == 429:
        raise RuntimeError("YAHOO_RATE_LIMIT_429")

    response.raise_for_status()

    data = response.json()
    result = data.get("quoteResponse", {}).get("result", [])

    return result


def build_error_row(symbol, error, previous=None):
    if previous and previous.get("status") == "OK":
        row = dict(previous)
        row["status"] = "STALE_OK"
        row["staleReason"] = str(error)
        row["lastFetchFailedAtUtc"] = now_utc()
        return row

    return {
        "symbol": symbol,
        "yahooSymbol": symbol,
        "status": "ERROR",
        "error": str(error),
        "regularMarketPrice": None,
        "dayChangePct": None,
        "fetchedAtUtc": now_utc(),
    }


def main():
    print("=================================")
    print("🔥 LIVE PRICE FEED - BATCH YAHOO QUOTE")
    print("=================================")

    LIVE_FEED_DIR.mkdir(parents=True, exist_ok=True)

    symbols = load_symbols()
    previous_quotes = load_previous_quotes()

    print(f"symbols: {len(symbols)}")
    print(f"batchSize: {BATCH_SIZE}")

    rows_by_symbol = {}
    ok_count = 0
    stale_count = 0
    error_count = 0

    for batch_index, batch in enumerate(chunk_list(symbols, BATCH_SIZE), start=1):
        print(f"\nbatch {batch_index}: {len(batch)} symbols")

        try:
            quotes = fetch_batch(batch)
            quote_map = {q.get("symbol"): q for q in quotes if q.get("symbol")}

            for symbol in batch:
                q = quote_map.get(symbol)

                if q:
                    row = normalize_quote(q)
                    rows_by_symbol[symbol] = row

                    if row["status"] == "OK":
                        ok_count += 1
                    else:
                        previous = previous_quotes.get(symbol)
                        rows_by_symbol[symbol] = build_error_row(
                            symbol,
                            "missing regularMarketPrice",
                            previous,
                        )
                        if previous and previous.get("status") == "OK":
                            stale_count += 1
                        else:
                            error_count += 1
                else:
                    previous = previous_quotes.get(symbol)
                    rows_by_symbol[symbol] = build_error_row(
                        symbol,
                        "symbol not returned by yahoo batch quote",
                        previous,
                    )
                    if previous and previous.get("status") == "OK":
                        stale_count += 1
                    else:
                        error_count += 1

        except Exception as e:
            print(f"❌ batch failed: {e}")

            for symbol in batch:
                previous = previous_quotes.get(symbol)
                rows_by_symbol[symbol] = build_error_row(symbol, e, previous)

                if previous and previous.get("status") == "OK":
                    stale_count += 1
                else:
                    error_count += 1

            if "429" in str(e) or "YAHOO_RATE_LIMIT" in str(e):
                print("⏳ rate limited. sleeping 20s...")
                time.sleep(20)

        time.sleep(REQUEST_SLEEP_SEC)

    rows = [rows_by_symbol[s] for s in symbols]

    output = {
        "generatedAt": now_utc(),
        "source": "yahoo_quote_batch",
        "batchSize": BATCH_SIZE,
        "totalSymbols": len(rows),
        "okCount": ok_count,
        "staleCount": stale_count,
        "errorCount": error_count,
        "items": rows,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("")
    print("=================================")
    print("✅ LIVE PRICE FEED SAVED")
    print("=================================")
    print(f"ok: {ok_count}")
    print(f"stale: {stale_count}")
    print(f"error: {error_count}")
    print(f"saved: {OUTPUT_PATH}")

    print("")
    print("sample:")
    for row in rows[:10]:
        print(
            row.get("symbol"),
            row.get("status"),
            "price=",
            row.get("regularMarketPrice"),
            "move=",
            row.get("dayChangePct"),
        )


if __name__ == "__main__":
    main()
