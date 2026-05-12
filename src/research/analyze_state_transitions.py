from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HIERARCHY_DIR = ROOT / "data" / "hierarchy"
OUTPUT_DIR = ROOT / "data" / "research"


STATE_COL = "finalHierarchyState"
BIAS_COL = "survivabilityBias"

FORWARD_WINDOWS = [1, 5, 10, 20]


def load_hierarchy_data() -> pd.DataFrame:
    files = []
    files += list(HIERARCHY_DIR.glob("*.csv"))
    files += list(HIERARCHY_DIR.glob("*.json"))

    if not files:
        raise FileNotFoundError(f"hierarchy files not found: {HIERARCHY_DIR}")

    frames = []

    for file in files:
        if file.suffix == ".csv":
            frames.append(pd.read_csv(file))

        elif file.suffix == ".json":
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                frames.append(pd.DataFrame(data))
            elif isinstance(data, dict):
                if "rows" in data:
                    frames.append(pd.DataFrame(data["rows"]))
                elif "data" in data:
                    frames.append(pd.DataFrame(data["data"]))
                else:
                    frames.append(pd.DataFrame([data]))

    if not frames:
        raise ValueError("no hierarchy rows loaded")

    df = pd.concat(frames, ignore_index=True)

    required_cols = ["date", "symbol", STATE_COL]

    for col in required_cols:
        if col not in df.columns:
            raise KeyError(f"{col} column not found in hierarchy data")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    df = df.dropna(subset=["date", "symbol"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    return df


def add_forward_states(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    for window in FORWARD_WINDOWS:
        result[f"nextState_{window}d"] = result.groupby("symbol")[STATE_COL].shift(
            -window
        )

        if BIAS_COL in result.columns:
            result[f"nextBias_{window}d"] = result.groupby("symbol")[BIAS_COL].shift(
                -window
            )

    return result


def build_transition_table(
    df: pd.DataFrame,
    current_col: str,
    next_col: str,
) -> pd.DataFrame:
    temp = df[[current_col, next_col]].dropna().copy()

    transition = (
        temp.groupby([current_col, next_col])
        .size()
        .reset_index(name="count")
        .sort_values([current_col, "count"], ascending=[True, False])
    )

    total = transition.groupby(current_col)["count"].transform("sum")
    transition["rate"] = transition["count"] / total
    transition["ratePct"] = (transition["rate"] * 100).round(2)

    return transition


def summarize_survivability(df: pd.DataFrame, window: int) -> pd.DataFrame:
    next_col = f"nextState_{window}d"

    temp = df[[STATE_COL, next_col]].dropna().copy()

    if temp.empty:
        return pd.DataFrame(
            columns=[
                STATE_COL,
                "rows",
                "survivedRatePct",
                "riskTransitionRatePct",
            ]
        )

    good_keywords = [
        "ELITE",
        "CONSTRUCTIVE",
        "HEALTHY",
    ]

    risk_keywords = [
        "DETERIORATING",
        "TERMINAL",
        "LATE_STAGE",
    ]

    def is_good_state(value: str) -> int:
        value = str(value)
        return int(any(keyword in value for keyword in good_keywords))

    def is_risk_state(value: str) -> int:
        value = str(value)
        return int(any(keyword in value for keyword in risk_keywords))

    temp["survived"] = temp[next_col].apply(is_good_state).astype(float)
    temp["riskTransition"] = temp[next_col].apply(is_risk_state).astype(float)

    summary = (
        temp.groupby(STATE_COL)
        .agg(
            rows=(next_col, "count"),
            survivedRate=("survived", "mean"),
            riskTransitionRate=("riskTransition", "mean"),
        )
        .reset_index()
    )

    summary["survivedRatePct"] = (summary["survivedRate"] * 100).round(2)
    summary["riskTransitionRatePct"] = (summary["riskTransitionRate"] * 100).round(2)

    summary = summary.sort_values(
        ["survivedRate", "rows"],
        ascending=[False, False],
    )

    return summary[
        [
            STATE_COL,
            "rows",
            "survivedRatePct",
            "riskTransitionRatePct",
        ]
    ]


def print_top_transitions(
    transition: pd.DataFrame, window: int, top_n: int = 5
) -> None:
    print("\n=================================")
    print(f"🔁 TOP STATE TRANSITIONS: {window}D")
    print("=================================")

    for state, group in transition.groupby(STATE_COL):
        print(f"\n[{state}]")
        print(
            group.head(top_n)[[f"nextState_{window}d", "count", "ratePct"]].to_string(
                index=False
            )
        )


def print_survivability_summary(summary: pd.DataFrame, window: int) -> None:
    print("\n=================================")
    print(f"🧬 SURVIVABILITY SUMMARY: {window}D")
    print("=================================")
    print(summary.to_string(index=False))


def save_outputs(
    transition_tables: dict[int, pd.DataFrame],
    survivability_summaries: dict[int, pd.DataFrame],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for window, table in transition_tables.items():
        path = OUTPUT_DIR / f"state_transitions_{window}d.csv"
        table.to_csv(path, index=False)

    for window, summary in survivability_summaries.items():
        path = OUTPUT_DIR / f"state_survivability_summary_{window}d.csv"
        summary.to_csv(path, index=False)


def main() -> None:
    print("=================================")
    print("🧠 ANALYZE STATE TRANSITIONS")
    print("=================================")

    df = load_hierarchy_data()

    print(f"rows: {len(df):,}")
    print(f"symbols: {df['symbol'].nunique():,}")
    print(f"first: {df['date'].min().date()}")
    print(f"last: {df['date'].max().date()}")

    df = add_forward_states(df)

    transition_tables = {}
    survivability_summaries = {}

    for window in FORWARD_WINDOWS:
        next_col = f"nextState_{window}d"

        transition = build_transition_table(
            df=df,
            current_col=STATE_COL,
            next_col=next_col,
        )

        summary = summarize_survivability(df=df, window=window)

        transition_tables[window] = transition
        survivability_summaries[window] = summary

        print_top_transitions(transition, window)
        print_survivability_summary(summary, window)

    save_outputs(transition_tables, survivability_summaries)

    print("\n=================================")
    print("✅ SAVED")
    print("=================================")
    print(f"output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
