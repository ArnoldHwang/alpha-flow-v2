import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SNAPSHOT_DATA_PATH = "data/snapshots"
STATE_DATA_PATH = "data/states"

TIMEFRAME_FOLDERS = ["daily", "weekly", "monthly"]

STATE_VERSION = "timeframe-state-v2"


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, rows):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def safe_float(value, default=0):
    if value is None or pd.isna(value):
        return default
    return float(value)


def classify_trend(row):
    close = safe_float(row.get("close"))
    ema20 = safe_float(row.get("ema20"))
    ema60 = safe_float(row.get("ema60"))
    ema120 = safe_float(row.get("ema120"))

    if close > ema20 > ema60 > ema120:
        return "STRONG_UPTREND"

    if close > ema20 and close > ema60:
        return "UPTREND"

    if close > ema60 and close < ema20:
        return "PULLBACK_IN_UPTREND"

    if close < ema20 and close < ema60:
        return "WEAK_OR_DOWN"

    return "NEUTRAL"


def classify_expansion(row):
    change5 = safe_float(row.get("change5"))
    change20 = safe_float(row.get("change20"))
    ema20_gap = safe_float(row.get("ema20Gap"))
    volume_ratio = safe_float(row.get("volumeRatio20"), 1)

    if change20 >= 25 and ema20_gap >= 20:
        return "EXTENDED"

    if change5 >= 10 and volume_ratio >= 1.5:
        return "RE_ACCELERATION"

    if change20 >= 10 and ema20_gap >= 5:
        return "HEALTHY_EXPANSION"

    if abs(change20) <= 5 and volume_ratio <= 1.1:
        return "COMPRESSION"

    return "NORMAL"


def classify_exhaustion(row):
    rsi = safe_float(row.get("rsi14"))
    ema20_gap = safe_float(row.get("ema20Gap"))
    volume_ratio = safe_float(row.get("volumeRatio20"), 1)
    close_position = safe_float(row.get("closePosition"), 0.5)

    if rsi >= 80 and ema20_gap >= 25 and volume_ratio >= 2:
        return "TERMINAL_RISK"

    if rsi >= 75 and ema20_gap >= 18:
        return "OVERHEATED"

    if volume_ratio >= 2 and close_position <= 0.4:
        return "DISTRIBUTION_WARNING"

    return "LOW"


def classify_location(row):
    high_gap = safe_float(row.get("distanceFromHigh20"))
    low_gap = safe_float(row.get("distanceFromLow20"))

    if high_gap >= -3:
        return "NEAR_HIGH"

    if high_gap <= -15 and low_gap >= 10:
        return "PULLBACK_ZONE"

    if low_gap <= 5:
        return "NEAR_LOW"

    return "MID_RANGE"


def build_continuation_state(row):
    trend = classify_trend(row)
    expansion = classify_expansion(row)
    exhaustion = classify_exhaustion(row)
    location = classify_location(row)

    rsi = safe_float(row.get("rsi14"))
    ema20_gap = safe_float(row.get("ema20Gap"))
    ema60_gap = safe_float(row.get("ema60Gap"))
    change5 = safe_float(row.get("change5"))
    change20 = safe_float(row.get("change20"))
    volume_ratio = safe_float(row.get("volumeRatio20"), 1)
    close_position = safe_float(row.get("closePosition"), 0.5)
    distance_from_high20 = safe_float(row.get("distanceFromHigh20"))
    distance_from_low20 = safe_float(row.get("distanceFromLow20"))

    if exhaustion == "TERMINAL_RISK":
        return "TERMINAL_RISK"

    if exhaustion == "OVERHEATED":
        return "LATE_STAGE_CONTINUATION"

    if trend == "STRONG_UPTREND" and expansion == "RE_ACCELERATION":
        return "RE_ACCELERATING_CONTINUATION"

    if trend in ["STRONG_UPTREND", "UPTREND"] and expansion == "HEALTHY_EXPANSION":
        return "HEALTHY_CONTINUATION"

    if trend in ["STRONG_UPTREND", "UPTREND"] and location == "PULLBACK_ZONE":
        return "HEALTHY_PULLBACK"

    if expansion == "COMPRESSION" and trend in ["UPTREND", "STRONG_UPTREND"]:
        return "BASE_BUILDING"

    if trend == "PULLBACK_IN_UPTREND":
        return "PAUSE_OR_PULLBACK"

    # =========================
    # WEAK_OR_DOWN 세분화
    # 기존에는 전부 DETERIORATING으로 묶어서
    # healthy reset / soft pullback / real breakdown이 섞였다.
    # =========================

    if trend == "WEAK_OR_DOWN":
        # 진짜 붕괴:
        # 20일 고점에서 많이 밀리고, 단기/중기 수익률도 약하며,
        # 종가 위치도 낮은 상태
        if (
            distance_from_high20 <= -15
            and change20 <= -8
            and change5 <= -3
            and close_position <= 0.35
        ):
            return "REAL_BREAKDOWN"

        # 패닉성 매도:
        # 거래량이 터졌는데 종가 위치가 낮고 단기 낙폭이 큼
        if volume_ratio >= 1.8 and close_position <= 0.3 and change5 <= -5:
            return "PANIC_SELLING"

        # 건강한 리셋:
        # 중기 추세 훼손은 크지 않고, 고점에서 식었지만 저점권 붕괴는 아님
        if change20 >= -5 and distance_from_low20 >= 8 and rsi >= 40:
            return "HEALTHY_RESET"

        # 약한 조정:
        # 완전 붕괴는 아니지만 아직 추세 회복은 안 된 상태
        return "SOFT_PULLBACK"

    return "NEUTRAL"


