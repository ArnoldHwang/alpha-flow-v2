# src/research/analyze_high_position_quality.py

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "data" / "research" / "expectancy_curve_clusters.csv"

OUT_DIR = ROOT / "data" / "research"
OUT_CSV = OUT_DIR / "high_position_quality.csv"
OUT_JSON = OUT_DIR / "high_position_quality.json"

MIN_OK_ROWS = 30


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_str(value, default="UNKNOWN"):
    try:
        if pd.isna(value):
            return default
        value = str(value).strip()
        return value if value else default
    except Exception:
        return default


def is_high_position(row):
    hierarchy = safe_str(row.get("finalHierarchyState"))
    daily = safe_str(row.get("dailyContinuationState"))
    curve = safe_str(row.get("expectancyCurveCluster"))

    high_words = [
        "TERMINAL",
        "LATE_STAGE",
        "MONTHLY_EXTENDED",
        "AGING",
        "ELITE_CONTINUATION",
    ]

    text = f"{hierarchy} {daily} {curve}"

    return any(w in text for w in high_words)


def classify_high_position_quality(row):
    rows = safe_float(row.get("rows"))

    if rows < MIN_OK_ROWS:
        return "LOW_SAMPLE_RESEARCH_ONLY"

    hierarchy = safe_str(row.get("finalHierarchyState"))
    trajectory = safe_str(row.get("trajectoryState"))
    daily = safe_str(row.get("dailyContinuationState"))
    curve = safe_str(row.get("expectancyCurveCluster"))
    action = safe_str(row.get("preferredAction"))
    swing_grade = safe_str(row.get("swingGrade"))

    win20 = safe_float(row.get("winRate_20d"))
    ret20 = safe_float(row.get("avgReturn_20d"))
    win60 = safe_float(row.get("winRate_60d"))
    ret60 = safe_float(row.get("avgReturn_60d"))

    swing_score = safe_float(row.get("swingScore_3d_20d"))
    collapse = safe_float(row.get("collapseRisk_20d_60d"))
    decay = safe_float(row.get("decay_20d_to_60d"))

    good_score = 0
    bad_score = 0

    if trajectory in [
        "RECOVERY_TRAJECTORY",
        "STABLE_CONTINUATION",
        "ACCELERATING_TRAJECTORY",
    ]:
        good_score += 2

    if trajectory in ["DISTRIBUTION_TRAJECTORY", "BREAKDOWN_PERSISTENCE"]:
        bad_score += 2

    if curve in [
        "INSTITUTIONAL_DRIFT_CONTINUATION",
        "HIGH_QUALITY_SWING_CONTINUATION",
        "IGNITION_TO_SWING_CONTINUATION",
        "MIDTERM_SWING_EXPANSION",
        "SLOW_COMPOUNDING_CONTINUATION",
    ]:
        good_score += 3

    if curve in [
        "BURST_AND_FADE",
        "TACTICAL_SWING_THEN_DECAY",
        "WEAK_OR_NEGATIVE_CURVE",
    ]:
        bad_score += 3

    if action in [
        "PRIMARY_SWING_CANDIDATE",
        "SLOW_SWING_OR_HOLD_WITH_TRAIL",
        "SHORT_SWING_FAST_PROFIT",
    ]:
        good_score += 2

    if action in ["AVOID", "RESEARCH_ONLY"]:
        bad_score += 2

    if swing_grade in ["ELITE_SWING_EXPECTANCY", "HIGH_SWING_EXPECTANCY"]:
        good_score += 2

    if swing_grade in ["WEAK_SWING_EXPECTANCY", "LOW_SAMPLE_RESEARCH_ONLY"]:
        bad_score += 2

    if win20 >= 55 and ret20 >= 4:
        good_score += 2

    if win60 >= 55 and ret60 >= 8:
        good_score += 2

    if collapse >= 15:
        bad_score += 2

    if decay >= 8:
        bad_score += 2

    if "TERMINAL" in hierarchy and collapse >= 10:
        bad_score += 2

    if "TERMINAL" in hierarchy and ret20 >= 8 and collapse < 8:
        good_score += 1

    if "MONTHLY_EXTENDED" in hierarchy and trajectory == "RECOVERY_TRAJECTORY":
        good_score += 1

    if "DISTRIBUTION" in daily:
        bad_score += 1

    if good_score >= bad_score + 4:
        return "GOOD_HIGH_POSITION"

    if good_score >= bad_score + 2:
        return "HEALTHY_HIGH_POSITION_BUT_ENTRY_RISK"

    if bad_score >= good_score + 4:
        return "BAD_HIGH_POSITION"

    if bad_score >= good_score + 2:
        return "HIGH_POSITION_DISTRIBUTION_RISK"

    return "MIXED_HIGH_POSITION"


