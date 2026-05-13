# src/research/build_state_expectancy_matrix.py

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "data" / "research" / "archetype_hierarchy_expectancy.csv"

OUT_DIR = ROOT / "data" / "research"
OUT_JSON = OUT_DIR / "state_expectancy_matrix.json"
OUT_CSV = OUT_DIR / "state_expectancy_matrix.csv"

HORIZONS = ["1d", "3d", "5d", "10d", "20d", "30d", "60d"]

MIN_ROWS_STRONG = 300
MIN_ROWS_OK = 50
MIN_ROWS_WEAK = 20


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


def first_existing(row, names, default="UNKNOWN"):
    for name in names:
        if name in row.index:
            value = safe_str(row.get(name), default=None)
            if value and value != "UNKNOWN":
                return value
    return default


def sample_quality(rows):
    if rows >= MIN_ROWS_STRONG:
        return "STRONG_SAMPLE"
    if rows >= MIN_ROWS_OK:
        return "OK_SAMPLE"
    if rows >= MIN_ROWS_WEAK:
        return "WEAK_SAMPLE"
    return "LOW_SAMPLE"


def confidence_multiplier(rows):
    if rows >= MIN_ROWS_STRONG:
        return 1.00
    if rows >= MIN_ROWS_OK:
        return 0.85
    if rows >= MIN_ROWS_WEAK:
        return 0.65
    return 0.45


def get_metric(row, metric, horizon, default=0.0):
    return safe_float(row.get(f"{metric}_{horizon}", default), default)


def get_reward_risk(row, horizon):
    direct = row.get(f"rewardRisk_{horizon}", None)
    if direct is not None and not pd.isna(direct):
        return safe_float(direct, 1.0)

    fallback = row.get("rewardRisk_10d", None)
    if fallback is not None and not pd.isna(fallback):
        return safe_float(fallback, 1.0)

    mfe = get_metric(row, "avgMFE", horizon, 0.0)
    mae = abs(get_metric(row, "avgMAE", horizon, 0.0))

    if mae <= 0:
        return 1.0

    return round(mfe / mae, 4)


def horizon_score(row, horizon):
    rows = int(safe_float(row.get("rows", 0)))

    win = get_metric(row, "winRate", horizon, 0.0)
    survival = get_metric(row, "survivalRate", horizon, 0.0)
    avg_return = get_metric(row, "avgReturn", horizon, 0.0)
    mfe = get_metric(row, "avgMFE", horizon, 0.0)
    mae = abs(get_metric(row, "avgMAE", horizon, 0.0))
    rr = get_reward_risk(row, horizon)

    confidence = confidence_multiplier(rows)

    raw_score = (
        win * 0.32
        + survival * 0.25
        + avg_return * 1.60
        + mfe * 0.45
        + rr * 4.50
        - mae * 0.35
    )

    return round(raw_score * confidence, 4)


def choose_best_horizon(row):
    scored = []

    for horizon in HORIZONS:
        has_any = (
            f"winRate_{horizon}" in row.index
            or f"avgReturn_{horizon}" in row.index
            or f"survivalRate_{horizon}" in row.index
        )

        if not has_any:
            continue

        scored.append((horizon, horizon_score(row, horizon)))

    if not scored:
        return "UNKNOWN", 0.0

    scored = sorted(scored, key=lambda x: x[1], reverse=True)
    return scored[0][0], round(scored[0][1], 4)


