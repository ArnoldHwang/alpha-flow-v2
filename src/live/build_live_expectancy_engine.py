# src/live/build_live_expectancy_engine.py

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MATRIX_PATH = ROOT / "data" / "research" / "state_expectancy_matrix.json"


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


def load_state_expectancy_matrix():
    if not MATRIX_PATH.exists():
        print(f"⚠️ missing expectancy matrix: {MATRIX_PATH}")
        return {}

    with open(MATRIX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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


def attach_live_expectancy_to_row(row, matrix):
    """
    live row에 historical expectancy를 붙인다.

    핵심:
    continuationArchetype + finalHierarchyState 조합으로 lookup한다.

    continuationArchetype = 현재 continuation subtype
    finalHierarchyState = monthly/weekly/daily 계층 상태
    """

    archetype = safe_str(row.get("continuationArchetype"))
    hierarchy = safe_str(
        row.get("finalHierarchyState")
        or row.get("confirmedHierarchyState")
        or row.get("hierarchy")
    )

    matrix_item = matrix.get(archetype, {}).get(hierarchy)

    expectancy_payload = build_expectancy_payload(matrix_item)

    new_row = dict(row)
    new_row.update(expectancy_payload)

    return new_row


def attach_live_expectancy(rows):
    """
    rows: list[dict]

    live decision board 생성 전/후 어디서든 사용 가능.
    """

    matrix = load_state_expectancy_matrix()

    if not rows:
        return []

    return [attach_live_expectancy_to_row(row, matrix) for row in rows]
