# src/live/providers/alpaca_provider.py

import os
import time
import requests

ALPACA_LATEST_BARS_URL = "https://data.alpaca.markets/v2/stocks/bars/latest"


def get_env(name: str):
    value = os.getenv(name)

    if value is None or str(value).strip() == "":
        raise RuntimeError(f"missing environment variable: {name}")

    return value.strip()


def build_headers():
    return {
        "APCA-API-KEY-ID": get_env("APCA_API_KEY_ID"),
        "APCA-API-SECRET-KEY": get_env("APCA_API_SECRET_KEY"),
        "Accept": "application/json",
    }


def fetch_alpaca_latest_bars(symbols, timeout=15, feed="iex"):
    params = {
        "symbols": ",".join(symbols),
        "feed": feed,
    }

    response = requests.get(
        ALPACA_LATEST_BARS_URL,
        headers=build_headers(),
        params=params,
        timeout=timeout,
    )

    if response.status_code == 429:
        raise RuntimeError("ALPACA_RATE_LIMIT_429")

    response.raise_for_status()

    data = response.json()
    bars = data.get("bars", {})

    if not isinstance(bars, dict):
        return {}

    return bars


def fetch_alpaca_latest_bars_with_retry(
    symbols,
    timeout=15,
    retry=2,
    sleep_sec=3,
    feed="iex",
):
    last_error = None

    for attempt in range(1, retry + 1):
        try:
            return fetch_alpaca_latest_bars(
                symbols=symbols,
                timeout=timeout,
                feed=feed,
            )

        except Exception as e:
            last_error = e
            print(f"⚠️ alpaca fetch retry {attempt}/{retry}: {e}")
            time.sleep(sleep_sec)

    raise last_error
