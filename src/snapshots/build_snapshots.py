import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config.scanner_config import RAW_DATA_PATH, DATA_VERSION

SNAPSHOT_DATA_PATH = "data/snapshots"

TIMEFRAME_FOLDERS = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
}


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def safe_float(value, digits=4):
    if pd.isna(value):
        return None
    return round(float(value), digits)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, rows):
    ensure_dir(os.path.dirname(path))

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def calc_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calc_atr(df, period=14):
    prev_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return true_range.rolling(period).mean()


def build_snapshot_df(rows):
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df.sort_values("date").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "adjClose", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema60"] = df["close"].ewm(span=60, adjust=False).mean()
    df["ema120"] = df["close"].ewm(span=120, adjust=False).mean()

    df["ema20Gap"] = ((df["close"] - df["ema20"]) / df["ema20"]) * 100
    df["ema60Gap"] = ((df["close"] - df["ema60"]) / df["ema60"]) * 100
    df["ema120Gap"] = ((df["close"] - df["ema120"]) / df["ema120"]) * 100

    df["rsi14"] = calc_rsi(df["close"], 14)
    df["atr14"] = calc_atr(df, 14)
    df["atr14Pct"] = (df["atr14"] / df["close"]) * 100

    df["volumeMa20"] = df["volume"].rolling(20).mean()
    df["volumeRatio20"] = df["volume"] / df["volumeMa20"]

    df["high20"] = df["high"].rolling(20).max()
    df["low20"] = df["low"].rolling(20).min()

    df["distanceFromHigh20"] = ((df["close"] - df["high20"]) / df["high20"]) * 100
    df["distanceFromLow20"] = ((df["close"] - df["low20"]) / df["low20"]) * 100

    df["change1"] = df["close"].pct_change(1) * 100
    df["change5"] = df["close"].pct_change(5) * 100
    df["change10"] = df["close"].pct_change(10) * 100
    df["change20"] = df["close"].pct_change(20) * 100

    df["volatility20"] = df["close"].pct_change().rolling(20).std() * 100

    df["rangePct"] = ((df["high"] - df["low"]) / df["close"]) * 100
    df["bodyPct"] = ((df["close"] - df["open"]).abs() / df["close"]) * 100

    df["closePosition"] = (df["close"] - df["low"]) / (df["high"] - df["low"])
    df["closePosition"] = df["closePosition"].replace(
        [float("inf"), -float("inf")], None
    )

    df["isAboveEma20"] = df["close"] > df["ema20"]
    df["isAboveEma60"] = df["close"] > df["ema60"]
    df["isAboveEma120"] = df["close"] > df["ema120"]

    return df


def build_snapshot_rows(df):
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = []

    for _, row in df.iterrows():
        snapshot = {
            "symbol": row.get("symbol"),
            "timeframe": row.get("timeframe"),
            "date": row.get("date"),
            "candleStart": row.get("candleStart"),
            "candleEnd": row.get("candleEnd"),
            "isComplete": bool(row.get("isComplete")),
            "assetType": row.get("assetType"),
            "sector": row.get("sector"),
            "themes": row.get("themes", []),
            "betaType": row.get("betaType"),
            "marketCapGroup": row.get("marketCapGroup"),
            "role": row.get("role"),
            "open": safe_float(row.get("open")),
            "high": safe_float(row.get("high")),
            "low": safe_float(row.get("low")),
            "close": safe_float(row.get("close")),
            "adjClose": safe_float(row.get("adjClose")),
            "volume": int(row.get("volume", 0)),
            "ema20": safe_float(row.get("ema20")),
            "ema60": safe_float(row.get("ema60")),
            "ema120": safe_float(row.get("ema120")),
            "ema20Gap": safe_float(row.get("ema20Gap")),
            "ema60Gap": safe_float(row.get("ema60Gap")),
            "ema120Gap": safe_float(row.get("ema120Gap")),
            "rsi14": safe_float(row.get("rsi14")),
            "atr14": safe_float(row.get("atr14")),
            "atr14Pct": safe_float(row.get("atr14Pct")),
            "volumeMa20": safe_float(row.get("volumeMa20")),
            "volumeRatio20": safe_float(row.get("volumeRatio20")),
            "high20": safe_float(row.get("high20")),
            "low20": safe_float(row.get("low20")),
            "distanceFromHigh20": safe_float(row.get("distanceFromHigh20")),
            "distanceFromLow20": safe_float(row.get("distanceFromLow20")),
            "change1": safe_float(row.get("change1")),
            "change5": safe_float(row.get("change5")),
            "change10": safe_float(row.get("change10")),
            "change20": safe_float(row.get("change20")),
            "volatility20": safe_float(row.get("volatility20")),
            "rangePct": safe_float(row.get("rangePct")),
            "bodyPct": safe_float(row.get("bodyPct")),
            "closePosition": safe_float(row.get("closePosition")),
            "isAboveEma20": bool(row.get("isAboveEma20")),
            "isAboveEma60": bool(row.get("isAboveEma60")),
            "isAboveEma120": bool(row.get("isAboveEma120")),
            "sourceDataVersion": DATA_VERSION,
            "snapshotVersion": "snapshot-v2",
            "createdAt": now_iso,
            "updatedAt": now_iso,
        }

        rows.append(snapshot)

    return rows


def process_timeframe(timeframe_name):
    raw_folder = os.path.join(RAW_DATA_PATH, timeframe_name)
    snapshot_folder = os.path.join(SNAPSHOT_DATA_PATH, timeframe_name)

    ensure_dir(snapshot_folder)

    if not os.path.exists(raw_folder):
        print(f"⚠️ raw folder missing: {raw_folder}")
        return

    files = [f for f in os.listdir(raw_folder) if f.endswith(".json")]

    print("")
    print(f"📦 {timeframe_name} raw files: {len(files)}")

    for file_name in files:
        raw_path = os.path.join(raw_folder, file_name)
        save_path = os.path.join(snapshot_folder, file_name)

        try:
            rows = load_json(raw_path)
            df = build_snapshot_df(rows)
            snapshot_rows = build_snapshot_rows(df)

            save_json(save_path, snapshot_rows)

            live_count = sum(1 for x in snapshot_rows if not x["isComplete"])

            print(
                f"✅ {timeframe_name} | {file_name} | "
                f"rows: {len(snapshot_rows)} | live: {live_count}"
            )

        except Exception as e:
            print(f"❌ FAIL {timeframe_name} | {file_name} | {e}")


def main():
    print("=================================")
    print("🧠 ALPHA-FLOW V2 BUILD SNAPSHOTS")
    print("=================================")

    for timeframe_name in TIMEFRAME_FOLDERS.keys():
        process_timeframe(timeframe_name)

    print("")
    print("=================================")
    print("✅ SNAPSHOT BUILD COMPLETE")
    print("=================================")


if __name__ == "__main__":
    main()
