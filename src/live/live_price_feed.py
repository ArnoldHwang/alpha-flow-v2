# src/live/live_price_feed.py

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

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

BATCH_SIZE = int(os.getenv("LIVE_FEED_BATCH_SIZE", "10"))
REQUEST_SLEEP_SEC = float(os.getenv("LIVE_FEED_REQUEST_SLEEP_SEC", "3"))
SYMBOL_LIMIT = int(os.getenv("LIVE_FEED_SYMBOL_LIMIT", "30"))

ALPACA_FEED = os.getenv("ALPACA_FEED", "iex").strip().lower()

NY_TZ = ZoneInfo("America/New_York")


def now_utc_dt():
    return datetime.now(timezone.utc)


def now_utc():
    return now_utc_dt().isoformat()


def now_ny():
    return now_utc_dt().astimezone(NY_TZ)


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_str(value, default=""):
    if value is None:
        return default

    text = str(value).strip()

    if text == "" or text.lower() == "nan":
        return default

    return text


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


def parse_dt(value):
    if value is None:
        return None

    try:
        text = str(value).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def seconds_since(value):
    dt = parse_dt(value)

    if dt is None:
        return None

    return round((now_utc_dt() - dt).total_seconds(), 2)


def classify_market_session():
    """
    미국 정규장/프리/애프터/장외 구분.

    한국 시간 기준으로 생각하지 않고
    New York 시간 기준으로 판단한다.

    REGULAR:
      09:30 ~ 16:00 ET

    PREMARKET:
      04:00 ~ 09:30 ET

    AFTER_HOURS:
      16:00 ~ 20:00 ET

    CLOSED:
      그 외 시간 / 주말
    """
    dt = now_ny()

    if dt.weekday() >= 5:
        return "CLOSED"

    minutes = dt.hour * 60 + dt.minute

    pre_start = 4 * 60
    regular_start = 9 * 60 + 30
    regular_end = 16 * 60
    after_end = 20 * 60

    if pre_start <= minutes < regular_start:
        return "PREMARKET"

    if regular_start <= minutes < regular_end:
        return "REGULAR"

    if regular_end <= minutes < after_end:
        return "AFTER_HOURS"

    return "CLOSED"


def is_realtime_session(session):
    return session in {"REGULAR", "PREMARKET", "AFTER_HOURS"}


def is_alpaca_stock_symbol(symbol):
    symbol = safe_str(symbol).upper()

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


def load_latest_confirmed_daily_row(symbol):
    path = RAW_DAILY_DIR / f"{symbol}.json"

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list) or len(data) == 0:
            return {}

        last = data[-1]

        if not isinstance(last, dict):
            return {}

        return last
    except Exception:
        return {}


def load_latest_confirmed_close(symbol):
    row = load_latest_confirmed_daily_row(symbol)
    return safe_float(row.get("close") or row.get("adjClose"), None)


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

            symbol = safe_str(row.get("symbol")).upper()

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
            symbol = path.stem.strip().upper()

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


def normalize_alpaca_bar(symbol, bar, previous=None, market_session="UNKNOWN"):
    if previous is None:
        previous = {}

    price = safe_float(bar.get("c"), None)
    open_price = safe_float(bar.get("o"), None)
    high = safe_float(bar.get("h"), None)
    low = safe_float(bar.get("l"), None)
    volume = safe_float(bar.get("v"), None)

    confirmed_daily = load_latest_confirmed_daily_row(symbol)
    confirmed_close = safe_float(
        confirmed_daily.get("close") or confirmed_daily.get("adjClose"),
        None,
    )

    day_change_pct = calc_pct(price, confirmed_close)
    intraday_from_open_pct = calc_pct(price, open_price)
    close_position = calc_close_position(price, low, high)

    alpaca_bar_time = bar.get("t")
    quote_freshness_sec = seconds_since(alpaca_bar_time)

    is_realtime = price is not None and market_session in {
        "REGULAR",
        "PREMARKET",
        "AFTER_HOURS",
    }

    if quote_freshness_sec is not None and quote_freshness_sec > 1800:
        is_realtime = False

    data_status = "REALTIME" if is_realtime else "DELAYED_OR_SESSION_CLOSED"

    return {
        "symbol": symbol,
        "provider": "alpaca",
        "status": "OK" if price is not None else "ERROR",
        "dataStatus": data_status,
        "marketSession": market_session,
        "isRealtime": bool(is_realtime),
        "quoteFreshnessSec": quote_freshness_sec,
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
        "alpacaBarTime": alpaca_bar_time,
        "alpacaVwap": bar.get("vw"),
        "alpacaTradeCount": bar.get("n"),
        "confirmedClose": confirmed_close,
        "confirmedDate": confirmed_daily.get("date"),
        "fetchedAtUtc": now_utc(),
    }


def build_stale_row(symbol, previous, error, market_session):
    row = dict(previous or {})

    row["symbol"] = symbol
    row["provider"] = row.get("provider", "alpaca")
    row["status"] = "STALE_OK"
    row["dataStatus"] = "STALE"
    row["marketSession"] = market_session
    row["isRealtime"] = False
    row["staleReason"] = str(error)
    row["lastFetchFailedAtUtc"] = now_utc()

    last_fetch_time = row.get("fetchedAtUtc") or row.get("alpacaBarTime")
    row["quoteFreshnessSec"] = seconds_since(last_fetch_time)

    return row


