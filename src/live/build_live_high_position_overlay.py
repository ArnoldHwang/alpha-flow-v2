# src/live/build_live_high_position_overlay.py

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HIGH_POSITION_PATH = ROOT / "data" / "research" / "high_position_quality.csv"

DEFAULT_HIGH_POSITION = {
    "highPositionQuality": "NO_HIGH_POSITION_DATA",
    "positionInterpretation": "고점 품질 데이터가 아직 연결되지 않았다.",
    "positionActionGuide": "고점 품질 판단 전까지는 기존 점수와 실시간 흐름을 우선 확인",
    "highPositionMatched": False,
}


def safe_str(value, default="UNKNOWN"):
    if value is None:
        return default

    value = str(value).strip()
    return value if value else default


def normalize_key(value):
    return safe_str(value).upper()


def load_high_position_rows():
    if not HIGH_POSITION_PATH.exists():
        print(f"⚠️ missing high position quality: {HIGH_POSITION_PATH}")
        return []

    with open(HIGH_POSITION_PATH, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_high_position_index(rows):
    """
    high_position_quality.csv를 live row lookup용 index로 변환한다.

    우선순위:
    1. finalHierarchyState + trajectoryState
    2. dailyContinuationState + trajectoryState
    3. trajectoryState 단독 fallback
    """

    index = {
        "hierarchy_trajectory": {},
        "daily_trajectory": {},
        "trajectory": {},
    }

    for row in rows:
        analysis_type = safe_str(row.get("analysisType"))

        trajectory = normalize_key(row.get("trajectoryState"))
        hierarchy = normalize_key(row.get("finalHierarchyState"))
        daily_state = normalize_key(row.get("dailyContinuationState"))

        if analysis_type == "hierarchy_trajectory_combo":
            index["hierarchy_trajectory"][(hierarchy, trajectory)] = row

        elif analysis_type == "daily_trajectory_combo":
            index["daily_trajectory"][(daily_state, trajectory)] = row

        elif analysis_type == "trajectory":
            index["trajectory"][trajectory] = row

    return index


def build_high_position_payload(item):
    if not item:
        return dict(DEFAULT_HIGH_POSITION)

    return {
        "highPositionQuality": safe_str(item.get("highPositionQuality")),
        "positionInterpretation": safe_str(item.get("positionInterpretation")),
        "positionActionGuide": safe_str(item.get("positionActionGuide")),
        "highPositionMatched": True,
    }


def find_high_position_item(row, index):
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

    item = index["hierarchy_trajectory"].get((hierarchy, trajectory))
    if item:
        return item

    item = index["daily_trajectory"].get((daily_state, trajectory))
    if item:
        return item

    item = index["trajectory"].get(trajectory)
    if item:
        return item

    return None


def attach_high_position_quality(rows):
    """
    live rows에 좋은 고점 / 위험한 고점 판단을 붙인다.

    highPositionQuality:
    - GOOD_HIGH_POSITION
    - HEALTHY_HIGH_POSITION_BUT_ENTRY_RISK
    - MIXED_HIGH_POSITION
    - HIGH_POSITION_DISTRIBUTION_RISK
    - BAD_HIGH_POSITION
    - LOW_SAMPLE_RESEARCH_ONLY
    """

    if not rows:
        return []

    high_rows = load_high_position_rows()
    index = build_high_position_index(high_rows)

    output = []

    for row in rows:
        item = find_high_position_item(row, index)
        payload = build_high_position_payload(item)

        new_row = dict(row)
        new_row.update(payload)
        output.append(new_row)

    return output
