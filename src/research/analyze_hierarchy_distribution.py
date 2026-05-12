from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HIERARCHY_DIR = ROOT / "data" / "hierarchy"

SYMBOL_CONFIG_PATHS = [
    ROOT / "config" / "symbols.json",
    ROOT / "config" / "market_symbols.json",
]

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


def normalize_symbol(symbol: str) -> str:
    return (
        str(symbol).upper().strip().replace("^", "").replace("=", "-").replace(".", "-")
    )


def load_watch_symbols() -> list[str]:
    symbols: set[str] = set()

    for path in SYMBOL_CONFIG_PATHS:
        if not path.exists():
            print(f"⚠️ config not found: {path}")
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 핵심:
        # themes / sector / betaType 같은 문자열은 절대 symbol로 읽지 않는다.
        # 오직 dict 안의 "symbol" 필드만 읽는다.
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = []
            for value in data.values():
                if isinstance(value, list):
                    items.extend(value)
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol")
            if not symbol:
                continue

            symbols.add(normalize_symbol(symbol))

    return sorted(symbols)


def load_hierarchy_data() -> pd.DataFrame:
    files = []
    files += list(HIERARCHY_DIR.glob("*.csv"))
    files += list(HIERARCHY_DIR.glob("*.json"))

    if not files:
        raise FileNotFoundError(f"hierarchy files not found: {HIERARCHY_DIR}")

    frames = []

    for file in sorted(files):
        if file.suffix == ".csv":
            frames.append(pd.read_csv(file))

        elif file.suffix == ".json":
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                frame = pd.DataFrame(data)
            elif isinstance(data, dict):
                if "rows" in data and isinstance(data["rows"], list):
                    frame = pd.DataFrame(data["rows"])
                elif "data" in data and isinstance(data["data"], list):
                    frame = pd.DataFrame(data["data"])
                else:
                    frame = pd.DataFrame([data])
            else:
                continue

            if "symbol" not in frame.columns:
                frame["symbol"] = file.stem

            frames.append(frame)

    if not frames:
        raise ValueError("no hierarchy rows loaded")

    df = pd.concat(frames, ignore_index=True)

    if "date" not in df.columns:
        raise KeyError("date column not found in hierarchy data")

    if "symbol" not in df.columns:
        raise KeyError("symbol column not found in hierarchy data")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["symbol"] = df["symbol"].map(normalize_symbol)

    df = df.dropna(subset=["date", "symbol"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

    return df


def print_value_counts(df: pd.DataFrame, col: str, top_n: int = 30) -> None:
    if col not in df.columns:
        return

    print(f"\n=== {col} ===")
    print(df[col].value_counts(dropna=False).head(top_n))


def get_latest_market_date(df: pd.DataFrame):
    date_counts = df.groupby("date")["symbol"].nunique().sort_index()

    max_symbol_count = int(date_counts.max())
    min_required_symbols = max(10, int(df["symbol"].nunique() * 0.7))

    valid_dates = date_counts[date_counts >= min_required_symbols]

    if valid_dates.empty:
        latest_date = date_counts.idxmax()
        print("\n⚠️ no broad market date found. using date with max symbol count.")
    else:
        latest_date = valid_dates.index.max()

    return latest_date, min_required_symbols, max_symbol_count


def print_latest_snapshot(df: pd.DataFrame) -> None:
    latest_date, min_required_symbols, max_symbol_count = get_latest_market_date(df)
    latest = df[df["date"] == latest_date].copy()

    print("\n=================================")
    print(" LATEST HIERARCHY SNAPSHOT")
    print("=================================")
    print(f"latest market date: {latest_date.date()}")
    print(f"symbols: {latest['symbol'].nunique()}")
    print(f"rows: {len(latest)}")
    print(f"required symbols: {min_required_symbols}")
    print(f"max symbols in one date: {max_symbol_count}")

    cols = [
        "symbol",
        "finalHierarchyState",
        "survivabilityBias",
        "dailyContinuationState",
        "monthlyExhaustionState",
        "weeklyExhaustionState",
        "dailyExhaustionState",
    ]

    cols = [c for c in cols if c in latest.columns]

    print("\n--- latest symbols ---")
    print(latest[cols].sort_values("symbol").to_string(index=False))


def print_symbol_recent(df: pd.DataFrame, symbols: list[str], days: int = 20) -> None:
    print("\n=================================")
    print("🎯 WATCH SYMBOLS")
    print("=================================")

    if not symbols:
        print("⚠️ watch symbols empty.")
        return

    available_symbols = set(df["symbol"].unique())
    target_symbols = sorted([s for s in symbols if s in available_symbols])
    missing_symbols = sorted([s for s in symbols if s not in available_symbols])

    print(f"config symbols: {len(symbols)}")
    print(f"available in hierarchy: {len(target_symbols)}")
    print(f"missing from hierarchy: {len(missing_symbols)}")

    if missing_symbols:
        print("\n--- missing sample ---")
        print(missing_symbols[:50])

    latest_date, _, _ = get_latest_market_date(df)
    latest = df[df["date"] == latest_date].copy()

    print("\n--- watch symbols latest state summary ---")

    cols = [
        "date",
        "symbol",
        "finalHierarchyState",
        "survivabilityBias",
        "monthlyContinuationState",
        "weeklyContinuationState",
        "dailyContinuationState",
    ]

    cols = [c for c in cols if c in latest.columns]

    watch_latest = latest[latest["symbol"].isin(target_symbols)].copy()

    if watch_latest.empty:
        print("⚠️ no watch symbols on latest market date.")
    else:
        print(watch_latest[cols].sort_values("symbol").to_string(index=False))

    # 너무 길어지는 것 방지: 최근 20일 상세는 핵심 상태만 출력
    key_symbols = target_symbols[:20]

    for symbol in key_symbols:
        target = df[df["symbol"] == symbol].tail(days)

        if target.empty:
            continue

        print("\n=================================")
        print(f"📈 RECENT STATE: {symbol}")
        print("=================================")

        recent_cols = [
            "date",
            "symbol",
            "finalHierarchyState",
            "survivabilityBias",
            "monthlyContinuationState",
            "weeklyContinuationState",
            "dailyContinuationState",
        ]

        recent_cols = [c for c in recent_cols if c in target.columns]
        print(target[recent_cols].to_string(index=False))


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
