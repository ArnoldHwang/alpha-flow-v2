# src/research/analyze_archetype_expectancy.py

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

ARCHETYPE_DIR = ROOT / "data" / "survivability_archetypes"
RAW_DAILY_DIR = ROOT / "data" / "raw" / "daily"

OUTPUT_DIR = ROOT / "data" / "research"
OUTPUT_PATH = OUTPUT_DIR / "archetype_expectancy.csv"
OUTPUT_COMBO_PATH = OUTPUT_DIR / "archetype_hierarchy_expectancy.csv"

FORWARD_WINDOWS = [1, 3, 5, 10, 20, 30, 60]
MIN_SAMPLES = 30


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_float(value: Any, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def normalize_symbol(symbol: Any) -> str:
    return (
        str(symbol).upper().strip().replace("^", "").replace("=", "-").replace(".", "-")
    )


def load_records_from_dir(directory: Path, label: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    if not directory.exists():
        raise FileNotFoundError(f"{label} dir not found: {directory}")

    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue

        data = load_json(path)

        if isinstance(data, list):
            rows.extend(data)
        elif isinstance(data, dict):
            for key in ["records", "data", "rows", "items"]:
                if isinstance(data.get(key), list):
                    rows.extend(data[key])
                    break
            else:
                rows.append(data)

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError(f"{label} data empty")

    if "symbol" not in df.columns:
        raise KeyError(f"{label} missing symbol column")

    if "date" not in df.columns:
        raise KeyError(f"{label} missing date column")

    df["symbol"] = df["symbol"].map(normalize_symbol)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["symbol", "date"]).copy()

    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def load_archetype_rows() -> pd.DataFrame:
    df = load_records_from_dir(ARCHETYPE_DIR, "archetype")

    required = [
        "continuationArchetype",
        "archetypeBias",
        "preferredTimeframe",
        "archetypeRisk",
    ]

    for col in required:
        if col not in df.columns:
            raise KeyError(f"archetype data missing column: {col}")

    return df


def load_raw_daily_rows() -> pd.DataFrame:
    df = load_records_from_dir(RAW_DAILY_DIR, "raw daily")

    if "close" not in df.columns:
        raise KeyError("raw daily missing close column")

    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    if "high" in df.columns:
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
    else:
        df["high"] = df["close"]

    if "low" in df.columns:
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
    else:
        df["low"] = df["close"]

    df = df.dropna(subset=["close"]).copy()
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def attach_forward_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["symbol", "date"]).copy()

    for window in FORWARD_WINDOWS:
        future_close = df.groupby("symbol")["close"].shift(-window)

        df[f"forwardReturn_{window}d"] = (
            (future_close - df["close"]) / df["close"]
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


def safe_div(a, b):
    if a is None or b is None:
        return None
    if pd.isna(a) or pd.isna(b) or b == 0:
        return None
    return a / b


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


def detect_best_horizon(row: Dict[str, Any]) -> str:
    candidates = []

    for window in FORWARD_WINDOWS:
        valid_rows = row.get(f"validRows_{window}d", 0)
        avg_return = row.get(f"avgReturn_{window}d")
        win_rate = row.get(f"winRate_{window}d")
        reward_risk = row.get(f"rewardRisk_{window}d")
        survival_rate = row.get(f"survivalRate_{window}d")

        if valid_rows < MIN_SAMPLES:
            continue

        if avg_return is None or win_rate is None:
            continue

        rr = reward_risk if reward_risk is not None else 0
        sr = survival_rate if survival_rate is not None else 0

        score = avg_return * 2.0 + (win_rate - 50) * 0.25 + rr * 1.5 + (sr - 50) * 0.12

        candidates.append((score, window))

    if not candidates:
        return "NO_RELIABLE_HORIZON"

    _, best = max(candidates, key=lambda x: x[0])

    if best in [1, 3]:
        return "SHORT_BURST"

    if best in [5, 10]:
        return "SWING_CONTINUATION"

    if best in [20, 30]:
        return "MIDTERM_CONTINUATION"

    if best == 60:
        return "LONG_SURVIVABILITY"

    return f"{best}D_BEST"


def build_expectancy(df: pd.DataFrame, group_cols, label: str) -> pd.DataFrame:
    if isinstance(group_cols, str):
        group_cols = [group_cols]

    missing = [c for c in group_cols if c not in df.columns]

    if missing:
        print(f"⚠️ skip {label}: missing {missing}")
        return pd.DataFrame()

    rows = []

    for keys, group in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {
            "analysisType": label,
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
                len(valid),
                win_rate,
                avg_return,
                reward_risk,
            )

        row["bestHorizon"] = detect_best_horizon(row)
        rows.append(row)

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    result["sampleRank"] = (
        result["sampleQuality"].map({"OK": 0, "LOW_SAMPLE": 1}).fillna(9)
    )

    sort_cols = ["sampleRank"]
    ascending = [True]

    for c in ["avgReturn_20d", "survivalRate_20d", "winRate_10d", "avgReturn_60d"]:
        if c in result.columns:
            sort_cols.append(c)
            ascending.append(False)

    result = result.sort_values(sort_cols, ascending=ascending)
    result = result.drop(columns=["sampleRank"])

    return result.reset_index(drop=True)


def print_summary(title: str, df: pd.DataFrame, cols, limit=30):
    print("")
    print("=================================")
    print(title)
    print("=================================")

    if df.empty:
        print("no data")
        return

    show_cols = [
        *cols,
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
        "avgMFE_10d",
        "avgMAE_10d",
        "rewardRisk_10d",
        "expectancyGrade_10d",
        "expectancyGrade_20d",
    ]

    show_cols = [c for c in show_cols if c in df.columns]

    ok = df[df["sampleQuality"] == "OK"].copy()

    if ok.empty:
        print("no OK sample rows")
        return

    print(ok[show_cols].head(limit).to_string(index=False))


def main():
    print("=================================")
    print("🧠 ANALYZE ARCHETYPE EXPECTANCY")
    print("=================================")

    archetype_df = load_archetype_rows()
    raw_df = load_raw_daily_rows()

    print(f"archetype rows: {len(archetype_df):,}")
    print(f"raw rows: {len(raw_df):,}")

    merged = pd.merge(
        archetype_df,
        raw_df[["symbol", "date", "close", "high", "low"]],
        on=["symbol", "date"],
        how="inner",
    )

    if merged.empty:
        raise ValueError("merged archetype + raw daily empty")

    print(f"merged rows: {len(merged):,}")

    merged = attach_forward_metrics(merged)

    archetype_exp = build_expectancy(
        merged,
        "continuationArchetype",
        "archetype",
    )

    archetype_hierarchy_exp = build_expectancy(
        merged,
        ["continuationArchetype", "finalHierarchyState"],
        "archetype_hierarchy_combo",
    )

    archetype_trajectory_exp = build_expectancy(
        merged,
        ["continuationArchetype", "trajectoryState"],
        "archetype_trajectory_combo",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    archetype_exp.to_csv(OUTPUT_PATH, index=False)
    archetype_hierarchy_exp.to_csv(OUTPUT_COMBO_PATH, index=False)
    archetype_trajectory_exp.to_csv(
        OUTPUT_DIR / "archetype_trajectory_expectancy.csv",
        index=False,
    )

    print_summary(
        "🧬 ARCHETYPE EXPECTANCY",
        archetype_exp,
        ["continuationArchetype"],
    )

    print_summary(
        "🧩 ARCHETYPE + HIERARCHY EXPECTANCY",
        archetype_hierarchy_exp,
        ["continuationArchetype", "finalHierarchyState"],
    )

    print("")
    print("✅ SAVED")
    print(OUTPUT_PATH)
    print(OUTPUT_COMBO_PATH)
    print(OUTPUT_DIR / "archetype_trajectory_expectancy.csv")


if __name__ == "__main__":
    main()
