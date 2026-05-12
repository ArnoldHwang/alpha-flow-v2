# src/live/live_price_feed.py

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

INPUT_DIR = "data/live_states"
OUTPUT_DIR = "data/live_feed"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "live_quotes.json")

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

REQUEST_SLEEP_SEC = 0.15


def load_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    return []


def save_json(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def normalize_symbol(symbol: str) -> str:
    symbol = str(symbol).strip()

    mapping = {
        "GC-F": "GC=F",
        "CL-F": "CL=F",
        "BZ-F": "BZ=F",
        "TNX": "^TNX",
        "VIX": "^VIX",
        "DX-Y-NYB": "DX-Y.NYB",
    }

    return mapping.get(symbol, symbol)


def restore_symbol(symbol: str) -> str:
    mapping = {
        "GC=F": "GC-F",
        "CL=F": "CL-F",
        "BZ=F": "BZ-F",
        "^TNX": "TNX",
        "^VIX": "VIX",
        "DX-Y.NYB": "DX-Y-NYB",
    }

    return mapping.get(symbol, symbol)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def load_target_symbols() -> List[str]:
    summary_path = os.path.join(INPUT_DIR, "_live_state_summary.json")

    if not os.path.exists(summary_path):
        raise FileNotFoundError(
            f"live state summary not found: {summary_path}\n"
            "먼저 실행: python src/live/build_live_state_engine.py"
        )

    rows = load_json(summary_path)

    symbols = []

    for row in rows:
        if row.get("status") != "OK":
            continue

        symbol = row.get("symbol")

        if not symbol:
            continue

        symbols.append(normalize_symbol(symbol))

    return sorted(set(symbols))


def fetch_chart_quote(symbol: str) -> Optional[Dict[str, Any]]:
    url = YAHOO_CHART_URL.format(symbol=symbol)

    params = {
        "range": "1d",
        "interval": "1m",
        "includePrePost": "false",
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=15,
        )

        if response.status_code != 200:
            return {
                "symbol": restore_symbol(symbol),
                "yahooSymbol": symbol,
                "status": "ERROR",
                "error": f"HTTP_{response.status_code}",
                "fetchedAtUtc": datetime.now(timezone.utc).isoformat(),
            }

        data = response.json()
        result = data.get("chart", {}).get("result", [])

        if not result:
            return {
                "symbol": restore_symbol(symbol),
                "yahooSymbol": symbol,
                "status": "ERROR",
                "error": "NO_RESULT",
                "fetchedAtUtc": datetime.now(timezone.utc).isoformat(),
            }

        chart = result[0]
        meta = chart.get("meta", {})
        indicators = chart.get("indicators", {})
        quote_list = indicators.get("quote", [])

        if not quote_list:
            return {
                "symbol": restore_symbol(symbol),
                "yahooSymbol": symbol,
                "status": "ERROR",
                "error": "NO_QUOTE",
                "fetchedAtUtc": datetime.now(timezone.utc).isoformat(),
            }

        quote = quote_list[0]

        closes = quote.get("close", []) or []
        highs = quote.get("high", []) or []
        lows = quote.get("low", []) or []
        opens = quote.get("open", []) or []
        volumes = quote.get("volume", []) or []

        valid_closes = [safe_float(v, None) for v in closes if v is not None]
        valid_highs = [safe_float(v, None) for v in highs if v is not None]
        valid_lows = [safe_float(v, None) for v in lows if v is not None]
        valid_opens = [safe_float(v, None) for v in opens if v is not None]
        valid_volumes = [safe_float(v, 0) for v in volumes if v is not None]

        if not valid_closes:
            return {
                "symbol": restore_symbol(symbol),
                "yahooSymbol": symbol,
                "status": "ERROR",
                "error": "NO_CLOSE",
                "fetchedAtUtc": datetime.now(timezone.utc).isoformat(),
            }

        current_price = valid_closes[-1]
        previous_close = safe_float(meta.get("previousClose"))
        open_price = (
            valid_opens[0]
            if valid_opens
            else safe_float(meta.get("regularMarketPrice"))
        )
        day_high = max(valid_highs) if valid_highs else current_price
        day_low = min(valid_lows) if valid_lows else current_price
        current_volume = sum(valid_volumes)

        regular_market_volume = safe_float(meta.get("regularMarketVolume"))
        if regular_market_volume > current_volume:
            current_volume = regular_market_volume

        average_volume = safe_float(meta.get("averageDailyVolume10Day"))

        if average_volume <= 0:
            average_volume = safe_float(meta.get("averageDailyVolume3Month"))

        day_change_pct = 0.0
        if previous_close > 0:
            day_change_pct = (current_price - previous_close) / previous_close * 100

        intraday_from_open_pct = 0.0
        if open_price > 0:
            intraday_from_open_pct = (current_price - open_price) / open_price * 100

        volume_ratio = 0.0
        if average_volume > 0:
            volume_ratio = current_volume / average_volume

        close_position = 0.5
        if day_high > day_low:
            close_position = (current_price - day_low) / (day_high - day_low)

        live_breakout_hint = (
            current_price >= day_high * 0.995
            and day_change_pct > 1.0
            and volume_ratio >= 0.35
        )

        live_rejection_hint = (
            close_position < 0.35 and day_change_pct < 0 and volume_ratio >= 0.5
        )

        return {
            "symbol": restore_symbol(symbol),
            "yahooSymbol": symbol,
            "status": "OK",
            "marketState": meta.get("marketState"),
            "currency": meta.get("currency"),
            "exchangeName": meta.get("exchangeName"),
            "instrumentType": meta.get("instrumentType"),
            "regularMarketPrice": round(current_price, 4),
            "regularMarketPreviousClose": round(previous_close, 4),
            "regularMarketOpen": round(open_price, 4),
            "regularMarketDayHigh": round(day_high, 4),
            "regularMarketDayLow": round(day_low, 4),
            "regularMarketVolume": round(current_volume, 0),
            "averageDailyVolume": round(average_volume, 0),
            "dayChangePct": round(day_change_pct, 2),
            "intradayFromOpenPct": round(intraday_from_open_pct, 2),
            "volumeRatio": round(volume_ratio, 3),
            "closePosition": round(close_position, 3),
            "liveBreakoutHint": live_breakout_hint,
            "liveRejectionHint": live_rejection_hint,
            "fetchedAtUtc": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "symbol": restore_symbol(symbol),
            "yahooSymbol": symbol,
            "status": "ERROR",
            "error": str(e),
            "fetchedAtUtc": datetime.now(timezone.utc).isoformat(),
        }


def main() -> None:
    print("=================================")
    print("🧠 LIVE PRICE FEED")
    print("=================================")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    symbols = load_target_symbols()

    print(f"symbols: {len(symbols):,}")

    rows = []

    for idx, symbol in enumerate(symbols, start=1):
        row = fetch_chart_quote(symbol)
        rows.append(row)

        if idx % 20 == 0:
            print(f"fetched: {idx}/{len(symbols)}")

        time.sleep(REQUEST_SLEEP_SEC)

    save_json(OUTPUT_PATH, rows)

    ok_rows = [r for r in rows if r.get("status") == "OK"]
    error_rows = [r for r in rows if r.get("status") != "OK"]

    print("")
    print("=================================")
    print("✅ LIVE QUOTES SAVED")
    print("=================================")
    print(f"ok: {len(ok_rows):,}")
    print(f"errors: {len(error_rows):,}")
    print(f"saved: {OUTPUT_PATH}")

    if error_rows:
        print("")
        print("=================================")
        print("⚠️ ERRORS SAMPLE")
        print("=================================")
        for row in error_rows[:20]:
            print(row.get("symbol"), row.get("error"))

    print("")
    print("=================================")
    print("🔥 SAMPLE")
    print("=================================")

    for row in ok_rows[:30]:
        print(
            row["symbol"],
            "price=",
            row["regularMarketPrice"],
            "change%=",
            row["dayChangePct"],
            "volRatio=",
            row["volumeRatio"],
            "breakout=",
            row["liveBreakoutHint"],
            "reject=",
            row["liveRejectionHint"],
        )

    print("")
    print("✅ DONE")


if __name__ == "__main__":
    main()
