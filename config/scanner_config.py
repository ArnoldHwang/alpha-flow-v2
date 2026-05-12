DATA_VERSION = "mtf-raw-v2"

START_DATE = "2021-01-01"

# None이면 최신 날짜까지 자동 수집
END_DATE = None

# True면 아직 확정 안 된 오늘 일봉 제거
DROP_INCOMPLETE_DAILY_CANDLE = True

DROP_INCOMPLETE_CANDLES = True

RAW_DATA_PATH = "data/raw"

TIMEFRAMES = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
}
