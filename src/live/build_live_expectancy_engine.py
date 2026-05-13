# src/live/build_live_expectancy_engine.py

import json
from pathlib import Path

from src.live.build_live_high_position_overlay import attach_high_position_quality

ROOT = Path(__file__).resolve().parents[2]

MATRIX_PATH = ROOT / "data" / "research" / "state_expectancy_matrix.json"
CURVE_CLUSTER_PATH = ROOT / "data" / "research" / "expectancy_curve_clusters.json"


DEFAULT_EXPECTANCY = {
    "bestHorizon": "UNKNOWN",
    "expectancyScore": 0.0,
    "expectancyGrade": "UNKNOWN_EXPECTANCY",
    "operatingMode": "NO_EXPECTANCY_DATA",
    "sampleQuality": "NO_SAMPLE",
    "historicalWinRate3d": 0.0,
    "historicalWinRate5d": 0.0,
    "historicalWinRate10d": 0.0,
    "historicalWinRate20d": 0.0,
    "historicalWinRate60d": 0.0,
    "historicalSurvivalRate10d": 0.0,
    "historicalSurvivalRate20d": 0.0,
    "historicalSurvivalRate60d": 0.0,
    "historicalAvgReturn5d": 0.0,
    "historicalAvgReturn10d": 0.0,
    "historicalAvgReturn20d": 0.0,
    "historicalAvgReturn60d": 0.0,
    "historicalRewardRisk10d": 0.0,
    "expectancyMatched": False,
}

DEFAULT_CURVE = {
    "expectancyCurveCluster": "UNKNOWN_CURVE",
    "preferredAction": "NO_CURVE_DATA",
    "swingGrade": "UNKNOWN_SWING",
    "bestSwingWindow": "UNKNOWN",
    "swingScore_3d_20d": 0.0,
    "burstScore_1d_5d": 0.0,
    "longSurvivabilityScore_30d_60d": 0.0,
    "collapseRisk_20d_60d": 0.0,
    "curveStrengthScore": 0.0,
    "swingAvgReturn_3d_20d": 0.0,
    "swingAvgWinRate_3d_20d": 0.0,
    "curveMatched": False,
}


def safe_str(value, default="UNKNOWN"):
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return round(float(value), 4)
    except Exception:
        return default


