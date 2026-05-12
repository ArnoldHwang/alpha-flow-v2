# src/live/live_price_feed.py

import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone

import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from live.providers.alpaca_provider import (
    fetch_alpaca_latest_bars_with_retry,
)

RAW_DAILY_DIR = ROOT / "data" / "raw" / "daily"
LIVE_FEED_DIR = ROOT / "data" / "live_feed"
LIVE_STATES_DIR = ROOT / "data" / "live_states"

OUTPUT_PATH = LIVE_FEED_DIR / "live_quotes.json"
BOARD_PATH = LIVE_STATES_DIR / "_live_decision_board.json"

BATCH_SIZE = 10
REQUEST_SLEEP_SEC = 3
SYMBOL_LIMIT = 30

ALPACA_FEED = os.getenv("ALPACA_FEED", "iex").strip().lower()


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


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


def is_alpaca_stock_symbol(symbol):
    if not symbol:
        return False

    blocked_symbols = {
        "BTC-USD",
        "ETH-USD",
        "CL-F",
        "BZ-F",
        "GC-F",
        "DX-Y-NYB",
        "VIX",
        "TNX",
    }

    if symbol in blocked_symbols:
        return False

    if symbol.startswith("^"):
        return False

    if symbol.endswith("-USD"):
        return False

    if symbol.endswith("-F"):
        return False

    if "=" in symbol:
        return False

    return True


def load_latest_confirmed_close(symbol):
    """
    최근 확정 일봉 close 사용.
    move 계산 핵심.
    """

    path = RAW_DAILY_DIR / f"{symbol}.json"

    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return None

        if len(data) == 0:
            return None

        last = data[-1]

        return safe_float(last.get("close") or last.get("adjClose"))

    except Exception:
        return None


def extract_top_symbols_from_board():
    data = load_json(BOARD_PATH, {})
    board = data.get("board", {})

    if not isinstance(board, dict):
        return []

    priority_groups = [
        "ACTION_CONFIRMING",
        "ACTION_WATCH",
        "ACTION_CAUTION",
        "ACTION_RISK_OFF",
    ]

    candidates = []

    for group in priority_groups:
        rows = board.get(group, [])

        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue

            symbol = row.get("symbol")

            if not is_alpaca_stock_symbol(symbol):
                continue

            score = safe_float(row.get("score", row.get("livePressureScore", 0)))

            move = safe_float(row.get("move", row.get("dayChangePct", 0)))

            candidates.append(
                {
                    "symbol": symbol,
                    "score": score,
                    "move": move,
                }
            )

    best_by_symbol = {}

    for item in candidates:
        symbol = item["symbol"]

        if symbol not in best_by_symbol:
            best_by_symbol[symbol] = item
            continue

        if item["score"] > best_by_symbol[symbol]["score"]:
            best_by_symbol[symbol] = item

    ranked = sorted(
        best_by_symbol.values(),
        key=lambda x: (x["score"], x["move"]),
        reverse=True,
    )

    return [x["symbol"] for x in ranked[:SYMBOL_LIMIT]]


def load_fallback_symbols():
    symbols = []

    if RAW_DAILY_DIR.exists():
        for path in RAW_DAILY_DIR.glob("*.json"):
            symbol = path.stem.strip()

            if symbol and is_alpaca_stock_symbol(symbol):
                symbols.append(symbol)

    symbols = sorted(set(symbols))
    return symbols[:SYMBOL_LIMIT]


def load_symbols():
    top_symbols = extract_top_symbols_from_board()

    if top_symbols:
        print("symbolSource: decision_board_top_symbols")
        return top_symbols

    print("symbolSource: fallback_raw_daily")
    return load_fallback_symbols()


def load_previous_quotes():
    if not OUTPUT_PATH.exists():
        return {}

    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])

        return {row.get("symbol"): row for row in items if row.get("symbol")}

    except Exception:
        return {}


