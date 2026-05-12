# src/live/build_live_state_engine.py

import json
import os
from glob import glob
from typing import Any, Dict, List

import pandas as pd

# =====================================
# CONFIG
# =====================================

INPUT_PATH = "data/survivability_profiles/_latest_timeframe_profiles.json"
OUTPUT_DIR = "data/live_states"

SUMMARY_OUTPUT_PATH = os.path.join(
    OUTPUT_DIR,
    "_live_state_summary.json",
)


# =====================================
# JSON UTILS
# =====================================


def load_json_records(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["records", "data", "rows", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]

        return [data]

    return []


def save_json(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


# =====================================
# SAFE
# =====================================


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default

        return float(value)

    except Exception:
        return default


def safe_state(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"

    text = str(value).strip()

    if text == "" or text.lower() == "nan":
        return "NA"

    return text


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 2)


# =====================================
# LIVE FEATURE BUILD
# =====================================


def build_live_metrics(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    현재 구조:
    아직 실시간 API 연결 전 단계.

    survivability 데이터의 최신 상태 기반으로
    live deviation 가상 layer 생성.

    이후:
    websocket / live api 연결 시
    현재가 / 실시간 거래량 / VWAP 등 연결 예정.
    """

    result = {}

    survivability = safe_float(
        row.get("continuationSurvivabilityScore"),
        50,
    )

    failure_risk = safe_float(
        row.get("continuationFailureRisk"),
        50,
    )

    tactical = safe_float(
        row.get("tacticalBurstScore"),
        50,
    )

    swing = safe_float(
        row.get("swingContinuationScore"),
        50,
    )

    institutional = safe_float(
        row.get("institutionalSurvivabilityScore"),
        50,
    )

    trajectory = safe_state(row.get("trajectoryState"))
    hierarchy = safe_state(row.get("finalHierarchyState"))
    daily_state = safe_state(row.get("dailyContinuationState"))

    # =====================================
    # LIVE PRESSURE
    # =====================================

    live_breakout_pressure = (
        tactical * 0.45 + survivability * 0.25 + swing * 0.20 - failure_risk * 0.10
    )

    if trajectory == "ACCELERATING_TRAJECTORY":
        live_breakout_pressure += 12

    if trajectory == "RECOVERY_TRAJECTORY":
        live_breakout_pressure += 8

    if daily_state in [
        "RE_ACCELERATING_CONTINUATION",
        "LATE_STAGE_CONTINUATION",
    ]:
        live_breakout_pressure += 8

    if hierarchy in [
        "TERMINAL_STRUCTURE_RISK",
        "LATE_STAGE_REACCELERATION",
    ]:
        live_breakout_pressure += 10

    live_breakout_pressure = clamp(live_breakout_pressure)

    # =====================================
    # LIVE REACCELERATION
    # =====================================

    live_reacceleration = (
        survivability * 0.35 + swing * 0.35 + institutional * 0.20 - failure_risk * 0.10
    )

    if trajectory == "RECOVERY_TRAJECTORY":
        live_reacceleration += 15

    if daily_state in [
        "SOFT_PULLBACK",
        "HEALTHY_RESET",
        "BASE_BUILDING",
    ]:
        live_reacceleration += 10

    if hierarchy == "AGING_CONTINUATION_STRUCTURE":
        live_reacceleration += 10

    if trajectory == "VOLATILE_CHOP":
        live_reacceleration -= 15

    live_reacceleration = clamp(live_reacceleration)

    # =====================================
    # LIVE FAILURE
    # =====================================

    live_failure_pressure = (
        failure_risk * 0.60 + (100 - survivability) * 0.20 + (100 - swing) * 0.20
    )

    if trajectory == "DISTRIBUTION_TRAJECTORY":
        live_failure_pressure += 10

    if trajectory == "BREAKDOWN_PERSISTENCE":
        live_failure_pressure += 15

    if trajectory == "VOLATILE_CHOP":
        live_failure_pressure += 20

    if daily_state in [
        "REAL_BREAKDOWN",
        "PANIC_SELLING",
    ]:
        live_failure_pressure += 12

    if hierarchy == "TERMINAL_STRUCTURE_RISK":
        live_failure_pressure += 10

    live_failure_pressure = clamp(live_failure_pressure)

    # =====================================
    # LIVE CONTINUATION PRESSURE
    # =====================================

    live_continuation_pressure = (
        survivability * 0.40 + institutional * 0.30 + swing * 0.20 - failure_risk * 0.10
    )

    if hierarchy == "AGING_CONTINUATION_STRUCTURE":
        live_continuation_pressure += 12

    if trajectory == "STABLE_CONTINUATION":
        live_continuation_pressure += 10

    if trajectory == "RECOVERY_TRAJECTORY":
        live_continuation_pressure += 5

    if hierarchy == "ELITE_CONTINUATION_STRUCTURE":
        live_continuation_pressure -= 4

    live_continuation_pressure = clamp(live_continuation_pressure)

    result["liveBreakoutPressure"] = live_breakout_pressure
    result["liveReaccelerationSignal"] = live_reacceleration
    result["liveFailurePressure"] = live_failure_pressure
    result["liveContinuationPressure"] = live_continuation_pressure

    return result


# =====================================
# LIVE STATE
# =====================================


def classify_live_state(row: Dict[str, Any]) -> str:
    breakout = safe_float(row.get("liveBreakoutPressure"))
    reacc = safe_float(row.get("liveReaccelerationSignal"))
    fail = safe_float(row.get("liveFailurePressure"))
    continuation = safe_float(row.get("liveContinuationPressure"))

    if fail >= 75:
        return "LIVE_FAILURE_RISK"

    if breakout >= 58 and reacc >= 65:
        return "LIVE_REACCELERATION"

    if breakout >= 60:
        return "LIVE_BREAKOUT"

    if continuation >= 68 and fail <= 45:
        return "LIVE_CONTINUATION"

    if fail >= 60:
        return "LIVE_DISTRIBUTION"

    return "LIVE_NEUTRAL"


def classify_live_bias(row: Dict[str, Any]) -> str:
    state = safe_state(row.get("liveState"))

    if state in [
        "LIVE_REACCELERATION",
        "LIVE_BREAKOUT",
    ]:
        return "OFFENSIVE"

    if state == "LIVE_CONTINUATION":
        return "CONSTRUCTIVE"

    if state in [
        "LIVE_DISTRIBUTION",
        "LIVE_FAILURE_RISK",
    ]:
        return "DEFENSIVE"

    return "NEUTRAL"


# =====================================
# PROCESS
# =====================================


def process_file(path: str) -> Dict[str, Any]:
    file_name = os.path.basename(path)
    symbol = file_name.replace(".json", "")

    rows = load_json_records(path)

    if not rows:
        return {
            "symbol": symbol,
            "status": "SKIPPED_EMPTY",
        }

    df = pd.DataFrame(rows)

    if df.empty:
        return {
            "symbol": symbol,
            "status": "SKIPPED_EMPTY",
        }

    if "date" in df.columns:
        df["date"] = pd.to_datetime(
            df["date"],
            errors="coerce",
        )

        df = df.sort_values("date")

    latest = df.iloc[-1].to_dict()

    live_metrics = build_live_metrics(latest)
    latest.update(live_metrics)

    latest["liveState"] = classify_live_state(latest)
    latest["liveBias"] = classify_live_bias(latest)

    return {
        "symbol": safe_state(latest.get("symbol", symbol)),
        "date": (
            latest.get("date").strftime("%Y-%m-%d")
            if hasattr(latest.get("date"), "strftime")
            else safe_state(latest.get("date"))
        ),
        # existing context
        "continuationSurvivabilityScore": latest.get("continuationSurvivabilityScore"),
        "continuationSurvivabilityGrade": latest.get("continuationSurvivabilityGrade"),
        "tacticalBurstScore": latest.get("tacticalBurstScore"),
        "swingContinuationScore": latest.get("swingContinuationScore"),
        "institutionalSurvivabilityScore": latest.get(
            "institutionalSurvivabilityScore"
        ),
        "failureRiskScore": latest.get("failureRiskScore"),
        "timeframeProfile": latest.get("timeframeProfile"),
        "dailyContinuationState": latest.get("dailyContinuationState"),
        "trajectoryState": latest.get("trajectoryState"),
        "finalHierarchyState": latest.get("finalHierarchyState"),
        # live
        "liveBreakoutPressure": latest.get("liveBreakoutPressure"),
        "liveReaccelerationSignal": latest.get("liveReaccelerationSignal"),
        "liveFailurePressure": latest.get("liveFailurePressure"),
        "liveContinuationPressure": latest.get("liveContinuationPressure"),
        "liveState": latest.get("liveState"),
        "liveBias": latest.get("liveBias"),
        "status": "OK",
    }


# =====================================
# MAIN
# =====================================


def main() -> None:
    print("=================================")
    print("🧠 BUILD LIVE STATE ENGINE")
    print("=================================")

    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    profile_rows = load_json_records(INPUT_PATH)

    if not profile_rows:
        raise ValueError(f"No profile rows found: {INPUT_PATH}")

    results = []

    for row in profile_rows:
        if row.get("status") != "OK":
            continue

        live_metrics = build_live_metrics(row)
        row.update(live_metrics)

        row["liveState"] = classify_live_state(row)
        row["liveBias"] = classify_live_bias(row)

        results.append(
            {
                "symbol": safe_state(row.get("symbol")),
                "date": safe_state(row.get("latestDate")),
                "continuationSurvivabilityScore": row.get(
                    "continuationSurvivabilityScore"
                ),
                "continuationSurvivabilityGrade": row.get(
                    "continuationSurvivabilityGrade"
                ),
                "tacticalBurstScore": row.get("tacticalBurstScore"),
                "swingContinuationScore": row.get("swingContinuationScore"),
                "institutionalSurvivabilityScore": row.get(
                    "institutionalSurvivabilityScore"
                ),
                "failureRiskScore": row.get("failureRiskScore"),
                "timeframeProfile": row.get("timeframeProfile"),
                "dailyContinuationState": row.get("dailyContinuationState"),
                "trajectoryState": row.get("trajectoryState"),
                "finalHierarchyState": row.get("finalHierarchyState"),
                "liveBreakoutPressure": row.get("liveBreakoutPressure"),
                "liveReaccelerationSignal": row.get("liveReaccelerationSignal"),
                "liveFailurePressure": row.get("liveFailurePressure"),
                "liveContinuationPressure": row.get("liveContinuationPressure"),
                "liveState": row.get("liveState"),
                "liveBias": row.get("liveBias"),
                "status": "OK",
            }
        )

    save_json(SUMMARY_OUTPUT_PATH, results)

    df = pd.DataFrame(results)

    ok_df = df[df["status"] == "OK"].copy()

    print(f"okFiles: {len(ok_df):,}")
    print(f"saved: {SUMMARY_OUTPUT_PATH}")

    if ok_df.empty:
        print("NO RESULT")
        return

    print("")
    print("=================================")
    print("📊 LIVE STATE DISTRIBUTION")
    print("=================================")

    print(ok_df["liveState"].value_counts(dropna=False).to_string())

    display_cols = [
        "symbol",
        "date",
        "liveState",
        "liveBias",
        "liveBreakoutPressure",
        "liveReaccelerationSignal",
        "liveContinuationPressure",
        "liveFailurePressure",
        "continuationSurvivabilityScore",
        "trajectoryState",
        "finalHierarchyState",
    ]

    print("")
    print("=================================")
    print("🔥 TOP LIVE BREAKOUT")
    print("=================================")

    print(
        ok_df.sort_values(
            "liveBreakoutPressure",
            ascending=False,
        )[display_cols]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("🚀 TOP LIVE REACCELERATION")
    print("=================================")

    print(
        ok_df.sort_values(
            "liveReaccelerationSignal",
            ascending=False,
        )[display_cols]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("🏦 TOP LIVE CONTINUATION")
    print("=================================")

    print(
        ok_df.sort_values(
            "liveContinuationPressure",
            ascending=False,
        )[display_cols]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("🧨 TOP LIVE FAILURE RISK")
    print("=================================")

    print(
        ok_df.sort_values(
            "liveFailurePressure",
            ascending=False,
        )[display_cols]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("✅ DONE")
    print("=================================")


if __name__ == "__main__":
    main()
