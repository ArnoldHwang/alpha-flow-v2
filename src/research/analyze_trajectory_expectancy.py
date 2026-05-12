import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

TRAJECTORY_DIR = ROOT / "data" / "trajectory"
RAW_DIR = ROOT / "data" / "raw" / "daily"
OUTPUT_DIR = ROOT / "data" / "research"

FORWARD_WINDOWS = [1, 3, 5, 10, 20, 30, 60]
MIN_SAMPLES = 30


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_symbol(symbol):
    return (
        str(symbol).upper().strip().replace("^", "").replace("=", "-").replace(".", "-")
    )


def load_json_rows(folder):
    rows = []

    for path in sorted(folder.glob("*.json")):
        data = load_json(path)

        if isinstance(data, list):
            rows.extend(data)
        elif isinstance(data, dict):
            if "rows" in data and isinstance(data["rows"], list):
                rows.extend(data["rows"])
            elif "data" in data and isinstance(data["data"], list):
                rows.extend(data["data"])
            else:
                rows.append(data)

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError(f"empty data: {folder}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].map(normalize_symbol)

    return df.dropna(subset=["date", "symbol"])


def attach_forward_returns(df):
    df = df.sort_values(["symbol", "date"]).copy()

    for window in FORWARD_WINDOWS:
        future_close = df.groupby("symbol")["close"].shift(-window)

        df[f"forwardReturn_{window}d"] = (
            (future_close - df["close"]) / df["close"]
        ) * 100

        df[f"forwardUp_{window}d"] = (df[f"forwardReturn_{window}d"] > 0).astype(int)

    return df


def grade_expectancy(valid_rows, win_rate, avg_return):
    if valid_rows < MIN_SAMPLES:
        return "LOW_SAMPLE"

    if win_rate >= 60 and avg_return >= 3:
        return "HIGH_EXPECTANCY"

    if win_rate >= 55 and avg_return >= 1:
        return "GOOD_EXPECTANCY"

    if win_rate >= 52 and avg_return >= 0:
        return "MILD_EXPECTANCY"

    if win_rate < 50 and avg_return < 0:
        return "NEGATIVE_EXPECTANCY"

    return "MIXED_EXPECTANCY"


def build_expectancy(df, group_cols, analysis_type):
    if isinstance(group_cols, str):
        group_cols = [group_cols]

    results = []

    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {
            "analysisType": analysis_type,
            "rows": len(group),
            "sampleQuality": "OK" if len(group) >= MIN_SAMPLES else "LOW_SAMPLE",
        }

        for col, key in zip(group_cols, keys):
            row[col] = key

        for window in FORWARD_WINDOWS:
            ret_col = f"forwardReturn_{window}d"
            up_col = f"forwardUp_{window}d"

            valid = group.dropna(subset=[ret_col])
            valid_rows = len(valid)

            row[f"validRows_{window}d"] = valid_rows

            if valid_rows == 0:
                row[f"winRate_{window}d"] = None
                row[f"avgReturn_{window}d"] = None
                row[f"medianReturn_{window}d"] = None
                row[f"positiveAvg_{window}d"] = None
                row[f"negativeAvg_{window}d"] = None
                row[f"expectancyGrade_{window}d"] = "NO_DATA"
                continue

            positive = valid[valid[ret_col] > 0]
            negative = valid[valid[ret_col] <= 0]

            win_rate = valid[up_col].mean() * 100
            avg_return = valid[ret_col].mean()

            row[f"winRate_{window}d"] = round(win_rate, 2)
            row[f"avgReturn_{window}d"] = round(avg_return, 2)
            row[f"medianReturn_{window}d"] = round(valid[ret_col].median(), 2)
            row[f"positiveAvg_{window}d"] = (
                round(positive[ret_col].mean(), 2) if len(positive) > 0 else None
            )
            row[f"negativeAvg_{window}d"] = (
                round(negative[ret_col].mean(), 2) if len(negative) > 0 else None
            )
            row[f"expectancyGrade_{window}d"] = grade_expectancy(
                valid_rows=valid_rows,
                win_rate=win_rate,
                avg_return=avg_return,
            )

        results.append(row)

    out = pd.DataFrame(results)

    if out.empty:
        return out

    out["sampleRank"] = out["sampleQuality"].map({"OK": 0, "LOW_SAMPLE": 1})

    sort_cols = ["sampleRank"]
    ascending = [True]

    if "winRate_5d" in out.columns:
        sort_cols.append("winRate_5d")
        ascending.append(False)

    if "avgReturn_20d" in out.columns:
        sort_cols.append("avgReturn_20d")
        ascending.append(False)

    out = out.sort_values(sort_cols, ascending=ascending)
    out = out.drop(columns=["sampleRank"])

    return out.reset_index(drop=True)


def print_summary(title, df, group_cols, limit=40):
    print("")
    print("=================================")
    print(title)
    print("=================================")

    cols = list(group_cols) + [
        "rows",
        "sampleQuality",
        "winRate_1d",
        "winRate_3d",
        "winRate_5d",
        "winRate_10d",
        "winRate_20d",
        "winRate_30d",
        "winRate_60d",
        "avgReturn_5d",
        "avgReturn_20d",
        "avgReturn_60d",
        "expectancyGrade_5d",
        "expectancyGrade_20d",
    ]

    cols = [c for c in cols if c in df.columns]

    ok = df[df["sampleQuality"] == "OK"].copy()

    if ok.empty:
        print("no OK samples")
        return

    print(ok[cols].head(limit).to_string(index=False))


def print_key_findings(trajectory_df, combo_df):
    print("")
    print("=================================")
    print("🔥 KEY TRAJECTORY FINDINGS")
    print("=================================")

    cols1 = [
        "trajectoryState",
        "rows",
        "sampleQuality",
        "winRate_5d",
        "winRate_20d",
        "winRate_60d",
        "avgReturn_5d",
        "avgReturn_20d",
        "avgReturn_60d",
        "expectancyGrade_5d",
        "expectancyGrade_20d",
    ]

    cols1 = [c for c in cols1 if c in trajectory_df.columns]

    watch_trajectories = [
        "RECOVERY_TRAJECTORY",
        "STABLE_CONTINUATION",
        "ACCELERATING_TRAJECTORY",
        "DISTRIBUTION_TRAJECTORY",
        "BREAKDOWN_PERSISTENCE",
        "VOLATILE_CHOP",
        "NEUTRAL_TRAJECTORY",
    ]

    for trajectory in watch_trajectories:
        target = trajectory_df[trajectory_df["trajectoryState"] == trajectory]
        if not target.empty:
            print("")
            print(target[cols1].to_string(index=False))

    print("")
    print("=================================")
    print("🧩 KEY HIERARCHY + TRAJECTORY COMBOS")
    print("=================================")

    cols2 = [
        "finalHierarchyState",
        "trajectoryState",
        "rows",
        "sampleQuality",
        "winRate_5d",
        "winRate_20d",
        "winRate_60d",
        "avgReturn_5d",
        "avgReturn_20d",
        "avgReturn_60d",
        "expectancyGrade_5d",
        "expectancyGrade_20d",
    ]

    cols2 = [c for c in cols2 if c in combo_df.columns]

    watch_combos = [
        ("MIXED_STRUCTURE", "RECOVERY_TRAJECTORY"),
        ("MIXED_STRUCTURE", "STABLE_CONTINUATION"),
        ("MIXED_STRUCTURE", "DISTRIBUTION_TRAJECTORY"),
        ("MIXED_STRUCTURE", "BREAKDOWN_PERSISTENCE"),
        ("ELITE_CONTINUATION_STRUCTURE", "RECOVERY_TRAJECTORY"),
        ("AGING_CONTINUATION_STRUCTURE", "RECOVERY_TRAJECTORY"),
        ("AGING_CONTINUATION_STRUCTURE", "DISTRIBUTION_TRAJECTORY"),
        ("TERMINAL_STRUCTURE_RISK", "DISTRIBUTION_TRAJECTORY"),
        ("TERMINAL_STRUCTURE_RISK", "BREAKDOWN_PERSISTENCE"),
        ("HEALTHY_BUT_MONTHLY_EXTENDED", "RECOVERY_TRAJECTORY"),
        ("LATE_STAGE_REACCELERATION", "RECOVERY_TRAJECTORY"),
    ]

    for hierarchy_state, trajectory_state in watch_combos:
        target = combo_df[
            (combo_df["finalHierarchyState"] == hierarchy_state)
            & (combo_df["trajectoryState"] == trajectory_state)
        ]

        if not target.empty:
            print("")
            print(target[cols2].to_string(index=False))


def main():
    print("=================================")
    print("🧠 ANALYZE TRAJECTORY EXPECTANCY")
    print("=================================")

    trajectory_df = load_json_rows(TRAJECTORY_DIR)

    raw_df = load_json_rows(RAW_DIR)

    raw_df["close"] = pd.to_numeric(raw_df["close"], errors="coerce")
    raw_df = raw_df.dropna(subset=["close"])

    merged = pd.merge(
        trajectory_df,
        raw_df[["symbol", "date", "close"]],
        on=["symbol", "date"],
        how="inner",
    )

    merged = attach_forward_returns(merged)

    trajectory_expectancy = build_expectancy(
        merged,
        "trajectoryState",
        "trajectory",
    )

    hierarchy_trajectory_expectancy = build_expectancy(
        merged,
        ["finalHierarchyState", "trajectoryState"],
        "hierarchy_trajectory_combo",
    )

    daily_trajectory_expectancy = build_expectancy(
        merged,
        ["dailyContinuationState", "trajectoryState"],
        "daily_trajectory_combo",
    )

    print_summary(
        "🧠 TRAJECTORY EXPECTANCY SUMMARY",
        trajectory_expectancy,
        ["trajectoryState"],
    )

    print_summary(
        "🧩 HIERARCHY + TRAJECTORY EXPECTANCY",
        hierarchy_trajectory_expectancy,
        ["finalHierarchyState", "trajectoryState"],
    )

    print_summary(
        "📌 DAILY STATE + TRAJECTORY EXPECTANCY",
        daily_trajectory_expectancy,
        ["dailyContinuationState", "trajectoryState"],
    )

    print_key_findings(
        trajectory_expectancy,
        hierarchy_trajectory_expectancy,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path1 = OUTPUT_DIR / "trajectory_expectancy.csv"
    path2 = OUTPUT_DIR / "hierarchy_trajectory_expectancy.csv"
    path3 = OUTPUT_DIR / "daily_trajectory_expectancy.csv"

    trajectory_expectancy.to_csv(path1, index=False)
    hierarchy_trajectory_expectancy.to_csv(path2, index=False)
    daily_trajectory_expectancy.to_csv(path3, index=False)

    print("")
    print("=================================")
    print("✅ SAVED")
    print("=================================")
    print(path1)
    print(path2)
    print(path3)


if __name__ == "__main__":
    main()