def classify_expectancy(row, best_horizon):
    rows = int(safe_float(row.get("rows", 0)))

    if rows < MIN_ROWS_WEAK or best_horizon == "UNKNOWN":
        return "LOW_CONFIDENCE"

    win = get_metric(row, "winRate", best_horizon, 0.0)
    survival = get_metric(row, "survivalRate", best_horizon, 0.0)
    avg_return = get_metric(row, "avgReturn", best_horizon, 0.0)
    rr = get_reward_risk(row, best_horizon)

    if rows < MIN_ROWS_OK:
        if win >= 58 and avg_return >= 6 and rr >= 1.2:
            return "PROMISING_BUT_LOW_SAMPLE"
        return "LOW_CONFIDENCE"

    if win >= 62 and avg_return >= 8 and survival >= 35 and rr >= 1.2:
        return "ELITE_EXPECTANCY"

    if win >= 58 and avg_return >= 5 and survival >= 30 and rr >= 1.05:
        return "HIGH_EXPECTANCY"

    if win >= 54 and avg_return >= 2 and rr >= 1.0:
        return "GOOD_EXPECTANCY"

    if win >= 50 and avg_return >= 0:
        return "MILD_EXPECTANCY"

    if avg_return < 0 or win < 48:
        return "NEGATIVE_EXPECTANCY"

    return "MIXED_EXPECTANCY"


def classify_operating_mode(row, best_horizon, grade):
    archetype = safe_str(row.get("continuationArchetype"))
    hierarchy = safe_str(row.get("finalHierarchyState"))
    trajectory = first_existing(
        row,
        ["trajectoryType", "trajectoryState", "trajectory"],
        default="UNKNOWN",
    )
    regime = first_existing(
        row,
        ["marketRegime", "regimeState", "marketState"],
        default="UNKNOWN",
    )

    if grade in ["LOW_CONFIDENCE"]:
        return "RESEARCH_ONLY"

    if grade == "NEGATIVE_EXPECTANCY":
        return "AVOID_OR_SHORTLIST_REVIEW"

    if "TERMINAL" in hierarchy or "TERMINAL" in archetype:
        if grade in ["ELITE_EXPECTANCY", "HIGH_EXPECTANCY"]:
            return "TACTICAL_HIGH_RISK_CONTINUATION"
        return "TERMINAL_RISK_AVOID"

    if "DISTRIBUTION" in trajectory or "DISTRIBUTION" in archetype:
        if grade in ["ELITE_EXPECTANCY", "HIGH_EXPECTANCY"]:
            return "TACTICAL_DISTRIBUTION_BOUNCE"
        return "DISTRIBUTION_RISK_REVIEW"

    if "RISK_OFF" in regime and grade not in ["ELITE_EXPECTANCY", "HIGH_EXPECTANCY"]:
        return "REGIME_CONSTRAINED_REVIEW"

    if best_horizon == "1d":
        return "ONE_DAY_BURST"

    if best_horizon in ["3d", "5d"]:
        return "SHORT_SWING_CONTINUATION"

    if best_horizon in ["10d", "20d"]:
        return "SWING_TO_MIDTERM_CONTINUATION"

    if best_horizon in ["30d", "60d"]:
        return "LONG_SURVIVABILITY_CONTINUATION"

    return "MIXED_CONTINUATION"


def build_item(row):
    archetype = safe_str(row.get("continuationArchetype"))
    hierarchy = safe_str(row.get("finalHierarchyState"))

    trajectory = first_existing(
        row,
        ["trajectoryType", "trajectoryState", "trajectory"],
        default="UNKNOWN",
    )

    regime = first_existing(
        row,
        ["marketRegime", "regimeState", "marketState"],
        default="UNKNOWN",
    )

    survivability = first_existing(
        row,
        ["survivabilityBias", "survivabilityState", "survivability"],
        default="UNKNOWN",
    )

    rows = int(safe_float(row.get("rows", 0)))

    best_horizon, best_score = choose_best_horizon(row)
    grade = classify_expectancy(row, best_horizon)
    mode = classify_operating_mode(row, best_horizon, grade)

    item = {
        "continuationArchetype": archetype,
        "finalHierarchyState": hierarchy,
        "trajectoryType": trajectory,
        "marketRegime": regime,
        "survivabilityBias": survivability,
        "rows": rows,
        "sampleQuality": sample_quality(rows),
        "confidenceMultiplier": confidence_multiplier(rows),
        "bestHorizon": best_horizon,
        "expectancyScore": best_score,
        "expectancyGrade": grade,
        "operatingMode": mode,
    }

    for horizon in HORIZONS:
        item[f"winRate_{horizon}"] = get_metric(row, "winRate", horizon, 0.0)
        item[f"survivalRate_{horizon}"] = get_metric(row, "survivalRate", horizon, 0.0)
        item[f"avgReturn_{horizon}"] = get_metric(row, "avgReturn", horizon, 0.0)
        item[f"avgMFE_{horizon}"] = get_metric(row, "avgMFE", horizon, 0.0)
        item[f"avgMAE_{horizon}"] = get_metric(row, "avgMAE", horizon, 0.0)
        item[f"rewardRisk_{horizon}"] = get_reward_risk(row, horizon)
        item[f"expectancyScore_{horizon}"] = horizon_score(row, horizon)

    return item


