# src/research/analyze_expectancy_curves.py

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILES = [
    ROOT / "data" / "research" / "trajectory_expectancy.csv",
    ROOT / "data" / "research" / "hierarchy_trajectory_expectancy.csv",
    ROOT / "data" / "research" / "daily_trajectory_expectancy.csv",
]

OUT_DIR = ROOT / "data" / "research"
OUT_CSV = OUT_DIR / "expectancy_curves_swing.csv"
OUT_JSON = OUT_DIR / "expectancy_curves_swing.json"

SWING_WINDOWS = [3, 5, 10, 20]
BURST_WINDOWS = [1, 3, 5]
LONG_WINDOWS = [30, 60]

MIN_OK_ROWS = 30
MIN_STRONG_ROWS = 100


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


def sample_quality(rows):
    if rows >= MIN_STRONG_ROWS:
        return "STRONG_SAMPLE"
    if rows >= MIN_OK_ROWS:
        return "OK_SAMPLE"
    return "LOW_SAMPLE"


def metric(row, name, window):
    return safe_float(row.get(f"{name}_{window}d"), 0.0)


def avg_metrics(row, name, windows):
    values = [metric(row, name, w) for w in windows]
    return round(sum(values) / len(values), 4) if values else 0.0


def reward_risk(row, window):
    pos = metric(row, "positiveAvg", window)
    neg = abs(metric(row, "negativeAvg", window))

    if neg <= 0:
        return 1.0

    return round(pos / neg, 4)


def best_window(row, windows):
    scored = []

    for w in windows:
        win = metric(row, "winRate", w)
        avg_ret = metric(row, "avgReturn", w)
        rr = reward_risk(row, w)

        score = win * 0.40 + avg_ret * 2.20 + rr * 5.00
        scored.append((w, round(score, 4)))

    scored = sorted(scored, key=lambda x: x[1], reverse=True)
    return scored[0]


def swing_score(row):
    rows = int(safe_float(row.get("rows"), 0))

    win = avg_metrics(row, "winRate", SWING_WINDOWS)
    avg_ret = avg_metrics(row, "avgReturn", SWING_WINDOWS)

    rr_values = [reward_risk(row, w) for w in SWING_WINDOWS]
    rr = sum(rr_values) / len(rr_values)

    confidence = 1.0
    if rows < MIN_OK_ROWS:
        confidence = 0.45
    elif rows < MIN_STRONG_ROWS:
        confidence = 0.75

    score = win * 0.45 + avg_ret * 2.50 + rr * 6.00

    return round(score * confidence, 4)


def burst_score(row):
    win = avg_metrics(row, "winRate", BURST_WINDOWS)
    avg_ret = avg_metrics(row, "avgReturn", BURST_WINDOWS)
    return round(win * 0.45 + avg_ret * 2.80, 4)


def long_survivability_score(row):
    win = avg_metrics(row, "winRate", LONG_WINDOWS)
    avg_ret = avg_metrics(row, "avgReturn", LONG_WINDOWS)
    return round(win * 0.35 + avg_ret * 2.00, 4)


def collapse_risk(row):
    ret_20 = metric(row, "avgReturn", 20)
    ret_60 = metric(row, "avgReturn", 60)
    win_20 = metric(row, "winRate", 20)
    win_60 = metric(row, "winRate", 60)

    risk = 0.0

    if ret_20 > 0 and ret_60 < ret_20:
        risk += (ret_20 - ret_60) * 2.0

    if win_20 > 50 and win_60 < win_20:
        risk += (win_20 - win_60) * 0.6

    if ret_60 < 0:
        risk += abs(ret_60) * 2.5

    return round(risk, 4)


def classify_swing(row, score, collapse):
    rows = int(safe_float(row.get("rows"), 0))
    best_w, _ = best_window(row, SWING_WINDOWS)

    avg_win = avg_metrics(row, "winRate", SWING_WINDOWS)
    avg_ret = avg_metrics(row, "avgReturn", SWING_WINDOWS)

    if rows < MIN_OK_ROWS:
        return "LOW_SAMPLE_RESEARCH_ONLY"

    if collapse >= 18:
        return "TACTICAL_ONLY_COLLAPSE_RISK"

    if score >= 42 and avg_win >= 58 and avg_ret >= 3:
        return "ELITE_SWING_EXPECTANCY"

    if score >= 36 and avg_win >= 55 and avg_ret >= 1.5:
        return "HIGH_SWING_EXPECTANCY"

    if score >= 31 and avg_win >= 52 and avg_ret >= 0:
        return "GOOD_SWING_EXPECTANCY"

    if best_w in [3, 5] and avg_ret > 0:
        return "SHORT_SWING_ONLY"

    if avg_ret < 0 or avg_win < 48:
        return "WEAK_SWING_EXPECTANCY"

    return "MIXED_SWING_EXPECTANCY"