def normalize_alpaca_bar(symbol, bar, previous=None):
    if previous is None:
        previous = {}

    price = safe_float(bar.get("c"))
    open_price = safe_float(bar.get("o"))
    high = safe_float(bar.get("h"))
    low = safe_float(bar.get("l"))
    volume = safe_float(bar.get("v"))

    confirmed_close = load_latest_confirmed_close(symbol)

    # 핵심 수정:
    # move = 현재가 vs 최근 확정 종가
    day_change_pct = calc_pct(price, confirmed_close)

    intraday_from_open_pct = calc_pct(price, open_price)
    close_position = calc_close_position(price, low, high)

    return {
        "symbol": symbol,
        "provider": "alpaca",
        "status": "OK" if price is not None else "ERROR",
        "marketState": "UNKNOWN",
        "currency": previous.get("currency", "USD"),
        "exchangeName": previous.get("exchangeName"),
        "instrumentType": previous.get("instrumentType", "EQUITY"),
        "regularMarketPrice": price,
        "regularMarketPreviousClose": confirmed_close,
        "regularMarketOpen": open_price,
        "regularMarketDayHigh": high,
        "regularMarketDayLow": low,
        "regularMarketVolume": volume,
        "averageDailyVolume": previous.get("averageDailyVolume"),
        "dayChangePct": day_change_pct,
        "intradayFromOpenPct": intraday_from_open_pct,
        "volumeRatio": previous.get("volumeRatio"),
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
        "alpacaBarTime": bar.get("t"),
        "alpacaVwap": bar.get("vw"),
        "alpacaTradeCount": bar.get("n"),
        "confirmedClose": confirmed_close,
        "fetchedAtUtc": now_utc(),
    }


def build_stale_row(symbol, previous, error):
    row = dict(previous)

    row["status"] = "STALE_OK"
    row["provider"] = row.get("provider", "alpaca")
    row["staleReason"] = str(error)
    row["lastFetchFailedAtUtc"] = now_utc()

    return row


def build_error_row(symbol, error):
    return {
        "symbol": symbol,
        "provider": "alpaca",
        "status": "ERROR",
        "error": str(error),
        "regularMarketPrice": None,
        "dayChangePct": None,
        "fetchedAtUtc": now_utc(),
    }


def main():
    print("=================================")
    print("🔥 LIVE PRICE FEED - ALPACA")
    print("=================================")

    LIVE_FEED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    symbols = load_symbols()
    previous_quotes = load_previous_quotes()

    print(f"provider: alpaca")
    print(f"feed: {ALPACA_FEED}")
    print(f"symbols: {len(symbols)}")
    print(f"batchSize: {BATCH_SIZE}")
    print("watchSymbols:", ", ".join(symbols))

    rows_by_symbol = {}

    ok_count = 0
    stale_count = 0
    error_count = 0

    for batch_index, batch in enumerate(
        chunk_list(symbols, BATCH_SIZE),
        start=1,
    ):
        print("")
        print(f"batch {batch_index}: {len(batch)} symbols")

        try:
            bars = fetch_alpaca_latest_bars_with_retry(
                symbols=batch,
                feed=ALPACA_FEED,
            )

            for symbol in batch:
                bar = bars.get(symbol)

                if bar:
                    row = normalize_alpaca_bar(
                        symbol=symbol,
                        bar=bar,
                        previous=previous_quotes.get(symbol),
                    )

                    if row["status"] == "OK":
                        ok_count += 1
                    else:
                        error_count += 1

                    rows_by_symbol[symbol] = row

                else:
                    previous = previous_quotes.get(symbol)

                    if previous:
                        rows_by_symbol[symbol] = build_stale_row(
                            symbol,
                            previous,
                            "alpaca symbol not returned",
                        )
                        stale_count += 1
                    else:
                        rows_by_symbol[symbol] = build_error_row(
                            symbol,
                            "alpaca symbol not returned",
                        )
                        error_count += 1

        except Exception as e:
            print(f"❌ batch failed: {e}")

            for symbol in batch:
                previous = previous_quotes.get(symbol)

                if previous:
                    rows_by_symbol[symbol] = build_stale_row(
                        symbol,
                        previous,
                        e,
                    )
                    stale_count += 1
                else:
                    rows_by_symbol[symbol] = build_error_row(
                        symbol,
                        e,
                    )
                    error_count += 1

        time.sleep(REQUEST_SLEEP_SEC)

    rows = [rows_by_symbol[s] for s in symbols]

    output = {
        "generatedAt": now_utc(),
        "source": "alpaca_provider",
        "provider": "alpaca",
        "feed": ALPACA_FEED,
        "batchSize": BATCH_SIZE,
        "totalSymbols": len(rows),
        "okCount": ok_count,
        "staleCount": stale_count,
        "errorCount": error_count,
        "items": rows,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("")
    print("=================================")
    print("✅ LIVE PRICE FEED SAVED")
    print("=================================")

    print(f"ok: {ok_count}")
    print(f"stale: {stale_count}")
    print(f"error: {error_count}")

    print("")
    print("sample:")

    for row in rows[:10]:
        print(
            row.get("symbol"),
            "price=",
            row.get("regularMarketPrice"),
            "move=",
            row.get("dayChangePct"),
        )


if __name__ == "__main__":
    main()
