# src/research/cluster_expectancy_curves.py

from pathlib import Path
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "data" / "research" / "expectancy_curves_swing.csv"

OUT_DIR = ROOT / "data" / "research"
OUT_CSV = OUT_DIR / "expectancy_curve_clusters.csv"
OUT_JSON = OUT_DIR / "expectancy_curve_clusters.json"

RETURN_WINDOWS = [1, 3, 5, 10, 20, 30, 60]
SWING_WINDOWS = [3, 5, 10, 20]

MIN_ROWS_OK = 30


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


def avg(values):
    values = [safe_float(v) for v in values]
    if not values:
        return 0.0
    return sum(values) / len(values)


def get(row, col):
    return safe_float(row.get(col), 0.0)


def curve_values(row, prefix):
    return [get(row, f"{prefix}_{w}d") for w in RETURN_WINDOWS]


def slope(a, b):
    return round(b - a, 4)


def classify_curve(row):
    rows = int(get(row, "rows"))

    if rows < MIN_ROWS_OK:
        return "LOW_SAMPLE_RESEARCH_ONLY"

    if safe_str(row.get("trajectoryState")) == "INSUFFICIENT_HISTORY":
        return "INSUFFICIENT_HISTORY_ISOLATED"

    r1 = get(row, "avgReturn_1d")
    r3 = get(row, "avgReturn_3d")
    r5 = get(row, "avgReturn_5d")
    r10 = get(row, "avgReturn_10d")
    r20 = get(row, "avgReturn_20d")
    r30 = get(row, "avgReturn_30d")
    r60 = get(row, "avgReturn_60d")

    w1 = get(row, "winRate_1d")
    w3 = get(row, "winRate_3d")
    w5 = get(row, "winRate_5d")
    w10 = get(row, "winRate_10d")
    w20 = get(row, "winRate_20d")
    w30 = get(row, "winRate_30d")
    w60 = get(row, "winRate_60d")

    swing_avg_return = avg([r3, r5, r10, r20])
    swing_avg_win = avg([w3, w5, w10, w20])

    burst_return = avg([r1, r3, r5])
    mid_return = avg([r10, r20])
    long_return = avg([r30, r60])

    early_to_mid = slope(burst_return, mid_return)
    mid_to_long = slope(mid_return, long_return)

    collapse_from_20_to_60 = r20 - r60
    acceleration_5_to_20 = r20 - r5

    if burst_return >= 4 and mid_return < burst_return * 0.55:
        return "BURST_AND_FADE"

    if r1 >= 1.0 and r3 >= 2.0 and r5 >= 3.0 and r10 >= 4.0:
        if r20 >= r10:
            return "IGNITION_TO_SWING_CONTINUATION"
        return "FAST_IGNITION_SHORT_SWING"

    if swing_avg_win >= 58 and swing_avg_return >= 4 and r20 >= r10:
        return "HIGH_QUALITY_SWING_CONTINUATION"

    if r5 < 2 and r20 >= 5 and r60 >= r20:
        return "SLOW_COMPOUNDING_CONTINUATION"

    if r20 >= 6 and r60 >= 10 and w60 >= 55:
        return "INSTITUTIONAL_DRIFT_CONTINUATION"

    if r20 >= 8 and collapse_from_20_to_60 >= 6:
        return "TACTICAL_SWING_THEN_DECAY"

    if r20 >= 8 and r30 >= 8 and w20 >= 55:
        return "MIDTERM_SWING_EXPANSION"

    if r1 < 0 and r3 <= 0 and r20 > 3:
        return "DELAYED_RECOVERY_CONTINUATION"

    if swing_avg_return < 0 or swing_avg_win < 48:
        return "WEAK_OR_NEGATIVE_CURVE"

    if acceleration_5_to_20 >= 3:
        return "DELAYED_SWING_ACCELERATION"

    if mid_to_long > 4:
        return "LONG_TAIL_CONTINUATION"

    return "MIXED_EXPECTANCY_CURVE"


def curve_strength(row):
    r = curve_values(row, "avgReturn")
    w = curve_values(row, "winRate")

    swing_return = avg([get(row, f"avgReturn_{x}d") for x in SWING_WINDOWS])
    swing_win = avg([get(row, f"winRate_{x}d") for x in SWING_WINDOWS])

    rr10 = get(row, "rewardRisk_10d")
    rr20 = get(row, "rewardRisk_20d")

    score = (
        swing_win * 0.42
        + swing_return * 2.70
        + avg([rr10, rr20]) * 6.00
        + max(r) * 0.70
        - max(0, r[4] - r[6]) * 0.80
    )

    return round(score, 4)


