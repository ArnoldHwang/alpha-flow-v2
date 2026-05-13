# src/research/build_state_expectancy_matrix.py

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "data" / "research" / "archetype_hierarchy_expectancy.csv"

OUT_DIR = ROOT / "data" / "research"
OUT_JSON = OUT_DIR / "state_expectancy_matrix.json"
OUT_CSV = OUT_DIR / "state_expectancy_matrix.csv"


HORIZONS = ["3d", "5d", "10d", "20d", "60d"]

MIN_ROWS_STRONG = 300
MIN_ROWS_OK = 50


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_str(value, default="UNKNOWN"):
    if pd.isna(value):
        return default
    value = str(value).strip()
    return value if value else default


def sample_quality(rows):
    if rows >= MIN_ROWS_STRONG:
        return "STRONG_SAMPLE"
    if rows >= MIN_ROWS_OK:
        return "OK_SAMPLE"
    return "LOW_SAMPLE"


def horizon_score(row, h):
    win = safe_float(row.get(f"winRate_{h}", 0))
    survival = safe_float(row.get(f"survivalRate_{h}", 0))
    avg_return = safe_float(row.get(f"avgReturn_{h}", 0))

    # rewardRisk는 현재 10d 기준만 있음. 없으면 1.0 처리.
    rr = safe_float(row.get("rewardRisk_10d", 1.0), 1.0)

    # 핵심:
    # 단순 win rate가 아니라
    # 생존율 + 수익률 + 손익비를 같이 본다.
    return win * 0.35 + survival * 0.30 + avg_return * 1.50 + rr * 5.00


def choose_best_horizon(row):
    scored = []

    for h in HORIZONS:
        score = horizon_score(row, h)
        scored.append((h, score))

    scored = sorted(scored, key=lambda x: x[1], reverse=True)

    best_horizon, best_score = scored[0]

    return best_horizon, round(best_score, 4)


def classify_expectancy(row, best_horizon):
    rows = int(safe_float(row.get("rows", 0)))
    win = safe_float(row.get(f"winRate_{best_horizon}", 0))
    survival = safe_float(row.get(f"survivalRate_{best_horizon}", 0))
    avg_return = safe_float(row.get(f"avgReturn_{best_horizon}", 0))
    rr = safe_float(row.get("rewardRisk_10d", 1.0), 1.0)

    if rows < MIN_ROWS_OK:
        return "LOW_CONFIDENCE"

    if win >= 60 and avg_return >= 8 and survival >= 35:
        return "ELITE_EXPECTANCY"

    if win >= 56 and avg_return >= 5 and survival >= 30:
        return "HIGH_EXPECTANCY"

    if win >= 53 and avg_return >= 2 and rr >= 1.1:
        return "GOOD_EXPECTANCY"

    if win >= 50 and avg_return >= 0:
        return "MILD_EXPECTANCY"

    if avg_return < 0 or win < 48:
        return "NEGATIVE_EXPECTANCY"

    return "MIXED_EXPECTANCY"


def classify_operating_mode(row, best_horizon, grade):
    archetype = safe_str(row.get("continuationArchetype"))
    hierarchy = safe_str(row.get("finalHierarchyState"))

    if grade == "LOW_CONFIDENCE":
        return "RESEARCH_ONLY"

    if "TERMINAL" in hierarchy:
        if grade in ["ELITE_EXPECTANCY", "HIGH_EXPECTANCY"]:
            return "TACTICAL_HIGH_RISK_CONTINUATION"
        return "TERMINAL_RISK_AVOID"

    if archetype in ["TACTICAL_PARABOLIC_CONTINUATION", "LATE_STAGE_CONTINUATION"]:
        return "TACTICAL_MOMENTUM_WINDOW"

    if best_horizon in ["3d", "5d", "10d"]:
        return "SHORT_SWING_CONTINUATION"

    if best_horizon == "20d":
        return "MIDTERM_CONTINUATION"

    if best_horizon == "60d":
        return "LONG_SURVIVABILITY_CONTINUATION"

    return "MIXED_CONTINUATION"


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
        archetype = safe_str(row.get("continuationArchetype"))
        hierarchy = safe_str(row.get("finalHierarchyState"))
        rows = int(safe_float(row.get("rows", 0)))

        best_horizon, best_score = choose_best_horizon(row)
        grade = classify_expectancy(row, best_horizon)
        mode = classify_operating_mode(row, best_horizon, grade)

        item = {
            "continuationArchetype": archetype,
            "finalHierarchyState": hierarchy,
            "rows": rows,
            "sampleQuality": sample_quality(rows),
            "bestHorizon": best_horizon,
            "expectancyScore": best_score,
            "expectancyGrade": grade,
            "operatingMode": mode,
            "winRate_3d": safe_float(row.get("winRate_3d")),
            "winRate_5d": safe_float(row.get("winRate_5d")),
            "winRate_10d": safe_float(row.get("winRate_10d")),
            "winRate_20d": safe_float(row.get("winRate_20d")),
            "winRate_60d": safe_float(row.get("winRate_60d")),
            "survivalRate_10d": safe_float(row.get("survivalRate_10d")),
            "survivalRate_20d": safe_float(row.get("survivalRate_20d")),
            "survivalRate_60d": safe_float(row.get("survivalRate_60d")),
            "avgReturn_5d": safe_float(row.get("avgReturn_5d")),
            "avgReturn_10d": safe_float(row.get("avgReturn_10d")),
            "avgReturn_20d": safe_float(row.get("avgReturn_20d")),
            "avgReturn_60d": safe_float(row.get("avgReturn_60d")),
            "avgMFE_10d": safe_float(row.get("avgMFE_10d")),
            "avgMAE_10d": safe_float(row.get("avgMAE_10d")),
            "rewardRisk_10d": safe_float(row.get("rewardRisk_10d")),
        }

        output_rows.append(item)

        if archetype not in matrix:
            matrix[archetype] = {}

        matrix[archetype][hierarchy] = item

    out_df = pd.DataFrame(output_rows)

    out_df = out_df.sort_values(
        by=["expectancyGrade", "expectancyScore", "rows"],
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
    print(f"matrix archetypes: {len(matrix):,}")
    print("")
    print("TOP EXPECTANCY:")
    print(
        out_df[
            [
                "continuationArchetype",
                "finalHierarchyState",
                "rows",
                "sampleQuality",
                "bestHorizon",
                "expectancyScore",
                "expectancyGrade",
                "operatingMode",
                "winRate_60d",
                "avgReturn_60d",
                "survivalRate_60d",
            ]
        ]
        .head(30)
        .to_string(index=False)
    )

    print("")
    print("✅ SAVED")
    print(OUT_CSV)
    print(OUT_JSON)


def main():
    build_matrix()


if __name__ == "__main__":
    main()