def load_json(path, missing_message):
    if not path.exists():
        print(f"⚠️ {missing_message}: {path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state_expectancy_matrix():
    data = load_json(MATRIX_PATH, "missing expectancy matrix")
    return data if isinstance(data, dict) else {}


def load_curve_clusters():
    data = load_json(CURVE_CLUSTER_PATH, "missing expectancy curve clusters")
    return data if isinstance(data, list) else []


def build_expectancy_payload(matrix_item):
    if not matrix_item:
        return dict(DEFAULT_EXPECTANCY)

    return {
        "bestHorizon": safe_str(matrix_item.get("bestHorizon")),
        "expectancyScore": safe_float(matrix_item.get("expectancyScore")),
        "expectancyGrade": safe_str(matrix_item.get("expectancyGrade")),
        "operatingMode": safe_str(matrix_item.get("operatingMode")),
        "sampleQuality": safe_str(matrix_item.get("sampleQuality")),
        "historicalWinRate3d": safe_float(matrix_item.get("winRate_3d")),
        "historicalWinRate5d": safe_float(matrix_item.get("winRate_5d")),
        "historicalWinRate10d": safe_float(matrix_item.get("winRate_10d")),
        "historicalWinRate20d": safe_float(matrix_item.get("winRate_20d")),
        "historicalWinRate60d": safe_float(matrix_item.get("winRate_60d")),
        "historicalSurvivalRate10d": safe_float(matrix_item.get("survivalRate_10d")),
        "historicalSurvivalRate20d": safe_float(matrix_item.get("survivalRate_20d")),
        "historicalSurvivalRate60d": safe_float(matrix_item.get("survivalRate_60d")),
        "historicalAvgReturn5d": safe_float(matrix_item.get("avgReturn_5d")),
        "historicalAvgReturn10d": safe_float(matrix_item.get("avgReturn_10d")),
        "historicalAvgReturn20d": safe_float(matrix_item.get("avgReturn_20d")),
        "historicalAvgReturn60d": safe_float(matrix_item.get("avgReturn_60d")),
        "historicalRewardRisk10d": safe_float(matrix_item.get("rewardRisk_10d")),
        "expectancyMatched": True,
    }


def build_curve_payload(curve_item):
    if not curve_item:
        return dict(DEFAULT_CURVE)

    return {
        "expectancyCurveCluster": safe_str(curve_item.get("expectancyCurveCluster")),
        "preferredAction": safe_str(curve_item.get("preferredAction")),
        "swingGrade": safe_str(curve_item.get("swingGrade")),
        "bestSwingWindow": safe_str(curve_item.get("bestSwingWindow")),
        "swingScore_3d_20d": safe_float(curve_item.get("swingScore_3d_20d")),
        "burstScore_1d_5d": safe_float(curve_item.get("burstScore_1d_5d")),
        "longSurvivabilityScore_30d_60d": safe_float(
            curve_item.get("longSurvivabilityScore_30d_60d")
        ),
        "collapseRisk_20d_60d": safe_float(curve_item.get("collapseRisk_20d_60d")),
        "curveStrengthScore": safe_float(curve_item.get("curveStrengthScore")),
        "swingAvgReturn_3d_20d": safe_float(curve_item.get("swingAvgReturn_3d_20d")),
        "swingAvgWinRate_3d_20d": safe_float(curve_item.get("swingAvgWinRate_3d_20d")),
        "curveMatched": True,
    }


def normalize_key(value):
    return safe_str(value).upper()


def build_curve_index(curve_rows):
    index = {
        "hierarchy_trajectory": {},
        "daily_trajectory": {},
        "trajectory": {},
    }

    for item in curve_rows:
        analysis_type = safe_str(item.get("analysisType"))

        trajectory = normalize_key(item.get("trajectoryState"))
        hierarchy = normalize_key(item.get("finalHierarchyState"))
        daily_state = normalize_key(item.get("dailyContinuationState"))

        if analysis_type == "hierarchy_trajectory_combo":
            index["hierarchy_trajectory"][(hierarchy, trajectory)] = item

        elif analysis_type == "daily_trajectory_combo":
            index["daily_trajectory"][(daily_state, trajectory)] = item

        elif analysis_type == "trajectory":
            index["trajectory"][trajectory] = item

    return index


def find_matrix_item(row, matrix):
    archetype = safe_str(row.get("continuationArchetype"))

    hierarchy = safe_str(
        row.get("finalHierarchyState")
        or row.get("confirmedHierarchyState")
        or row.get("hierarchy")
    )

    trajectory = safe_str(row.get("trajectoryState") or row.get("trajectory"))

    regime = safe_str(
        row.get("marketRegime") or row.get("regimeState") or row.get("marketState")
    )

    survivability = safe_str(
        row.get("survivabilityBias") or row.get("survivabilityState") or row.get("bias")
    )

    level1 = matrix.get(archetype, {})
    level2 = level1.get(hierarchy, {})

    if isinstance(level2, dict):
        level3 = level2.get(trajectory) or level2.get("UNKNOWN")

        if isinstance(level3, dict):
            level4 = level3.get(regime) or level3.get("UNKNOWN")

            if isinstance(level4, dict):
                item = level4.get(survivability) or level4.get("UNKNOWN")

                if isinstance(item, dict) and "bestHorizon" in item:
                    return item

        if "bestHorizon" in level2:
            return level2

    return None


def find_curve_item(row, curve_index):
    trajectory = normalize_key(row.get("trajectoryState") or row.get("trajectory"))

    hierarchy = normalize_key(
        row.get("finalHierarchyState")
        or row.get("confirmedHierarchyState")
        or row.get("hierarchy")
    )

    daily_state = normalize_key(
        row.get("dailyContinuationState")
        or row.get("confirmedDailyState")
        or row.get("dailyState")
    )

    item = curve_index["hierarchy_trajectory"].get((hierarchy, trajectory))
    if item:
        return item

    item = curve_index["daily_trajectory"].get((daily_state, trajectory))
    if item:
        return item

    item = curve_index["trajectory"].get(trajectory)
    if item:
        return item

    return None


def attach_live_expectancy_to_row(row, matrix, curve_index):
    matrix_item = find_matrix_item(row, matrix)
    curve_item = find_curve_item(row, curve_index)

    expectancy_payload = build_expectancy_payload(matrix_item)
    curve_payload = build_curve_payload(curve_item)

    new_row = dict(row)
    new_row.update(expectancy_payload)
    new_row.update(curve_payload)

    return new_row


def attach_live_expectancy(rows):
    """
    live decision board 생성 전 live row에 아래 3가지를 붙인다.

    1. state expectancy
    2. swing expectancy curve
    3. high position quality
    """

    matrix = load_state_expectancy_matrix()
    curve_rows = load_curve_clusters()
    curve_index = build_curve_index(curve_rows)

    if not rows:
        return []

    enriched = [attach_live_expectancy_to_row(row, matrix, curve_index) for row in rows]

    enriched = attach_high_position_quality(enriched)

    return enriched