def preferred_action(row, cluster):
    if cluster in ["LOW_SAMPLE_RESEARCH_ONLY", "INSUFFICIENT_HISTORY_ISOLATED"]:
        return "RESEARCH_ONLY"

    if cluster == "BURST_AND_FADE":
        return "DAY1_TO_DAY5_ONLY"

    if cluster == "FAST_IGNITION_SHORT_SWING":
        return "SHORT_SWING_FAST_PROFIT"

    if cluster in [
        "IGNITION_TO_SWING_CONTINUATION",
        "HIGH_QUALITY_SWING_CONTINUATION",
        "MIDTERM_SWING_EXPANSION",
    ]:
        return "PRIMARY_SWING_CANDIDATE"

    if cluster in [
        "SLOW_COMPOUNDING_CONTINUATION",
        "INSTITUTIONAL_DRIFT_CONTINUATION",
        "LONG_TAIL_CONTINUATION",
    ]:
        return "SLOW_SWING_OR_HOLD_WITH_TRAIL"

    if cluster == "TACTICAL_SWING_THEN_DECAY":
        return "TACTICAL_10D_20D_EXIT_AWARE"

    if cluster == "DELAYED_RECOVERY_CONTINUATION":
        return "WATCH_FOR_CONFIRMATION"

    if cluster == "WEAK_OR_NEGATIVE_CURVE":
        return "AVOID"

    return "WATCHLIST"


def main():
    print("=================================")
    print("🧠 CLUSTER EXPECTANCY CURVES")
    print("=================================")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"missing input: {INPUT_PATH}\n"
            "run: python src/research/analyze_expectancy_curves.py"
        )

    df = pd.read_csv(INPUT_PATH)

    if df.empty:
        raise RuntimeError("empty input expectancy_curves_swing.csv")

    rows = []

    for _, row in df.iterrows():
        item = row.to_dict()

        cluster = classify_curve(row)
        strength = curve_strength(row)

        item["expectancyCurveCluster"] = cluster
        item["curveStrengthScore"] = strength
        item["preferredAction"] = preferred_action(row, cluster)

        item["swingAvgReturn_3d_20d"] = round(
            avg([get(row, f"avgReturn_{w}d") for w in SWING_WINDOWS]), 4
        )
        item["swingAvgWinRate_3d_20d"] = round(
            avg([get(row, f"winRate_{w}d") for w in SWING_WINDOWS]), 4
        )
        item["burstAvgReturn_1d_5d"] = round(
            avg([get(row, f"avgReturn_{w}d") for w in [1, 3, 5]]), 4
        )
        item["midAvgReturn_10d_20d"] = round(
            avg([get(row, f"avgReturn_{w}d") for w in [10, 20]]), 4
        )
        item["longAvgReturn_30d_60d"] = round(
            avg([get(row, f"avgReturn_{w}d") for w in [30, 60]]), 4
        )
        item["decay_20d_to_60d"] = round(
            get(row, "avgReturn_20d") - get(row, "avgReturn_60d"), 4
        )
        item["acceleration_5d_to_20d"] = round(
            get(row, "avgReturn_20d") - get(row, "avgReturn_5d"), 4
        )

        rows.append(item)

    out = pd.DataFrame(rows)

    action_rank = {
        "PRIMARY_SWING_CANDIDATE": 1,
        "SHORT_SWING_FAST_PROFIT": 2,
        "TACTICAL_10D_20D_EXIT_AWARE": 3,
        "SLOW_SWING_OR_HOLD_WITH_TRAIL": 4,
        "WATCH_FOR_CONFIRMATION": 5,
        "WATCHLIST": 6,
        "DAY1_TO_DAY5_ONLY": 7,
        "AVOID": 8,
        "RESEARCH_ONLY": 9,
    }

    out["actionRank"] = out["preferredAction"].map(action_rank).fillna(99)

    out = out.sort_values(
        by=["actionRank", "curveStrengthScore", "rows"],
        ascending=[True, False, False],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    print("")
    print("TOP CURVE CLUSTERS:")
    show_cols = [
        "sourceFile",
        "analysisType",
        "trajectoryState",
        "finalHierarchyState",
        "dailyContinuationState",
        "rows",
        "sampleQuality",
        "expectancyCurveCluster",
        "preferredAction",
        "curveStrengthScore",
        "bestSwingWindow",
        "swingGrade",
        "swingAvgWinRate_3d_20d",
        "swingAvgReturn_3d_20d",
        "burstAvgReturn_1d_5d",
        "midAvgReturn_10d_20d",
        "longAvgReturn_30d_60d",
        "decay_20d_to_60d",
        "acceleration_5d_to_20d",
    ]

    show_cols = [c for c in show_cols if c in out.columns]
    print(out[show_cols].head(50).to_string(index=False))

    print("")
    print("CLUSTER DISTRIBUTION:")
    print(out["expectancyCurveCluster"].value_counts(dropna=False).to_string())

    print("")
    print("PREFERRED ACTION DISTRIBUTION:")
    print(out["preferredAction"].value_counts(dropna=False).to_string())

    print("")
    print("✅ SAVED")
    print(OUT_CSV)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
