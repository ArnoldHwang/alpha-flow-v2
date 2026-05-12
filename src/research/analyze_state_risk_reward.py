import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

HIERARCHY_DIR = ROOT / "data" / "hierarchy"
RAW_DIR = ROOT / "data" / "raw" / "daily"
OUTPUT_DIR = ROOT / "data" / "research"

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
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    return df


def attach_forward_mfe_mae(df):
    df = df.sort_values(["symbol", "date"]).copy()

    result_rows = []

    for symbol, group in df.groupby("symbol"):
        group = group.sort_values("date").reset_index(drop=True)

        closes = group["close"].tolist()
        highs = group["high"].tolist()
        lows = group["low"].tolist()

        for i, row in group.iterrows():
            row_dict = row.to_dict()
            entry_close = closes[i]

            for window in FORWARD_WINDOWS:
                future_start = i + 1
                future_end = i + window + 1

                future_highs = highs[future_start:future_end]
                future_lows = lows[future_start:future_end]
                future_closes = closes[future_start:future_end]

                if not future_closes:
                    row_dict[f"forwardReturn_{window}d"] = None
                    row_dict[f"futureMaxGain_{window}d"] = None
                    row_dict[f"futureMaxDrawdown_{window}d"] = None
                    row_dict[f"hitPositive_{window}d"] = None
                    continue

                exit_close = future_closes[-1]

                forward_return = ((exit_close - entry_close) / entry_close) * 100
                max_gain = ((max(future_highs) - entry_close) / entry_close) * 100
                max_drawdown = ((min(future_lows) - entry_close) / entry_close) * 100

                row_dict[f"forwardReturn_{window}d"] = forward_return
                row_dict[f"futureMaxGain_{window}d"] = max_gain
                row_dict[f"futureMaxDrawdown_{window}d"] = max_drawdown
                row_dict[f"hitPositive_{window}d"] = int(forward_return > 0)

            result_rows.append(row_dict)

    return pd.DataFrame(result_rows)


def build_risk_reward_summary(df, state_col):
    results = []

    for state, group in df.groupby(state_col):
        row = {
            "state": state,
            "rows": len(group),
        }

        for window in FORWARD_WINDOWS:
            ret_col = f"forwardReturn_{window}d"
            gain_col = f"futureMaxGain_{window}d"
            dd_col = f"futureMaxDrawdown_{window}d"
            win_col = f"hitPositive_{window}d"

            valid = group.dropna(subset=[ret_col, gain_col, dd_col]).copy()

            if valid.empty:
                row[f"winRate_{window}d"] = None
                row[f"avgReturn_{window}d"] = None
                row[f"avgMaxGain_{window}d"] = None
                row[f"avgMaxDrawdown_{window}d"] = None
                row[f"rewardRisk_{window}d"] = None
                row[f"medianReturn_{window}d"] = None
                continue

            avg_gain = valid[gain_col].mean()
            avg_dd = valid[dd_col].mean()

            if avg_dd < 0:
                rr = avg_gain / abs(avg_dd)
            else:
                rr = None

            row[f"winRate_{window}d"] = round(valid[win_col].mean() * 100, 2)
            row[f"avgReturn_{window}d"] = round(valid[ret_col].mean(), 2)
            row[f"medianReturn_{window}d"] = round(valid[ret_col].median(), 2)
            row[f"avgMaxGain_{window}d"] = round(avg_gain, 2)
            row[f"avgMaxDrawdown_{window}d"] = round(avg_dd, 2)
            row[f"rewardRisk_{window}d"] = round(rr, 2) if rr is not None else None

        results.append(row)

    result = pd.DataFrame(results)

    sort_col = "rewardRisk_10d"
    if sort_col in result.columns:
        result = result.sort_values(sort_col, ascending=False)

    return result


def print_summary(df):
    print("")
    print("=================================")
    print("🧠 STATE RISK / REWARD SUMMARY")
    print("=================================")

    cols = [
        "state",
        "rows",
        "winRate_1d",
        "winRate_5d",
        "winRate_10d",
        "winRate_20d",
        "winRate_30d",
        "avgMaxGain_5d",
        "avgMaxDrawdown_5d",
        "rewardRisk_5d",
        "avgMaxGain_20d",
        "avgMaxDrawdown_20d",
        "rewardRisk_20d",
    ]

    cols = [c for c in cols if c in df.columns]

    print(df[cols].to_string(index=False))


def main():
    print("=================================")
    print("🧠 ANALYZE STATE RISK / REWARD")
    print("=================================")

    hierarchy_df = load_hierarchy_rows()
    raw_df = load_raw_daily_rows()

    raw_with_forward = attach_forward_mfe_mae(raw_df)

    merged = pd.merge(
        hierarchy_df,
        raw_with_forward,
        on=["symbol", "date"],
        how="inner",
        suffixes=("", "_raw"),
    )

    summary = build_risk_reward_summary(
        merged,
        STATE_COL,
    )

    print_summary(summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    save_path = OUTPUT_DIR / "state_risk_reward.csv"
    summary.to_csv(save_path, index=False)

    print("")
    print("=================================")
    print("✅ SAVED")
    print("=================================")
    print(save_path)


if __name__ == "__main__":
    main()