def nested_set(matrix, keys, item):
    current = matrix

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = item


def build_matrix():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"missing input file: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)

    required = [
        "continuationArchetype",
        "finalHierarchyState",
        "rows",
    ]

    for col in required:
        if col not in df.columns:
            raise RuntimeError(f"missing required column: {col}")

    output_rows = []
    matrix = {}

    for _, row in df.iterrows():
        item = build_item(row)

        output_rows.append(item)

        nested_set(
            matrix,
            [
                item["continuationArchetype"],
                item["finalHierarchyState"],
                item["trajectoryType"],
                item["marketRegime"],
                item["survivabilityBias"],
            ],
            item,
        )

    out_df = pd.DataFrame(output_rows)

    grade_order = {
        "ELITE_EXPECTANCY": 1,
        "HIGH_EXPECTANCY": 2,
        "GOOD_EXPECTANCY": 3,
        "MILD_EXPECTANCY": 4,
        "PROMISING_BUT_LOW_SAMPLE": 5,
        "MIXED_EXPECTANCY": 6,
        "NEGATIVE_EXPECTANCY": 7,
        "LOW_CONFIDENCE": 8,
    }

    out_df["gradeRank"] = out_df["expectancyGrade"].map(grade_order).fillna(99)

    out_df = out_df.sort_values(
        by=["gradeRank", "expectancyScore", "rows"],
        ascending=[True, False, False],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2)

    print("=================================")
    print("🧠 BUILD STATE EXPECTANCY MATRIX")
    print("=================================")
    print(f"input rows: {len(df):,}")
    print(f"output rows: {len(out_df):,}")
    print(f"matrix archetypes: {out_df['continuationArchetype'].nunique():,}")
    print("")

    print("TOP EXPECTANCY:")
    show_cols = [
        "continuationArchetype",
        "finalHierarchyState",
        "trajectoryType",
        "marketRegime",
        "survivabilityBias",
        "rows",
        "sampleQuality",
        "bestHorizon",
        "expectancyScore",
        "expectancyGrade",
        "operatingMode",
        "winRate_1d",
        "winRate_3d",
        "winRate_5d",
        "winRate_10d",
        "winRate_20d",
        "winRate_30d",
        "winRate_60d",
        "avgReturn_10d",
        "avgReturn_20d",
        "avgReturn_30d",
        "avgReturn_60d",
        "rewardRisk_10d",
    ]

    existing_show_cols = [c for c in show_cols if c in out_df.columns]

    print(out_df[existing_show_cols].head(30).to_string(index=False))

    print("")
    print("EXPECTANCY GRADE DISTRIBUTION:")
    print(out_df["expectancyGrade"].value_counts(dropna=False).to_string())

    print("")
    print("BEST HORIZON DISTRIBUTION:")
    print(out_df["bestHorizon"].value_counts(dropna=False).to_string())

    print("")
    print("✅ SAVED")
    print(OUT_CSV)
    print(OUT_JSON)


def main():
    build_matrix()


if __name__ == "__main__":
    main()
