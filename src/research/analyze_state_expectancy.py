import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

HIERARCHY_DIR = ROOT / "data" / "hierarchy"
TRAJECTORY_DIR = ROOT / "data" / "trajectory"
RAW_DIR = ROOT / "data" / "raw" / "daily"

OUTPUT_DIR = ROOT / "data" / "research"

FORWARD_WINDOWS = [1, 3, 5, 10, 20, 30, 60]
MIN_SAMPLES = 30

PRIMARY_STATE_COL = "finalHierarchyState"
DAILY_STATE_COL = "dailyContinuationState"
TRAJECTORY_COL = "trajectoryState"
SURVIVABILITY_COL = "survivabilityBias"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_symbol(symbol):
    return (
        str(symbol).upper().strip().replace("^", "").replace("=", "-").replace(".", "-")
    )


def safe_div(a, b):
    if b is None or pd.isna(b) or b == 0:
        return None
    if a is None or pd.isna(a):
        return None
    return a / b


def load_json_rows_from_dir(directory, label):
    rows = []

    if not directory.exists():
        raise FileNotFoundError(f"{label} directory not found: {directory}")

    for path in sorted(directory.glob("*.json")):
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
        raise ValueError(f"{label} data empty: {directory}")

    return df


def prepare_symbol_date(df, label):
    for col in ["date", "symbol"]:
        if col not in df.columns:
            raise KeyError(f"{col} column not found in {label} data")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].map(normalize_symbol)

    df = df.dropna(subset=["date", "symbol"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    return df


def load_hierarchy_rows():
    df = load_json_rows_from_dir(HIERARCHY_DIR, "hierarchy")
    return prepare_symbol_date(df, "hierarchy")


def load_trajectory_rows():
    df = load_json_rows_from_dir(TRAJECTORY_DIR, "trajectory")
    df = prepare_symbol_date(df, "trajectory")

    if TRAJECTORY_COL not in df.columns:
        raise KeyError(f"{TRAJECTORY_COL} column not found in trajectory data")

    keep_cols = ["symbol", "date", TRAJECTORY_COL]

    for optional_col in [
        "trajectoryType",
        "trajectoryScore",
        "trajectoryBias",
        "stateTransition",
        "transitionType",
    ]:
        if optional_col in df.columns:
            keep_cols.append(optional_col)

    df = df[keep_cols].copy()
    df = df.drop_duplicates(subset=["symbol", "date"], keep="last")

    return df


def load_raw_daily_rows():
    df = load_json_rows_from_dir(RAW_DIR, "raw daily")

    for col in ["date", "symbol", "close"]:
        if col not in df.columns:
            raise KeyError(f"{col} column not found in raw daily data")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].map(normalize_symbol)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    df["high"] = (
        pd.to_numeric(df["high"], errors="coerce")
        if "high" in df.columns
        else df["close"]
    )
    df["low"] = (
        pd.to_numeric(df["low"], errors="coerce")
        if "low" in df.columns
        else df["close"]
    )

    df = df.dropna(subset=["date", "symbol", "close"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    return df


def attach_forward_metrics(df):
    df = df.sort_values(["symbol", "date"]).copy()

    for window in FORWARD_WINDOWS:
        df[f"forwardReturn_{window}d"] = (
            (df.groupby("symbol")["close"].shift(-window) - df["close"]) / df["close"]
        ) * 100

        df[f"forwardMFE_{window}d"] = (
            df.groupby("symbol", group_keys=False)
            .apply(
                lambda g: (
                    (
                        g["high"]
                        .shift(-1)
                        .rolling(window, min_periods=1)
                        .max()
                        .shift(-(window - 1))
                        - g["close"]
                    )
                    / g["close"]
                )
                * 100
            )
            .reset_index(level=0, drop=True)
        )

        df[f"forwardMAE_{window}d"] = (
            df.groupby("symbol", group_keys=False)
            .apply(
                lambda g: (
                    (
                        g["low"]
                        .shift(-1)
                        .rolling(window, min_periods=1)
                        .min()
                        .shift(-(window - 1))
                        - g["close"]
                    )
                    / g["close"]
                )
                * 100
            )
            .reset_index(level=0, drop=True)
        )

        df[f"forwardUp_{window}d"] = (df[f"forwardReturn_{window}d"] > 0).astype(int)

        df[f"survived_{window}d"] = (
            (df[f"forwardReturn_{window}d"] > 0) & (df[f"forwardMAE_{window}d"] > -8)
        ).astype(int)

    return df


def grade_expectancy(valid_rows, win_rate, avg_return, reward_risk):
    if valid_rows < MIN_SAMPLES:
        return "LOW_SAMPLE"

    if (
        win_rate >= 60
        and avg_return >= 3
        and reward_risk is not None
        and reward_risk >= 1.5
    ):
        return "HIGH_EXPECTANCY"

    if (
        win_rate >= 55
        and avg_return >= 1
        and reward_risk is not None
        and reward_risk >= 1.1
    ):
        return "GOOD_EXPECTANCY"

    if win_rate >= 52 and avg_return >= 0:
        return "MILD_EXPECTANCY"

    if win_rate < 50 and avg_return < 0:
        return "NEGATIVE_EXPECTANCY"

    return "MIXED_EXPECTANCY"


def detect_best_horizon(row):
    candidates = []

    for window in FORWARD_WINDOWS:
        valid_rows = row.get(f"validRows_{window}d")
        win_rate = row.get(f"winRate_{window}d")
        avg_return = row.get(f"avgReturn_{window}d")
        reward_risk = row.get(f"rewardRisk_{window}d")
        survival_rate = row.get(f"survivalRate_{window}d")

        if valid_rows is None or pd.isna(valid_rows) or valid_rows < MIN_SAMPLES:
            continue
        if win_rate is None or pd.isna(win_rate):
            continue
        if avg_return is None or pd.isna(avg_return):
            continue

        rr = reward_risk if reward_risk is not None and not pd.isna(reward_risk) else 0
        sr = (
            survival_rate
            if survival_rate is not None and not pd.isna(survival_rate)
            else 0
        )

        score = avg_return * 2.0 + (win_rate - 50) * 0.25 + rr * 1.5 + (sr - 50) * 0.12
        candidates.append((score, window))

    if not candidates:
        return "NO_RELIABLE_HORIZON"

    _, best_window = max(candidates, key=lambda x: x[0])

    if best_window in [1, 3]:
        return "SHORT_BURST"
    if best_window in [5, 10]:
        return "SWING_CONTINUATION"
    if best_window in [20, 30]:
        return "MID_TERM_CONTINUATION"
    if best_window == 60:
        return "LONG_SURVIVABILITY"

    return f"{best_window}D_BEST"


def build_expectancy(df, group_cols, label_name):
    results = []

    if isinstance(group_cols, str):
        group_cols = [group_cols]

    missing = [c for c in group_cols if c not in df.columns]
    if missing:
        print(f"\n⚠️ SKIP {label_name}: missing columns {missing}")
        return pd.DataFrame()

    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {
            "analysisType": label_name,
            "rows": len(group),
            "sampleQuality": "OK" if len(group) >= MIN_SAMPLES else "LOW_SAMPLE",
        }

        for col, key in zip(group_cols, keys):
            row[col] = key

        for window in FORWARD_WINDOWS:
            ret_col = f"forwardReturn_{window}d"
            mfe_col = f"forwardMFE_{window}d"
            mae_col = f"forwardMAE_{window}d"
            up_col = f"forwardUp_{window}d"
            survived_col = f"survived_{window}d"

            valid = group.dropna(subset=[ret_col]).copy()
            row[f"validRows_{window}d"] = len(valid)

            if valid.empty:
                row[f"winRate_{window}d"] = None
                row[f"survivalRate_{window}d"] = None
                row[f"avgReturn_{window}d"] = None
                row[f"medianReturn_{window}d"] = None
                row[f"positiveAvg_{window}d"] = None
                row[f"negativeAvg_{window}d"] = None
                row[f"avgMFE_{window}d"] = None
                row[f"avgMAE_{window}d"] = None
                row[f"rewardRisk_{window}d"] = None
                row[f"expectancyGrade_{window}d"] = "NO_DATA"
                continue

            positive = valid[valid[ret_col] > 0]
            negative = valid[valid[ret_col] <= 0]

            win_rate = valid[up_col].mean() * 100
            survival_rate = valid[survived_col].mean() * 100
            avg_return = valid[ret_col].mean()
            median_return = valid[ret_col].median()

            positive_avg = positive[ret_col].mean() if len(positive) > 0 else None
            negative_avg = negative[ret_col].mean() if len(negative) > 0 else None

            avg_mfe = valid[mfe_col].mean()
            avg_mae = valid[mae_col].mean()

            reward_risk = (
                safe_div(positive_avg, abs(negative_avg))
                if negative_avg is not None
                else None
            )

            row[f"winRate_{window}d"] = round(win_rate, 2)
            row[f"survivalRate_{window}d"] = round(survival_rate, 2)
            row[f"avgReturn_{window}d"] = round(avg_return, 2)
            row[f"medianReturn_{window}d"] = round(median_return, 2)
            row[f"positiveAvg_{window}d"] = (
                round(positive_avg, 2) if positive_avg is not None else None
            )
            row[f"negativeAvg_{window}d"] = (
                round(negative_avg, 2) if negative_avg is not None else None
            )
            row[f"avgMFE_{window}d"] = round(avg_mfe, 2)
            row[f"avgMAE_{window}d"] = round(avg_mae, 2)
            row[f"rewardRisk_{window}d"] = (
                round(reward_risk, 2) if reward_risk is not None else None
            )

            row[f"expectancyGrade_{window}d"] = grade_expectancy(
                valid_rows=len(valid),
                win_rate=win_rate,
                avg_return=avg_return,
                reward_risk=reward_risk,
            )

        row["bestHorizon"] = detect_best_horizon(row)
        results.append(row)

    result_df = pd.DataFrame(results)

    if result_df.empty:
        return result_df

    result_df["sampleRank"] = (
        result_df["sampleQuality"].map({"OK": 0, "LOW_SAMPLE": 1}).fillna(9)
    )

    sort_cols = ["sampleRank"]
    ascending = [True]

    for col in [
        "avgReturn_20d",
        "survivalRate_20d",
        "winRate_10d",
        "rewardRisk_10d",
        "avgReturn_5d",
    ]:
        if col in result_df.columns:
            sort_cols.append(col)
            ascending.append(False)

    result_df = result_df.sort_values(sort_cols, ascending=ascending)
    result_df = result_df.drop(columns=["sampleRank"])

    return result_df.reset_index(drop=True)


def save_result(df, filename):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename

    if df is None or df.empty:
        print(f"⚠️ no data saved: {path}")
        return None

    df.to_csv(path, index=False)
    print(path)
    return path


def print_summary(title, df, state_cols, limit=30):
    print("")
    print("=================================")
    print(title)
    print("=================================")

    if df is None or df.empty:
        print("no data")
        return

    cols = state_cols + [
        "rows",
        "sampleQuality",
        "bestHorizon",
        "winRate_3d",
        "winRate_5d",
        "winRate_10d",
        "winRate_20d",
        "winRate_60d",
        "survivalRate_10d",
        "survivalRate_20d",
        "survivalRate_60d",
        "avgReturn_5d",
        "avgReturn_10d",
        "avgReturn_20d",
        "avgReturn_60d",
        "rewardRisk_10d",
        "expectancyGrade_10d",
        "expectancyGrade_20d",
    ]

    cols = [c for c in cols if c in df.columns]
    ok = df[df["sampleQuality"] == "OK"].copy() if "sampleQuality" in df.columns else df

    if ok.empty:
        print("no OK sample rows")
        return

    print(ok[cols].head(limit).to_string(index=False))


def print_key_findings(df):
    print("")
    print("=================================")
    print("🔥 KEY V2 EXPECTANCY FINDINGS")
    print("=================================")

    if df is None or df.empty:
        print("no combo data")
        return

    ok = df[df["sampleQuality"] == "OK"].copy()

    if ok.empty:
        print("no OK sample combo")
        return

    cols = [
        c
        for c in [
            PRIMARY_STATE_COL,
            DAILY_STATE_COL,
            TRAJECTORY_COL,
            SURVIVABILITY_COL,
            "rows",
            "bestHorizon",
            "winRate_5d",
            "winRate_10d",
            "winRate_20d",
            "survivalRate_10d",
            "survivalRate_20d",
            "avgReturn_10d",
            "avgReturn_20d",
            "rewardRisk_10d",
            "rewardRisk_20d",
            "expectancyGrade_10d",
            "expectancyGrade_20d",
        ]
        if c in ok.columns
    ]

    print("\n📌 Best 10d swing continuation candidates")
    swing = ok.sort_values(
        ["avgReturn_10d", "winRate_10d", "rewardRisk_10d"],
        ascending=[False, False, False],
    )
    print(swing[cols].head(15).to_string(index=False))

    print("\n📌 Best 20d survivability candidates")
    mid = ok.sort_values(
        ["survivalRate_20d", "avgReturn_20d", "rewardRisk_20d"],
        ascending=[False, False, False],
    )
    print(mid[cols].head(15).to_string(index=False))

    print("\n📌 Dangerous negative expectancy candidates")
    danger = ok.sort_values(["avgReturn_10d", "winRate_10d"], ascending=[True, True])
    print(danger[cols].head(15).to_string(index=False))


def main():
    print("=================================")
    print("🧠 ANALYZE STATE EXPECTANCY V2")
    print("=================================")

    hierarchy_df = load_hierarchy_rows()
    trajectory_df = load_trajectory_rows()
    raw_df = load_raw_daily_rows()

    print(f"hierarchy rows: {len(hierarchy_df):,}")
    print(f"trajectory rows: {len(trajectory_df):,}")
    print(f"raw daily rows: {len(raw_df):,}")

    state_df = pd.merge(
        hierarchy_df,
        trajectory_df,
        on=["symbol", "date"],
        how="left",
    )

    missing_trajectory = state_df[TRAJECTORY_COL].isna().sum()
    print(f"merged state rows: {len(state_df):,}")
    print(f"missing trajectoryState: {missing_trajectory:,}")

    merged = pd.merge(
        state_df,
        raw_df[["symbol", "date", "close", "high", "low"]],
        on=["symbol", "date"],
        how="inner",
    )

    if merged.empty:
        raise ValueError("merged state + raw daily data empty")

    print(f"merged price rows: {len(merged):,}")

    merged = attach_forward_metrics(merged)

    analysis_specs = [
        ("state_expectancy.csv", [PRIMARY_STATE_COL], "single_hierarchy_state"),
        (
            "state_daily_combo_expectancy.csv",
            [PRIMARY_STATE_COL, DAILY_STATE_COL],
            "hierarchy_daily_combo",
        ),
        (
            "hierarchy_trajectory_expectancy.csv",
            [PRIMARY_STATE_COL, TRAJECTORY_COL],
            "hierarchy_trajectory_combo",
        ),
        ("survivability_expectancy.csv", [SURVIVABILITY_COL], "survivability_bias"),
        ("trajectory_expectancy.csv", [TRAJECTORY_COL], "trajectory_state"),
        (
            "state_daily_trajectory_expectancy.csv",
            [PRIMARY_STATE_COL, DAILY_STATE_COL, TRAJECTORY_COL],
            "hierarchy_daily_trajectory_combo",
        ),
        (
            "state_survivability_trajectory_expectancy.csv",
            [PRIMARY_STATE_COL, SURVIVABILITY_COL, TRAJECTORY_COL],
            "hierarchy_survivability_trajectory_combo",
        ),
    ]

    results = []

    for filename, group_cols, label in analysis_specs:
        result = build_expectancy(merged, group_cols, label)
        results.append((filename, group_cols, label, result))

    print_summary(
        "🧠 SINGLE HIERARCHY STATE EXPECTANCY", results[0][3], [PRIMARY_STATE_COL]
    )
    print_summary(
        "🧩 HIERARCHY + DAILY EXPECTANCY",
        results[1][3],
        [PRIMARY_STATE_COL, DAILY_STATE_COL],
    )
    print_summary(
        "🧬 HIERARCHY + TRAJECTORY EXPECTANCY",
        results[2][3],
        [PRIMARY_STATE_COL, TRAJECTORY_COL],
    )
    print_summary(
        "🛡️ SURVIVABILITY BIAS EXPECTANCY", results[3][3], [SURVIVABILITY_COL]
    )
    print_summary("🧭 TRAJECTORY EXPECTANCY", results[4][3], [TRAJECTORY_COL])

    print_key_findings(results[5][3])

    print("")
    print("=================================")
    print("✅ SAVED")
    print("=================================")

    for filename, _, _, result in results:
        save_result(result, filename)


if __name__ == "__main__":
    main()
