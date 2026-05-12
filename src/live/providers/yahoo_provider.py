# src/live/providers/yahoo_provider.py

import time
import requests

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

FIELDS = [
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


def fetch_yahoo_quotes(symbols, timeout=15):
    params = {
        "symbols": ",".join(symbols),
        "fields": ",".join(FIELDS),
    }

    response = requests.get(
        YAHOO_QUOTE_URL,
        params=params,
        headers=HEADERS,
        timeout=timeout,
    )

    if response.status_code == 429:
        raise RuntimeError("YAHOO_RATE_LIMIT_429")

    response.raise_for_status()

    data = response.json()
    return data.get("quoteResponse", {}).get("result", [])


def fetch_yahoo_quotes_with_retry(symbols, timeout=15, retry=2, sleep_sec=3):
    last_error = None

    for attempt in range(1, retry + 1):
        try:
            return fetch_yahoo_quotes(symbols, timeout=timeout)
        except Exception as e:
            last_error = e
            print(f"⚠️ yahoo fetch retry {attempt}/{retry}: {e}")
            time.sleep(sleep_sec)

    raise last_error
