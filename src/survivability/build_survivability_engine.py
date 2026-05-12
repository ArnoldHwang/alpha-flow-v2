# src/survivability/build_survivability_engine.py

import json
import os
from glob import glob
from typing import Any, Dict, List, Optional

import pandas as pd

# =====================================
# CONFIG
# =====================================

INPUT_DIR = "data/transition_paths"
RESEARCH_DIR = "results/research"
OUTPUT_DIR = "data/survivability"

EXPECTANCY_PATH = os.path.join(RESEARCH_DIR, "transition_expectancy_all.csv")
TRANSITION_MATRIX_PATH = os.path.join(RESEARCH_DIR, "state_transition_matrix_all.csv")

OUTPUT_SUMMARY_PATH = os.path.join(OUTPUT_DIR, "_survivability_summary.json")

HORIZON_FOR_SCORE = 20

MIN_EXPECTANCY_ROWS = 30
MIN_TRANSITION_TOTAL = 100


# =====================================
# LOAD UTILS
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


def save_json_records(path: str, records: List[Dict[str, Any]]) -> None:
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


# =====================================
# LOAD RESEARCH TABLES
# =====================================


def load_expectancy_table() -> pd.DataFrame:
    if not os.path.exists(EXPECTANCY_PATH):
        raise FileNotFoundError(
            f"expectancy file not found: {EXPECTANCY_PATH}\n"
            "먼저 실행 필요: python src/research/analyze_transition_expectancy.py"
        )

    df = pd.read_csv(EXPECTANCY_PATH)

    required = ["pathColumn", "path", "rows"]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"expectancy table missing column: {col}")

    return df


def load_transition_matrix() -> pd.DataFrame:
    if not os.path.exists(TRANSITION_MATRIX_PATH):
        raise FileNotFoundError(
            f"transition matrix file not found: {TRANSITION_MATRIX_PATH}\n"
            "먼저 실행 필요: python src/research/build_state_transition_matrix.py"
        )

    df = pd.read_csv(TRANSITION_MATRIX_PATH)

    required = [
        "stateColumn",
        "forwardStep",
        "currentState",
        "nextState",
        "count",
        "total",
        "probability",
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"transition matrix missing column: {col}")

    return df


def build_expectancy_lookup(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}

    for _, row in df.iterrows():
        path_col = safe_state(row.get("pathColumn"))
        path = safe_state(row.get("path"))

        key = f"{path_col}::{path}"

        lookup[key] = row.to_dict()

    return lookup