def infer_group_name(row):
    parts = []

    for col in [
        "analysisType",
        "trajectoryState",
        "finalHierarchyState",
        "dailyContinuationState",
        "continuationArchetype",
    ]:
        if col in row.index:
            value = safe_str(row.get(col), "")
            if value:
                parts.append(f"{col}={value}")

    return " | ".join(parts) if parts else "UNKNOWN_GROUP"


def process_file(path):
    if not path.exists():
        print(f"⚠️ missing input skipped: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path)

    if df.empty:
        return pd.DataFrame()

    rows = []

    for _, row in df.iterrows():
        best_swing_window, best_swing_window_score = best_window(row, SWING_WINDOWS)

        s_score = swing_score(row)
        b_score = burst_score(row)
        l_score = long_survivability_score(row)
        c_risk = collapse_risk(row)

        item = {
            "sourceFile": path.name,
            "groupName": infer_group_name(row),
            "analysisType": safe_str(row.get("analysisType")),
            "rows": int(safe_float(row.get("rows"), 0)),
            "sampleQuality": sample_quality(int(safe_float(row.get("rows"), 0))),
            "bestSwingWindow": f"{best_swing_window}d",
            "bestSwingWindowScore": best_swing_window_score,
            "swingScore_3d_20d": s_score,
            "burstScore_1d_5d": b_score,
            "longSurvivabilityScore_30d_60d": l_score,
            "collapseRisk_20d_60d": c_risk,
            "swingGrade": classify_swing(row, s_score, c_risk),
        }

        for col in [
            "trajectoryState",
            "finalHierarchyState",
            "dailyContinuationState",
            "continuationArchetype",
        ]:
            if col in df.columns:
                item[col] = safe_str(row.get(col))

        for w in [1, 3, 5, 10, 20, 30, 60]:
            item[f"winRate_{w}d"] = metric(row, "winRate", w)
            item[f"avgReturn_{w}d"] = metric(row, "avgReturn", w)
            item[f"medianReturn_{w}d"] = metric(row, "medianReturn", w)
            item[f"rewardRisk_{w}d"] = reward_risk(row, w)

        rows.append(item)

    return pd.DataFrame(rows)


def main():
    print("=================================")
    print("🧠 ANALYZE EXPECTANCY CURVES - SWING")
    print("=================================")

    frames = [process_file(path) for path in INPUT_FILES]
    frames = [f for f in frames if not f.empty]

    if not frames:
        raise RuntimeError(
            "no input expectancy files found. run analyze_trajectory_expectancy.py first."
        )

    out = pd.concat(frames, ignore_index=True)

    grade_rank = {
        "ELITE_SWING_EXPECTANCY": 1,
        "HIGH_SWING_EXPECTANCY": 2,
        "GOOD_SWING_EXPECTANCY": 3,
        "SHORT_SWING_ONLY": 4,
        "MIXED_SWING_EXPECTANCY": 5,
        "TACTICAL_ONLY_COLLAPSE_RISK": 6,
        "WEAK_SWING_EXPECTANCY": 7,
        "LOW_SAMPLE_RESEARCH_ONLY": 8,
    }

    out["gradeRank"] = out["swingGrade"].map(grade_rank).fillna(99)

    out = out.sort_values(
        by=["gradeRank", "swingScore_3d_20d", "rows"],
        ascending=[True, False, False],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out.to_dict(orient="records"), f, ensure_ascii=False, indent=2)

    print("")
    print("TOP SWING EXPECTANCY:")
    show_cols = [
        "sourceFile",
        "analysisType",
        "trajectoryState",
        "finalHierarchyState",
        "dailyContinuationState",
        "rows",
        "sampleQuality",
        "bestSwingWindow",
        "swingScore_3d_20d",
        "burstScore_1d_5d",
        "longSurvivabilityScore_30d_60d",
        "collapseRisk_20d_60d",
        "swingGrade",
        "winRate_3d",
        "winRate_5d",
        "winRate_10d",
        "winRate_20d",
        "avgReturn_3d",
        "avgReturn_5d",
        "avgReturn_10d",
        "avgReturn_20d",
    ]

    show_cols = [c for c in show_cols if c in out.columns]
    print(out[show_cols].head(40).to_string(index=False))

    print("")
    print("SWING GRADE DISTRIBUTION:")
    print(out["swingGrade"].value_counts(dropna=False).to_string())

    print("")
    print("BEST SWING WINDOW DISTRIBUTION:")
    print(out["bestSwingWindow"].value_counts(dropna=False).to_string())

    print("")
    print("✅ SAVED")
    print(OUT_CSV)
    print(OUT_JSON)


if __name__ == "__main__":
    main()