def position_interpretation(q):
    if q == "GOOD_HIGH_POSITION":
        return "고점권이지만 상승 지속 품질이 좋다. 강한 종목이 더 가는 구조일 수 있다."

    if q == "HEALTHY_HIGH_POSITION_BUT_ENTRY_RISK":
        return "구조는 좋지만 현재 위치 부담이 있다. 추격보다 눌림 후 재가속 확인이 유리하다."

    if q == "BAD_HIGH_POSITION":
        return "고점권에서 힘이 약해지는 위험 구조다. 추격 매수는 피하는 쪽이 안전하다."

    if q == "HIGH_POSITION_DISTRIBUTION_RISK":
        return "고점권에서 매물/분산 위험이 있다. 짧게 보거나 보류가 맞다."

    if q == "LOW_SAMPLE_RESEARCH_ONLY":
        return "과거 사례가 부족하다. 실전 판단보다 연구용으로만 본다."

    return "좋은 요소와 위험 요소가 섞인 고점권 구조다. 추가 확인이 필요하다."


def action_guide(q):
    if q == "GOOD_HIGH_POSITION":
        return "눌림이 얕고 장중 재가속이 확인되면 스윙 후보로 유지"

    if q == "HEALTHY_HIGH_POSITION_BUT_ENTRY_RISK":
        return "즉시 추격보다 3~5일 눌림 후 재가속 확인"

    if q == "BAD_HIGH_POSITION":
        return "추격 금지. 실패 압력 감소 전까지 보류"

    if q == "HIGH_POSITION_DISTRIBUTION_RISK":
        return "짧은 tactical 대응만 가능. 손절/익절 기준 엄격히 필요"

    if q == "LOW_SAMPLE_RESEARCH_ONLY":
        return "실전 후보보다 관찰/연구용"

    return "보류 또는 소량 관찰. 다음 봉 확인 필요"


def main():
    print("=================================")
    print("🧠 ANALYZE HIGH POSITION QUALITY")
    print("=================================")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"missing input: {INPUT_PATH}\n"
            "run: python src/research/cluster_expectancy_curves.py"
        )

    df = pd.read_csv(INPUT_PATH)

    if df.empty:
        raise RuntimeError("empty input")

    high_df = df[df.apply(is_high_position, axis=1)].copy()

    if high_df.empty:
        raise RuntimeError("no high position rows found")

    high_df["highPositionQuality"] = high_df.apply(
        classify_high_position_quality, axis=1
    )
    high_df["positionInterpretation"] = high_df["highPositionQuality"].map(
        position_interpretation
    )
    high_df["positionActionGuide"] = high_df["highPositionQuality"].map(action_guide)

    rank = {
        "GOOD_HIGH_POSITION": 1,
        "HEALTHY_HIGH_POSITION_BUT_ENTRY_RISK": 2,
        "MIXED_HIGH_POSITION": 3,
        "HIGH_POSITION_DISTRIBUTION_RISK": 4,
        "BAD_HIGH_POSITION": 5,
        "LOW_SAMPLE_RESEARCH_ONLY": 6,
    }

    high_df["qualityRank"] = high_df["highPositionQuality"].map(rank).fillna(99)

    sort_cols = [
        "qualityRank",
        "curveStrengthScore",
        "swingScore_3d_20d",
        "rows",
    ]

    sort_cols = [c for c in sort_cols if c in high_df.columns]

    high_df = high_df.sort_values(
        by=sort_cols,
        ascending=[True, False, False, False][: len(sort_cols)],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    high_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(high_df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    print("")
    print("QUALITY DISTRIBUTION:")
    print(high_df["highPositionQuality"].value_counts(dropna=False).to_string())

    print("")
    print("TOP HIGH POSITION QUALITY:")
    show_cols = [
        "sourceFile",
        "analysisType",
        "trajectoryState",
        "finalHierarchyState",
        "dailyContinuationState",
        "rows",
        "expectancyCurveCluster",
        "preferredAction",
        "swingGrade",
        "bestSwingWindow",
        "curveStrengthScore",
        "swingScore_3d_20d",
        "collapseRisk_20d_60d",
        "decay_20d_to_60d",
        "highPositionQuality",
        "positionInterpretation",
        "positionActionGuide",
    ]

    show_cols = [c for c in show_cols if c in high_df.columns]
    print(high_df[show_cols].head(40).to_string(index=False))

    print("")
    print("✅ SAVED")
    print(OUT_CSV)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