def build_transition_lookup(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    currentState 기준으로 가장 확률 높은 nextState와 persistence probability 저장.
    """
    lookup: Dict[str, Dict[str, Any]] = {}

    filtered = df[
        (pd.to_numeric(df["forwardStep"], errors="coerce") == 5)
        & (pd.to_numeric(df["total"], errors="coerce") >= MIN_TRANSITION_TOTAL)
    ].copy()

    if filtered.empty:
        return lookup

    filtered["probability"] = pd.to_numeric(
        filtered["probability"],
        errors="coerce",
    ).fillna(0)

    for (state_col, current_state), group in filtered.groupby(
        ["stateColumn", "currentState"]
    ):
        group = group.sort_values("probability", ascending=False)

        top = group.iloc[0].to_dict()

        same_state = group[group["nextState"] == current_state]

        persistence_probability = 0.0

        if not same_state.empty:
            persistence_probability = safe_float(
                same_state.iloc[0].get("probability"),
                0,
            )

        key = f"{state_col}::{current_state}"

        lookup[key] = {
            "topNextState": safe_state(top.get("nextState")),
            "topTransitionProbability": safe_float(top.get("probability"), 0),
            "persistenceProbability": persistence_probability,
            "transitionTotal": int(safe_float(top.get("total"), 0)),
        }

    return lookup


# =====================================
# SCORE LOGIC
# =====================================


def get_expectancy(
    lookup: Dict[str, Dict[str, Any]],
    path_col: str,
    path: Any,
) -> Dict[str, Any]:
    key = f"{path_col}::{safe_state(path)}"
    return lookup.get(key, {})


def get_transition(
    lookup: Dict[str, Dict[str, Any]],
    state_col: str,
    state_value: Any,
) -> Dict[str, Any]:
    key = f"{state_col}::{safe_state(state_value)}"
    return lookup.get(key, {})


def normalize_score(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0

    score = (value - low) / (high - low) * 100
    return max(0.0, min(100.0, score))


def calc_expectancy_component(row: Dict[str, Any]) -> float:
    """
    path expectancy 기반 점수.
    20d 기대값 중심, 60d survivability 보조.
    """
    avg20 = safe_float(row.get("avgReturn_20d"), 0)
    win20 = safe_float(row.get("winRate_20d"), 50)
    avg60 = safe_float(row.get("avgReturn_60d"), 0)
    rows = safe_float(row.get("rows"), 0)

    avg20_score = normalize_score(avg20, -5, 15)
    win20_score = normalize_score(win20, 45, 70)
    avg60_score = normalize_score(avg60, -5, 25)

    sample_penalty = 1.0

    if rows < MIN_EXPECTANCY_ROWS:
        sample_penalty = 0.4
    elif rows < 50:
        sample_penalty = 0.7
    elif rows < 100:
        sample_penalty = 0.85

    return round(
        (avg20_score * 0.45 + win20_score * 0.35 + avg60_score * 0.20) * sample_penalty,
        2,
    )


def calc_transition_component(transition: Dict[str, Any]) -> float:
    """
    상태 persistence / 안정성 기반 점수.
    """
    persistence = safe_float(transition.get("persistenceProbability"), 0)
    top_prob = safe_float(transition.get("topTransitionProbability"), 0)

    persistence_score = normalize_score(persistence, 10, 70)
    top_score = normalize_score(top_prob, 20, 80)

    return round(
        persistence_score * 0.65 + top_score * 0.35,
        2,
    )


def calc_state_bias_component(row: Dict[str, Any]) -> float:
    """
    상태 자체의 방향성 보정.
    이름 기반 하드코딩이지만, 연구용 초기 압축 점수로만 사용.
    """
    daily_state = safe_state(row.get("dailyContinuationState"))
    trajectory = safe_state(row.get("trajectoryState"))
    hierarchy = safe_state(row.get("finalHierarchyState"))
    bias = safe_state(row.get("survivabilityBias"))

    score = 50.0

    # Daily state
    if daily_state in [
        "HEALTHY_CONTINUATION",
        "RE_ACCELERATING_CONTINUATION",
        "LATE_STAGE_CONTINUATION",
    ]:
        score += 12

    if daily_state in [
        "SOFT_PULLBACK",
        "HEALTHY_RESET",
        "BASE_BUILDING",
        "PAUSE_OR_PULLBACK",
    ]:
        score += 6

    if daily_state in [
        "REAL_BREAKDOWN",
        "PANIC_SELLING",
    ]:
        score -= 8

    if daily_state == "TERMINAL_RISK":
        score -= 5

    # Trajectory
    if trajectory == "RECOVERY_TRAJECTORY":
        score += 10

    if trajectory == "ACCELERATING_TRAJECTORY":
        score += 8

    if trajectory == "STABLE_CONTINUATION":
        score += 7

    if trajectory == "DISTRIBUTION_TRAJECTORY":
        score -= 5

    if trajectory == "BREAKDOWN_PERSISTENCE":
        score -= 8

    if trajectory == "VOLATILE_CHOP":
        score -= 15

    # Hierarchy
    if hierarchy == "AGING_CONTINUATION_STRUCTURE":
        score += 10

    if hierarchy == "HEALTHY_BUT_MONTHLY_EXTENDED":
        score += 7

    if hierarchy == "LATE_STAGE_REACCELERATION":
        score += 5

    if hierarchy == "ELITE_CONTINUATION_STRUCTURE":
        score += 2

    if hierarchy == "TERMINAL_STRUCTURE_RISK":
        score -= 3

    # Existing bias
    if bias == "HIGH":
        score += 8

    if bias == "GOOD":
        score += 6

    if bias == "GOOD_BUT_EXTENSION_RISK":
        score += 3

    if bias == "CAUTION":
        score -= 2

    if bias == "TACTICAL_ONLY":
        score -= 4

    if bias == "AVOID":
        score -= 8

    return round(max(0, min(100, score)), 2)


def classify_survivability(score: float, failure_risk: float) -> str:
    if score >= 75 and failure_risk <= 35:
        return "HIGH_SURVIVABILITY"

    if score >= 62 and failure_risk <= 45:
        return "GOOD_SURVIVABILITY"

    if score >= 50 and failure_risk <= 60:
        return "TACTICAL_SURVIVABILITY"

    if failure_risk >= 70:
        return "HIGH_FAILURE_RISK"

    return "LOW_SURVIVABILITY"


def classify_timeframe_expectancy(row: Dict[str, Any]) -> str:
    avg5 = safe_float(row.get("avgReturn_5d"), 0)
    avg20 = safe_float(row.get("avgReturn_20d"), 0)
    avg60 = safe_float(row.get("avgReturn_60d"), 0)

    if avg5 >= 4 and avg20 >= 6:
        return "TACTICAL_BURST_EXPECTANCY"

    if avg20 >= 6 and avg60 >= 10:
        return "SWING_TO_MIDTERM_EXPECTANCY"

    if avg60 >= 12 and avg20 >= 2:
        return "INSTITUTIONAL_DRIFT_EXPECTANCY"

    if avg5 < 0 and avg20 < 0:
        return "NEGATIVE_EXPECTANCY"

    return "MIXED_TIMEFRAME_EXPECTANCY"


def calc_failure_risk(row: Dict[str, Any]) -> float:
    daily_state = safe_state(row.get("dailyContinuationState"))
    trajectory = safe_state(row.get("trajectoryState"))
    hierarchy = safe_state(row.get("finalHierarchyState"))
    bias = safe_state(row.get("survivabilityBias"))

    risk = 35.0

    if daily_state in ["REAL_BREAKDOWN", "PANIC_SELLING", "TERMINAL_RISK"]:
        risk += 15

    if trajectory == "BREAKDOWN_PERSISTENCE":
        risk += 20

    if trajectory == "DISTRIBUTION_TRAJECTORY":
        risk += 12

    if trajectory == "VOLATILE_CHOP":
        risk += 22

    if hierarchy == "TERMINAL_STRUCTURE_RISK":
        risk += 10

    if hierarchy == "ELITE_CONTINUATION_STRUCTURE":
        risk += 5

    if bias == "AVOID":
        risk += 12

    if bias == "TACTICAL_ONLY":
        risk += 8

    if trajectory in ["RECOVERY_TRAJECTORY", "STABLE_CONTINUATION"]:
        risk -= 8

    if hierarchy == "AGING_CONTINUATION_STRUCTURE":
        risk -= 7

    if daily_state in ["SOFT_PULLBACK", "HEALTHY_RESET", "BASE_BUILDING"]:
        risk -= 5

    return round(max(0, min(100, risk)), 2)


# =====================================
# ROW ENRICH
# =====================================


def build_survivability_for_df(
    df: pd.DataFrame,
    expectancy_lookup: Dict[str, Dict[str, Any]],
    transition_lookup: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    rows = []

    for _, source in df.iterrows():
        row = source.to_dict()

        # path expectancy 우선순위:
        # hierarchy path는 큰 국면, trajectory path는 흐름, daily path는 단기 세부상태.
        hierarchy_exp = get_expectancy(
            expectancy_lookup,
            "hierarchyStatePath3",
            row.get("hierarchyStatePath3"),
        )

        trajectory_exp = get_expectancy(
            expectancy_lookup,
            "trajectoryStatePath5",
            row.get("trajectoryStatePath5"),
        )

        daily_exp = get_expectancy(
            expectancy_lookup,
            "dailyStatePath5",
            row.get("dailyStatePath5"),
        )

        hierarchy_exp_score = calc_expectancy_component(hierarchy_exp)
        trajectory_exp_score = calc_expectancy_component(trajectory_exp)
        daily_exp_score = calc_expectancy_component(daily_exp)

        expectancy_score = round(
            hierarchy_exp_score * 0.40
            + trajectory_exp_score * 0.35
            + daily_exp_score * 0.25,
            2,
        )

        daily_transition = get_transition(
            transition_lookup,
            "dailyContinuationState",
            row.get("dailyContinuationState"),
        )

        trajectory_transition = get_transition(
            transition_lookup,
            "trajectoryState",
            row.get("trajectoryState"),
        )

        hierarchy_transition = get_transition(
            transition_lookup,
            "finalHierarchyState",
            row.get("finalHierarchyState"),
        )

        daily_transition_score = calc_transition_component(daily_transition)
        trajectory_transition_score = calc_transition_component(trajectory_transition)
        hierarchy_transition_score = calc_transition_component(hierarchy_transition)

        transition_score = round(
            daily_transition_score * 0.30
            + trajectory_transition_score * 0.35
            + hierarchy_transition_score * 0.35,
            2,
        )

        state_bias_score = calc_state_bias_component(row)
        failure_risk = calc_failure_risk(row)

        survivability_score = round(
            expectancy_score * 0.45
            + transition_score * 0.30
            + state_bias_score * 0.25
            - failure_risk * 0.10,
            2,
        )

        survivability_score = max(0, min(100, survivability_score))

        best_exp = hierarchy_exp or trajectory_exp or daily_exp

        row["expectancyScore"] = expectancy_score
        row["transitionPersistenceScore"] = transition_score
        row["stateBiasScore"] = state_bias_score
        row["continuationFailureRisk"] = failure_risk
        row["continuationSurvivabilityScore"] = survivability_score
        row["continuationSurvivabilityGrade"] = classify_survivability(
            survivability_score,
            failure_risk,
        )
        row["timeframeExpectancyType"] = classify_timeframe_expectancy(best_exp)

        row["topNextDailyState5d"] = daily_transition.get("topNextState")
        row["topNextDailyStateProbability5d"] = daily_transition.get(
            "topTransitionProbability"
        )
        row["dailyStatePersistenceProbability5d"] = daily_transition.get(
            "persistenceProbability"
        )

        row["topNextTrajectoryState5d"] = trajectory_transition.get("topNextState")
        row["topNextTrajectoryProbability5d"] = trajectory_transition.get(
            "topTransitionProbability"
        )
        row["trajectoryPersistenceProbability5d"] = trajectory_transition.get(
            "persistenceProbability"
        )

        row["topNextHierarchyState5d"] = hierarchy_transition.get("topNextState")
        row["topNextHierarchyProbability5d"] = hierarchy_transition.get(
            "topTransitionProbability"
        )
        row["hierarchyPersistenceProbability5d"] = hierarchy_transition.get(
            "persistenceProbability"
        )

        row["hierarchyPathExpectancyRows"] = hierarchy_exp.get("rows")
        row["hierarchyPathAvgReturn20d"] = hierarchy_exp.get("avgReturn_20d")
        row["hierarchyPathWinRate20d"] = hierarchy_exp.get("winRate_20d")

        row["trajectoryPathExpectancyRows"] = trajectory_exp.get("rows")
        row["trajectoryPathAvgReturn20d"] = trajectory_exp.get("avgReturn_20d")
        row["trajectoryPathWinRate20d"] = trajectory_exp.get("winRate_20d")

        row["dailyPathExpectancyRows"] = daily_exp.get("rows")
        row["dailyPathAvgReturn20d"] = daily_exp.get("avgReturn_20d")
        row["dailyPathWinRate20d"] = daily_exp.get("winRate_20d")

        rows.append(row)

    return pd.DataFrame(rows)


# =====================================
# PROCESS FILES
# =====================================


def process_symbol_file(
    input_path: str,
    output_path: str,
    expectancy_lookup: Dict[str, Dict[str, Any]],
    transition_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    records = load_json_records(input_path)

    if not records:
        return {
            "file": os.path.basename(input_path),
            "status": "SKIPPED_EMPTY",
            "rows": 0,
        }

    df = pd.DataFrame(records)

    if "date" not in df.columns:
        return {
            "file": os.path.basename(input_path),
            "status": "SKIPPED_NO_DATE",
            "rows": len(df),
        }

    if "symbol" not in df.columns:
        symbol = os.path.basename(input_path).replace(".json", "")
        df["symbol"] = symbol

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    df = df.sort_values("date").copy()

    result = build_survivability_for_df(
        df,
        expectancy_lookup,
        transition_lookup,
    )

    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )

    records_out = result.to_dict(orient="records")
    save_json_records(output_path, records_out)

    latest = result.iloc[-1].to_dict()

    return {
        "file": os.path.basename(input_path),
        "symbol": safe_state(latest.get("symbol")),
        "status": "OK",
        "rows": len(result),
        "latestDate": latest.get("date"),
        "latestSurvivabilityScore": latest.get("continuationSurvivabilityScore"),
        "latestSurvivabilityGrade": latest.get("continuationSurvivabilityGrade"),
        "latestFailureRisk": latest.get("continuationFailureRisk"),
        "latestTimeframeExpectancyType": latest.get("timeframeExpectancyType"),
    }


def main() -> None:
    print("=================================")
    print("🧠 BUILD SURVIVABILITY ENGINE")
    print("=================================")

    if not os.path.exists(INPUT_DIR):
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    expectancy_df = load_expectancy_table()
    transition_df = load_transition_matrix()

    expectancy_lookup = build_expectancy_lookup(expectancy_df)
    transition_lookup = build_transition_lookup(transition_df)

    print(f"expectancyRows: {len(expectancy_df):,}")
    print(f"transitionRows: {len(transition_df):,}")
    print(f"expectancyLookup: {len(expectancy_lookup):,}")
    print(f"transitionLookup: {len(transition_lookup):,}")

    input_files = sorted(glob(os.path.join(INPUT_DIR, "*.json")))

    input_files = [
        path for path in input_files if not os.path.basename(path).startswith("_")
    ]

    if not input_files:
        raise FileNotFoundError(f"No symbol json files found: {INPUT_DIR}")

    summaries = []

    for input_path in input_files:
        file_name = os.path.basename(input_path)
        output_path = os.path.join(OUTPUT_DIR, file_name)

        result = process_symbol_file(
            input_path,
            output_path,
            expectancy_lookup,
            transition_lookup,
        )

        summaries.append(result)

    save_json_records(OUTPUT_SUMMARY_PATH, summaries)

    summary_df = pd.DataFrame(summaries)

    ok_df = summary_df[summary_df["status"] == "OK"].copy()

    print("")
    print("=================================")
    print("✅ SURVIVABILITY SAVED")
    print("=================================")
    print(f"okFiles: {len(ok_df):,}")
    print(f"summary: {OUTPUT_SUMMARY_PATH}")

    if not ok_df.empty:
        ok_df["latestSurvivabilityScore"] = pd.to_numeric(
            ok_df["latestSurvivabilityScore"],
            errors="coerce",
        )

        top = ok_df.sort_values(
            "latestSurvivabilityScore",
            ascending=False,
        ).head(40)

        print("")
        print("=================================")
        print("🔥 LATEST TOP SURVIVABILITY")
        print("=================================")

        print(
            top[
                [
                    "symbol",
                    "latestDate",
                    "latestSurvivabilityScore",
                    "latestSurvivabilityGrade",
                    "latestFailureRisk",
                    "latestTimeframeExpectancyType",
                ]
            ].to_string(index=False)
        )

    print("")
    print("=================================")
    print("✅ DONE")
    print("=================================")


if __name__ == "__main__":
    main()