def build_state_row(row):
    now_iso = datetime.now(timezone.utc).isoformat()

    trend_state = classify_trend(row)
    expansion_state = classify_expansion(row)
    exhaustion_state = classify_exhaustion(row)
    location_state = classify_location(row)
    continuation_state = build_continuation_state(row)

    return {
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
        "close": row.get("close"),
        "ema20Gap": row.get("ema20Gap"),
        "ema60Gap": row.get("ema60Gap"),
        "ema120Gap": row.get("ema120Gap"),
        "rsi14": row.get("rsi14"),
        "atr14Pct": row.get("atr14Pct"),
        "volumeRatio20": row.get("volumeRatio20"),
        "distanceFromHigh20": row.get("distanceFromHigh20"),
        "distanceFromLow20": row.get("distanceFromLow20"),
        "change5": row.get("change5"),
        "change20": row.get("change20"),
        "volatility20": row.get("volatility20"),
        "closePosition": row.get("closePosition"),
        "trendState": trend_state,
        "expansionState": expansion_state,
        "exhaustionState": exhaustion_state,
        "locationState": location_state,
        "continuationState": continuation_state,
        "sourceSnapshotVersion": row.get("snapshotVersion"),
        "stateVersion": STATE_VERSION,
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }


def process_timeframe(timeframe_name):
    snapshot_folder = os.path.join(SNAPSHOT_DATA_PATH, timeframe_name)
    state_folder = os.path.join(STATE_DATA_PATH, timeframe_name)

    ensure_dir(state_folder)

    if not os.path.exists(snapshot_folder):
        print(f"⚠️ snapshot folder missing: {snapshot_folder}")
        return

    files = [f for f in os.listdir(snapshot_folder) if f.endswith(".json")]

    print("")
    print(f"📦 {timeframe_name} snapshot files: {len(files)}")

    for file_name in files:
        snapshot_path = os.path.join(snapshot_folder, file_name)
        save_path = os.path.join(state_folder, file_name)

        try:
            rows = load_json(snapshot_path)
            state_rows = [build_state_row(row) for row in rows]

            save_json(save_path, state_rows)

            live_count = sum(1 for x in state_rows if not x["isComplete"])

            print(
                f"✅ {timeframe_name} | {file_name} | "
                f"rows: {len(state_rows)} | live: {live_count}"
            )

        except Exception as e:
            print(f"❌ FAIL {timeframe_name} | {file_name} | {e}")


def main():
    print("=================================")
    print("🧠 ALPHA-FLOW V2 BUILD TIMEFRAME STATES")
    print("=================================")

    for timeframe_name in TIMEFRAME_FOLDERS:
        process_timeframe(timeframe_name)

    print("")
    print("=================================")
    print("✅ TIMEFRAME STATE BUILD COMPLETE")
    print("=================================")


if __name__ == "__main__":
    main()
