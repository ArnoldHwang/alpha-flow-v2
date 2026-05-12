import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

HIERARCHY_DIR = ROOT / "data" / "hierarchy"
RAW_DIR = ROOT / "data" / "raw" / "daily"

STATE_COL = "finalHierarchyState"

FORWARD_WINDOWS = [1, 5, 10, 20, 30]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_hierarchy_rows():
    rows = []

    for path in HIERARCHY_DIR.glob("*.json"):
        rows.extend(load_json(path))

    df = pd.DataFrame(rows)

    df["date"] = pd.to_datetime(df["date"])

    return df


def load_raw_daily_rows():
    rows = []

    for path in RAW_DIR.glob("*.json"):
        rows.extend(load_json(path))

    df = pd.DataFrame(rows)

    df["date"] = pd.to_datetime(df["date"])

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


def build_expectancy(df, state_col):
    results = []

    for state, group in df.groupby(state_col):
        row = {
            "state": state,
            "rows": len(group),
        }

        for window in FORWARD_WINDOWS:
            ret_col = f"forwardReturn_{window}d"
            up_col = f"forwardUp_{window}d"

            valid = group.dropna(subset=[ret_col])

            if len(valid) == 0:
                row[f"winRate_{window}d"] = None
                row[f"avgReturn_{window}d"] = None
                row[f"medianReturn_{window}d"] = None
                row[f"positiveAvg_{window}d"] = None
                row[f"negativeAvg_{window}d"] = None
                continue

            positive = valid[valid[ret_col] > 0]
            negative = valid[valid[ret_col] <= 0]

            row[f"winRate_{window}d"] = round(
                valid[up_col].mean() * 100,
                2,
            )

            row[f"avgReturn_{window}d"] = round(
                valid[ret_col].mean(),
                2,
            )

            row[f"medianReturn_{window}d"] = round(
                valid[ret_col].median(),
                2,
            )

            row[f"positiveAvg_{window}d"] = (
                round(
                    positive[ret_col].mean(),
                    2,
                )
                if len(positive) > 0
                else None
            )

            row[f"negativeAvg_{window}d"] = (
                round(
                    negative[ret_col].mean(),
                    2,
                )
                if len(negative) > 0
                else None
            )

        results.append(row)

    result_df = pd.DataFrame(results)

    result_df = result_df.sort_values(
        "winRate_5d",
        ascending=False,
    )

    return result_df


def print_summary(df):
    print("")
    print("=================================")
    print("🧠 STATE EXPECTANCY SUMMARY")
    print("=================================")

    cols = [
        "state",
        "rows",
        "winRate_1d",
        "winRate_5d",
        "winRate_10d",
        "winRate_20d",
        "winRate_30d",
        "avgReturn_5d",
        "avgReturn_20d",
    ]

    print(df[cols].to_string(index=False))


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

    expectancy = build_expectancy(
        merged,
        STATE_COL,
    )

    print_summary(expectancy)

    output_dir = ROOT / "data" / "research"

    output_dir.mkdir(parents=True, exist_ok=True)

    save_path = output_dir / "state_expectancy.csv"

    expectancy.to_csv(save_path, index=False)

    print("")
    print("=================================")
    print("✅ SAVED")
    print("=================================")
    print(save_path)


if __name__ == "__main__":
    main()
