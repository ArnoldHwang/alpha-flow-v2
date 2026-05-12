# src/survivability/build_timeframe_expectancy_profile.py

import json
import os
from glob import glob
from typing import Any, Dict, List

import pandas as pd

INPUT_DIR = "data/survivability"
OUTPUT_DIR = "data/survivability_profiles"

LATEST_OUTPUT_PATH = os.path.join(
    OUTPUT_DIR,
    "_latest_timeframe_profiles.json",
)

SUMMARY_OUTPUT_PATH = os.path.join(
    OUTPUT_DIR,
    "_timeframe_profile_summary.json",
)


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


def save_json(path: str, records: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


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


def normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0

    score = (value - low) / (high - low) * 100
    return round(max(0.0, min(100.0, score)), 2)


def calc_tactical_burst_score(row: Dict[str, Any]) -> float:
    """
    tacticalBurstScore
    = 1~5일 단기 폭발 기대값.
    단기 강한 continuation / terminal burst / re-acceleration 감지용.
    """
    daily_avg20 = safe_float(row.get("dailyPathAvgReturn20d"), 0)
    trajectory_avg20 = safe_float(row.get("trajectoryPathAvgReturn20d"), 0)
    hierarchy_avg20 = safe_float(row.get("hierarchyPathAvgReturn20d"), 0)

    daily_win20 = safe_float(row.get("dailyPathWinRate20d"), 50)
    trajectory_win20 = safe_float(row.get("trajectoryPathWinRate20d"), 50)
    hierarchy_win20 = safe_float(row.get("hierarchyPathWinRate20d"), 50)

    trajectory = safe_state(row.get("trajectoryState"))
    hierarchy = safe_state(row.get("finalHierarchyState"))
    daily_state = safe_state(row.get("dailyContinuationState"))

    avg_score = normalize(
        daily_avg20 * 0.45 + trajectory_avg20 * 0.35 + hierarchy_avg20 * 0.20,
        -5,
        15,
    )

    win_score = normalize(
        daily_win20 * 0.45 + trajectory_win20 * 0.35 + hierarchy_win20 * 0.20,
        45,
        70,
    )

    bonus = 0.0

    if trajectory == "ACCELERATING_TRAJECTORY":
        bonus += 12

    if trajectory == "RECOVERY_TRAJECTORY":
        bonus += 8

    if daily_state in [
        "RE_ACCELERATING_CONTINUATION",
        "LATE_STAGE_CONTINUATION",
        "TERMINAL_RISK",
    ]:
        bonus += 10

    if hierarchy in [
        "TERMINAL_STRUCTURE_RISK",
        "LATE_STAGE_REACCELERATION",
    ]:
        bonus += 12

    failure_risk = safe_float(row.get("continuationFailureRisk"), 50)

    risk_penalty = normalize(failure_risk, 40, 90) * 0.25

    score = avg_score * 0.50 + win_score * 0.35 + bonus - risk_penalty

    return round(max(0, min(100, score)), 2)


def calc_swing_continuation_score(row: Dict[str, Any]) -> float:
    """
    swingContinuationScore
    = 10~20일 스윙 continuation 기대값.
    """
    expectancy = safe_float(row.get("expectancyScore"), 0)
    transition = safe_float(row.get("transitionPersistenceScore"), 0)
    state_bias = safe_float(row.get("stateBiasScore"), 0)
    failure_risk = safe_float(row.get("continuationFailureRisk"), 50)

    trajectory = safe_state(row.get("trajectoryState"))
    daily_state = safe_state(row.get("dailyContinuationState"))

    bonus = 0.0

    if trajectory in ["RECOVERY_TRAJECTORY", "STABLE_CONTINUATION"]:
        bonus += 8

    if daily_state in [
        "HEALTHY_CONTINUATION",
        "SOFT_PULLBACK",
        "HEALTHY_RESET",
        "PAUSE_OR_PULLBACK",
    ]:
        bonus += 6

    score = (
        expectancy * 0.45
        + transition * 0.25
        + state_bias * 0.25
        + bonus
        - failure_risk * 0.10
    )

    return round(max(0, min(100, score)), 2)


def calc_institutional_survivability_score(row: Dict[str, Any]) -> float:
    """
    institutionalSurvivabilityScore
    = 30~60일 기관형 오래 가는 continuation.
    """
    base = safe_float(row.get("continuationSurvivabilityScore"), 0)
    transition = safe_float(row.get("transitionPersistenceScore"), 0)
    failure_risk = safe_float(row.get("continuationFailureRisk"), 50)

    hierarchy = safe_state(row.get("finalHierarchyState"))
    trajectory = safe_state(row.get("trajectoryState"))
    timeframe_type = safe_state(row.get("timeframeExpectancyType"))

    bonus = 0.0

    if hierarchy == "AGING_CONTINUATION_STRUCTURE":
        bonus += 14

    if hierarchy == "HEALTHY_BUT_MONTHLY_EXTENDED":
        bonus += 10

    if trajectory == "STABLE_CONTINUATION":
        bonus += 10

    if trajectory == "RECOVERY_TRAJECTORY":
        bonus += 5

    if timeframe_type == "INSTITUTIONAL_DRIFT_EXPECTANCY":
        bonus += 15

    if timeframe_type == "SWING_TO_MIDTERM_EXPECTANCY":
        bonus += 8

    if hierarchy == "ELITE_CONTINUATION_STRUCTURE":
        bonus -= 5

    if hierarchy == "TERMINAL_STRUCTURE_RISK":
        bonus -= 8

    score = base * 0.45 + transition * 0.30 + bonus - failure_risk * 0.12

    return round(max(0, min(100, score)), 2)


def calc_failure_risk_score(row: Dict[str, Any]) -> float:
    risk = safe_float(row.get("continuationFailureRisk"), 50)

    trajectory = safe_state(row.get("trajectoryState"))
    daily_state = safe_state(row.get("dailyContinuationState"))
    hierarchy = safe_state(row.get("finalHierarchyState"))

    if trajectory == "VOLATILE_CHOP":
        risk += 12

    if trajectory == "BREAKDOWN_PERSISTENCE":
        risk += 10

    if daily_state in ["REAL_BREAKDOWN", "PANIC_SELLING"]:
        risk += 8

    if hierarchy == "TERMINAL_STRUCTURE_RISK":
        risk += 8

    if trajectory in ["RECOVERY_TRAJECTORY", "STABLE_CONTINUATION"]:
        risk -= 6

    if hierarchy == "AGING_CONTINUATION_STRUCTURE":
        risk -= 5

    return round(max(0, min(100, risk)), 2)


def classify_profile(
    tactical: float,
    swing: float,
    institutional: float,
    failure: float,
) -> str:
    if failure >= 70:
        return "HIGH_FAILURE_RISK"

    if tactical >= 65 and swing >= 55:
        return "TACTICAL_BURST_CONTINUATION"

    if institutional >= 62 and failure <= 45:
        return "INSTITUTIONAL_SURVIVABILITY"

    if swing >= 58 and failure <= 50:
        return "SWING_CONTINUATION"

    if tactical >= 58 and failure <= 60:
        return "TACTICAL_ONLY"

    if institutional >= 55:
        return "SLOW_DRIFT_CONTINUATION"

    return "MIXED_OR_LOW_EDGE"


def build_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    tactical = calc_tactical_burst_score(row)
    swing = calc_swing_continuation_score(row)
    institutional = calc_institutional_survivability_score(row)
    failure = calc_failure_risk_score(row)

    profile = classify_profile(
        tactical=tactical,
        swing=swing,
        institutional=institutional,
        failure=failure,
    )

    result = dict(row)

    result["tacticalBurstScore"] = tactical
    result["swingContinuationScore"] = swing
    result["institutionalSurvivabilityScore"] = institutional
    result["failureRiskScore"] = failure
    result["timeframeProfile"] = profile

    return result


def process_symbol_file(path: str) -> Dict[str, Any]:
    file_name = os.path.basename(path)
    symbol = file_name.replace(".json", "")

    records = load_json_records(path)

    if not records:
        return {
            "symbol": symbol,
            "file": file_name,
            "status": "SKIPPED_EMPTY",
            "rows": 0,
        }

    df = pd.DataFrame(records)

    if "date" not in df.columns:
        return {
            "symbol": symbol,
            "file": file_name,
            "status": "SKIPPED_NO_DATE",
            "rows": len(df),
        }

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df = df.sort_values("date").copy()

    latest = df.iloc[-1].to_dict()

    profile = build_profile(latest)

    return {
        "symbol": safe_state(profile.get("symbol", symbol)),
        "file": file_name,
        "status": "OK",
        "latestDate": (
            profile.get("date").strftime("%Y-%m-%d")
            if hasattr(profile.get("date"), "strftime")
            else safe_state(profile.get("date"))
        ),
        "continuationSurvivabilityScore": profile.get("continuationSurvivabilityScore"),
        "continuationSurvivabilityGrade": profile.get("continuationSurvivabilityGrade"),
        "tacticalBurstScore": profile.get("tacticalBurstScore"),
        "swingContinuationScore": profile.get("swingContinuationScore"),
        "institutionalSurvivabilityScore": profile.get(
            "institutionalSurvivabilityScore"
        ),
        "failureRiskScore": profile.get("failureRiskScore"),
        "timeframeProfile": profile.get("timeframeProfile"),
        "timeframeExpectancyType": profile.get("timeframeExpectancyType"),
        "dailyContinuationState": profile.get("dailyContinuationState"),
        "trajectoryState": profile.get("trajectoryState"),
        "finalHierarchyState": profile.get("finalHierarchyState"),
        "survivabilityBias": profile.get("survivabilityBias"),
    }


def main() -> None:
    print("=================================")
    print("🧠 BUILD TIMEFRAME EXPECTANCY PROFILE")
    print("=================================")

    if not os.path.exists(INPUT_DIR):
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(glob(os.path.join(INPUT_DIR, "*.json")))
    files = [f for f in files if not os.path.basename(f).startswith("_")]

    if not files:
        raise FileNotFoundError(f"No survivability json files found: {INPUT_DIR}")

    results = []

    for path in files:
        results.append(process_symbol_file(path))

    save_json(LATEST_OUTPUT_PATH, results)

    df = pd.DataFrame(results)
    ok_df = df[df["status"] == "OK"].copy()

    summary = {
        "totalFiles": len(results),
        "okFiles": len(ok_df),
        "profileDistribution": (
            ok_df["timeframeProfile"].value_counts(dropna=False).to_dict()
            if not ok_df.empty and "timeframeProfile" in ok_df.columns
            else {}
        ),
    }

    save_json(SUMMARY_OUTPUT_PATH, [summary])

    print(f"okFiles: {len(ok_df):,}")
    print(f"saved: {LATEST_OUTPUT_PATH}")
    print(f"summary: {SUMMARY_OUTPUT_PATH}")

    if ok_df.empty:
        print("NO OK RESULT")
        return

    for col in [
        "tacticalBurstScore",
        "swingContinuationScore",
        "institutionalSurvivabilityScore",
        "failureRiskScore",
    ]:
        ok_df[col] = pd.to_numeric(ok_df[col], errors="coerce")

    print("")
    print("=================================")
    print("📊 PROFILE DISTRIBUTION")
    print("=================================")
    print(ok_df["timeframeProfile"].value_counts(dropna=False).to_string())

    display_cols = [
        "symbol",
        "latestDate",
        "timeframeProfile",
        "tacticalBurstScore",
        "swingContinuationScore",
        "institutionalSurvivabilityScore",
        "failureRiskScore",
        "continuationSurvivabilityScore",
        "dailyContinuationState",
        "trajectoryState",
        "finalHierarchyState",
    ]

    print("")
    print("=================================")
    print("🔥 TOP TACTICAL BURST")
    print("=================================")
    print(
        ok_df.sort_values("tacticalBurstScore", ascending=False)[display_cols]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("🧭 TOP SWING CONTINUATION")
    print("=================================")
    print(
        ok_df.sort_values("swingContinuationScore", ascending=False)[display_cols]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("🏦 TOP INSTITUTIONAL SURVIVABILITY")
    print("=================================")
    print(
        ok_df.sort_values("institutionalSurvivabilityScore", ascending=False)[
            display_cols
        ]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("🧨 TOP FAILURE RISK")
    print("=================================")
    print(
        ok_df.sort_values("failureRiskScore", ascending=False)[display_cols]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("=================================")
    print("✅ DONE")
    print("=================================")


if __name__ == "__main__":
    main()
