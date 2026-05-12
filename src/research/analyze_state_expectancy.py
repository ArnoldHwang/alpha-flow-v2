import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

HIERARCHY_DIR = ROOT / "data" / "hierarchy"
RAW_DIR = ROOT / "data" / "raw" / "daily"

FORWARD_WINDOWS = [1, 3, 5, 10, 20, 30, 60]

MIN_SAMPLES = 30

PRIMARY_STATE_COL = "finalHierarchyState"
DAILY_STATE_COL = "dailyContinuationState"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_symbol(symbol):
    return (
        str(symbol).upper().strip().replace("^", "").replace("=", "-").replace(".", "-")
    )


def load_hierarchy_rows():
    rows = []

    for path in sorted(HIERARCHY_DIR.glob("*.json")):
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
        raise ValueError("hierarchy data empty")

    if "date" not in df.columns:
        raise KeyError("date column not found in hierarchy data")

    if "symbol" not in df.columns:
        raise KeyError("symbol column not found in hierarchy data")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].map(normalize_symbol)

    df = df.dropna(subset=["date", "symbol"])

    return df


def load_raw_daily_rows():
    rows = []

    for path in sorted(RAW_DIR.glob("*.json")):
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
        raise ValueError("raw daily data empty")

    if "date" not in df.columns:
        raise KeyError("date column not found in raw daily data")

    if "symbol" not in df.columns:
        raise KeyError("symbol column not found in raw daily data")

    if "close" not in df.columns:
        raise KeyError("close column not found in raw daily data")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].map(normalize_symbol)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    df = df.dropna(subset=["date", "symbol", "close"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    return df


def attach_forward_returns(df):
    df = df.sort_values(["symbol", "date"]).copy()

    for window in FORWARD_WINDOWS:
        future_close = df.groupby("symbol")["close"].shift(-window)

        df[f"forwardReturn_{window}d"] = (
            (future_close - df["close"]) / df["close"]
        ) * 100

        df[f"forwardUp_{window}d"] = (df[f"forwardReturn_{window}d"] > 0).astype(int)

    return df


def build_expectancy(df, group_cols, label_name):
    results = []

    if isinstance(group_cols, str):
        group_cols = [group_cols]

    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {
            "analysisType": label_name,
            "rows": len(group),
        }

        for col, key in zip(group_cols, keys):
            row[col] = key

        row["sampleQuality"] = "OK" if len(group) >= MIN_SAMPLES else "LOW_SAMPLE"

        for window in FORWARD_WINDOWS:
            ret_col = f"forwardReturn_{window}d"
            up_col = f"forwardUp_{window}d"

            valid = group.dropna(subset=[ret_col])

            row[f"validRows_{window}d"] = len(valid)

            if len(valid) == 0:
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
                valid_rows=len(valid),
                win_rate=win_rate,
                avg_return=avg_return,
            )

        results.append(row)

    result_df = pd.DataFrame(results)

    sort_cols = []
    ascending = []

    if "sampleQuality" in result_df.columns:
        result_df["sampleRank"] = result_df["sampleQuality"].map(
            {
                "OK": 0,
                "LOW_SAMPLE": 1,
            }
        )
        sort_cols.append("sampleRank")
        ascending.append(True)

    if "winRate_5d" in result_df.columns:
        sort_cols.append("winRate_5d")
        ascending.append(False)

    if "avgReturn_20d" in result_df.columns:
        sort_cols.append("avgReturn_20d")
        ascending.append(False)

    if sort_cols:
        result_df = result_df.sort_values(sort_cols, ascending=ascending)

    if "sampleRank" in result_df.columns:
        result_df = result_df.drop(columns=["sampleRank"])

    return result_df.reset_index(drop=True)


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


def print_single_state_summary(df):
    print("")
    print("=================================")
    print("🧠 STATE EXPECTANCY SUMMARY")
    print("=================================")

    cols = [
        "finalHierarchyState",
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

    print(df[cols].to_string(index=False))


def print_combo_summary(df):
    print("")
    print("=================================")
    print("🧩 HIERARCHY + DAILY COMBO EXPECTANCY")
    print("=================================")

    cols = [
        "finalHierarchyState",
        "dailyContinuationState",
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
        print("no OK sample combo")
        return

    print(ok[cols].head(40).to_string(index=False))


def print_key_findings(combo_df):
    print("")
    print("=================================")
    print("🔥 KEY COMBO FINDINGS")
    print("=================================")

    watch_combos = [
        ("DETERIORATING_STRUCTURE", "HEALTHY_CONTINUATION"),
        ("DETERIORATING_STRUCTURE", "RE_ACCELERATING_CONTINUATION"),
        ("MIXED_STRUCTURE", "HEALTHY_CONTINUATION"),
        ("MIXED_STRUCTURE", "RE_ACCELERATING_CONTINUATION"),
        ("ELITE_CONTINUATION_STRUCTURE", "HEALTHY_CONTINUATION"),
        ("CONSTRUCTIVE_PAUSE_STRUCTURE", "BASE_BUILDING"),
        ("CONSTRUCTIVE_PAUSE_STRUCTURE", "HEALTHY_CONTINUATION"),
        ("TERMINAL_STRUCTURE_RISK", "HEALTHY_CONTINUATION"),
        ("TERMINAL_STRUCTURE_RISK", "TERMINAL_RISK"),
        ("AGING_CONTINUATION_STRUCTURE", "HEALTHY_CONTINUATION"),
        ("HEALTHY_BUT_MONTHLY_EXTENDED", "HEALTHY_CONTINUATION"),
        ("LATE_STAGE_REACCELERATION", "HEALTHY_CONTINUATION"),
    ]

    cols = [
        "finalHierarchyState",
        "dailyContinuationState",
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

    cols = [c for c in cols if c in combo_df.columns]

    for hierarchy_state, daily_state in watch_combos:
        target = combo_df[
            (combo_df["finalHierarchyState"] == hierarchy_state)
            & (combo_df["dailyContinuationState"] == daily_state)
        ]

        if target.empty:
            continue

        print("")
        print(target[cols].to_string(index=False))


def main():
    print("=================================")
    print("🧠 ANALYZE STATE EXPECTANCY")
    print("=================================")

    hierarchy_df = load_hierarchy_rows()
    raw_df = load_raw_daily_rows()

    merged = pd.merge(
        hierarchy_df,
        raw_df[
            [
                "symbol",
                "date",
                "close",
            ]
        ],
        on=["symbol", "date"],
        how="inner",
    )

    merged = attach_forward_returns(merged)

    single_expectancy = build_expectancy(
        merged,
        PRIMARY_STATE_COL,
        "single_state",
    )

    combo_expectancy = build_expectancy(
        merged,
        [PRIMARY_STATE_COL, DAILY_STATE_COL],
        "hierarchy_daily_combo",
    )

    print_single_state_summary(single_expectancy)
    print_combo_summary(combo_expectancy)
    print_key_findings(combo_expectancy)

    output_dir = ROOT / "data" / "research"
    output_dir.mkdir(parents=True, exist_ok=True)

    single_path = output_dir / "state_expectancy.csv"
    combo_path = output_dir / "state_daily_combo_expectancy.csv"

    single_expectancy.to_csv(single_path, index=False)
    combo_expectancy.to_csv(combo_path, index=False)

    print("")
    print("=================================")
    print("✅ SAVED")
    print("=================================")
    print(single_path)
    print(combo_path)


if __name__ == "__main__":
    main()