def build_closed_session_row(symbol, previous, market_session):
    confirmed_daily = load_latest_confirmed_daily_row(symbol)
    confirmed_close = safe_float(
        confirmed_daily.get("close") or confirmed_daily.get("adjClose"),
        None,
    )

    if previous:
        row = dict(previous)
    else:
        row = {
            "symbol": symbol,
            "provider": "alpaca",
            "regularMarketPrice": confirmed_close,
            "regularMarketPreviousClose": confirmed_close,
            "dayChangePct": 0,
        }

    row["symbol"] = symbol
    row["status"] = "CLOSED_OK"
    row["dataStatus"] = "SESSION_CLOSED"
    row["marketSession"] = market_session
    row["isRealtime"] = False
    row["confirmedClose"] = confirmed_close
    row["confirmedDate"] = confirmed_daily.get("date")
    row["fetchedAtUtc"] = now_utc()
    row["quoteFreshnessSec"] = seconds_since(
        row.get("alpacaBarTime") or row.get("fetchedAtUtc")
    )
    row["staleReason"] = "market session closed; using confirmed/stale quote context"

    return row


def build_error_row(symbol, error, market_session):
    confirmed_close = load_latest_confirmed_close(symbol)

    return {
        "symbol": symbol,
        "provider": "alpaca",
        "status": "ERROR",
        "dataStatus": "ERROR",
        "marketSession": market_session,
        "isRealtime": False,
        "error": str(error),
        "regularMarketPrice": confirmed_close,
        "regularMarketPreviousClose": confirmed_close,
        "confirmedClose": confirmed_close,
        "dayChangePct": 0 if confirmed_close is not None else None,
        "quoteFreshnessSec": None,
        "fetchedAtUtc": now_utc(),
    }


def should_fetch_from_alpaca(market_session):
    """
    월요금 절약/에러 감소 방향:
    CLOSED에서는 굳이 Alpaca latest bar를 무리하게 때리지 않는다.
    정규장/프리/애프터에서만 fetch한다.
    """
    return market_session in {"REGULAR", "PREMARKET", "AFTER_HOURS"}


def main():
    print("=================================")
    print("🔥 LIVE PRICE FEED - ALPACA SESSION AWARE")
    print("=================================")

    LIVE_FEED_DIR.mkdir(parents=True, exist_ok=True)

    market_session = classify_market_session()
    fetch_enabled = should_fetch_from_alpaca(market_session)

    symbols = load_symbols()
    previous_quotes = load_previous_quotes()

    print(f"provider: alpaca")
    print(f"feed: {ALPACA_FEED}")
    print(f"marketSession: {market_session}")
    print(f"fetchEnabled: {fetch_enabled}")
    print(f"symbols: {len(symbols)}")
    print(f"batchSize: {BATCH_SIZE}")
    print("watchSymbols:", ", ".join(symbols))

    rows_by_symbol = {}

    ok_count = 0
    stale_count = 0
    closed_count = 0
    error_count = 0

    if not fetch_enabled:
        for symbol in symbols:
            previous = previous_quotes.get(symbol)

            rows_by_symbol[symbol] = build_closed_session_row(
                symbol=symbol,
                previous=previous,
                market_session=market_session,
            )

            closed_count += 1

    else:
        for batch_index, batch in enumerate(chunk_list(symbols, BATCH_SIZE), start=1):
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
                            market_session=market_session,
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
                                symbol=symbol,
                                previous=previous,
                                error="alpaca symbol not returned",
                                market_session=market_session,
                            )
                            stale_count += 1
                        else:
                            rows_by_symbol[symbol] = build_error_row(
                                symbol=symbol,
                                error="alpaca symbol not returned",
                                market_session=market_session,
                            )
                            error_count += 1

            except Exception as e:
                print(f"❌ batch failed: {e}")

                for symbol in batch:
                    previous = previous_quotes.get(symbol)

                    if previous:
                        rows_by_symbol[symbol] = build_stale_row(
                            symbol=symbol,
                            previous=previous,
                            error=e,
                            market_session=market_session,
                        )
                        stale_count += 1
                    else:
                        rows_by_symbol[symbol] = build_error_row(
                            symbol=symbol,
                            error=e,
                            market_session=market_session,
                        )
                        error_count += 1

            time.sleep(REQUEST_SLEEP_SEC)

    rows = [rows_by_symbol[s] for s in symbols if s in rows_by_symbol]

    output = {
        "generatedAt": now_utc(),
        "source": "alpaca_provider",
        "provider": "alpaca",
        "feed": ALPACA_FEED,
        "marketSession": market_session,
        "fetchEnabled": fetch_enabled,
        "batchSize": BATCH_SIZE,
        "totalSymbols": len(rows),
        "okCount": ok_count,
        "staleCount": stale_count,
        "closedCount": closed_count,
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
    print(f"closed: {closed_count}")
    print(f"error: {error_count}")

    print("")
    print("sample:")

    for row in rows[:10]:
        print(
            row.get("symbol"),
            "status=",
            row.get("status"),
            "session=",
            row.get("marketSession"),
            "realtime=",
            row.get("isRealtime"),
            "price=",
            row.get("regularMarketPrice"),
            "move=",
            row.get("dayChangePct"),
            "freshSec=",
            row.get("quoteFreshnessSec"),
        )


if __name__ == "__main__":
    main()
