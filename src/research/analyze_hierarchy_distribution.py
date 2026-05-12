from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HIERARCHY_DIR = ROOT / "data" / "hierarchy"
SYMBOLS_PATH = ROOT / "config" / "symbols.json"


STATE_COLS = [
    "finalHierarchyState",
    "survivabilityBias",
    "monthlyTrendState",
    "monthlyExpansionState",
    "monthlyExhaustionState",
    "monthlyContinuationState",
    "weeklyTrendState",
    "weeklyExpansionState",
    "weeklyExhaustionState",
    "weeklyContinuationState",
    "dailyTrendState",
    "dailyExpansionState",
    "dailyExhaustionState",
    "dailyContinuationState",
]


def load_watch_symbols() -> list[str]:
    if not SYMBOLS_PATH.exists():
        print(f"⚠️ symbols.json not found: {SYMBOLS_PATH}")
        return []

    with open(SYMBOLS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    symbols: list[str] = []

    if isinstance(data, list):
        symbols.extend(data)

    elif isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                symbols.extend(value)

            elif isinstance(value, dict):
                for nested_value in value.values():
                    if isinstance(nested_value, list):
                        symbols.extend(nested_value)

    symbols = [str(s).upper().strip() for s in symbols if s]
    return sorted(set(symbols))


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

    if "date" not in df.columns:
        raise KeyError("date column not found in hierarchy data")

    if "symbol" not in df.columns:
        raise KeyError("symbol column not found in hierarchy data")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    df = df.dropna(subset=["date", "symbol"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

    return df


def print_value_counts(df: pd.DataFrame, col: str, top_n: int = 30) -> None:
    if col not in df.columns:
        return

    print(f"\n=== {col} ===")
    print(df[col].value_counts(dropna=False).head(top_n))


def print_latest_snapshot(df: pd.DataFrame) -> None:
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].copy()

    print("\n=================================")
    print("📌 LATEST HIERARCHY SNAPSHOT")
    print("=================================")
    print(f"latest date: {latest_date.date()}")
    print(f"symbols: {latest['symbol'].nunique()}")
    print(f"rows: {len(latest)}")

    cols = [
        "symbol",
        "finalHierarchyState",
        "survivabilityBias",
        "monthlyContinuationState",
        "weeklyContinuationState",
        "dailyContinuationState",
        "monthlyExhaustionState",
        "weeklyExhaustionState",
        "dailyExhaustionState",
    ]

    cols = [c for c in cols if c in latest.columns]

    print("\n--- latest symbols ---")
    print(latest[cols].to_string(index=False))


def print_symbol_recent(df: pd.DataFrame, symbols: list[str], days: int = 20) -> None:
    if not symbols:
        print("\n⚠️ watch symbols empty. Skip recent symbol section.")
        return

    available_symbols = set(df["symbol"].unique())
    target_symbols = [s for s in symbols if s in available_symbols]

    print("\n=================================")
    print("🎯 WATCH SYMBOLS")
    print("=================================")
    print(f"config symbols: {len(symbols)}")
    print(f"available in hierarchy: {len(target_symbols)}")

    for symbol in target_symbols:
        target = df[df["symbol"] == symbol].tail(days)

        if target.empty:
            continue

        print("\n=================================")
        print(f"📈 RECENT STATE: {symbol}")
        print("=================================")

        cols = [
            "date",
            "symbol",
            "finalHierarchyState",
            "survivabilityBias",
            "monthlyContinuationState",
            "weeklyContinuationState",
            "dailyContinuationState",
        ]

        cols = [c for c in cols if c in target.columns]
        print(target[cols].to_string(index=False))


def main() -> None:
    print("=================================")
    print("🧠 ANALYZE HIERARCHY DISTRIBUTION")
    print("=================================")

    df = load_hierarchy_data()

    print(f"rows: {len(df):,}")
    print(f"symbols: {df['symbol'].nunique():,}")
    print(f"first: {df['date'].min().date()}")
    print(f"last: {df['date'].max().date()}")

    for col in STATE_COLS:
        print_value_counts(df, col)

    print_latest_snapshot(df)

    watch_symbols = load_watch_symbols()
    print_symbol_recent(df, watch_symbols, days=20)


if __name__ == "__main__":
    main()
