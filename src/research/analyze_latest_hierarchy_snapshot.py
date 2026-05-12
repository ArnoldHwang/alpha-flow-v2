import json
from pathlib import Path

import pandas as pd

HIERARCHY_DIR = Path("data/hierarchy")

SYMBOL_CONFIG_CANDIDATES = [
    Path("config/symbols.json"),
    Path("config/market_symbols.json"),
]


def load_hierarchy_json_files():
    rows = []

    if not HIERARCHY_DIR.exists():
        print(f"❌ hierarchy dir 없음: {HIERARCHY_DIR}")
        return pd.DataFrame()

    files = sorted(HIERARCHY_DIR.glob("*.json"))

    print(f"📁 hierarchy json files: {len(files)}")

    for path in files:
        symbol_from_file = path.stem.upper()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "rows" in data and isinstance(data["rows"], list):
                items = data["rows"]
            elif "data" in data and isinstance(data["data"], list):
                items = data["data"]
            else:
                items = [data]
        else:
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            row = dict(item)
            row["symbol"] = str(row.get("symbol", symbol_from_file)).upper()
            rows.append(row)

    return pd.DataFrame(rows)


def normalize_symbol(symbol):
    return str(symbol).upper().replace("^", "").replace("=", "-").replace(".", "-")


def load_config_symbols():
    symbols = set()

    for path in SYMBOL_CONFIG_CANDIDATES:
        if not path.exists():
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            continue

        for item in data:
            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol")

            if not symbol:
                continue

            symbols.add(normalize_symbol(symbol))

    return symbols


def main():
    print("=================================")
    print("🧠 ANALYZE LATEST HIERARCHY SNAPSHOT")
    print("=================================")

    df = load_hierarchy_json_files()

    if df.empty:
        print("❌ hierarchy data 없음")
        return

    if "date" not in df.columns:
        print("❌ date 컬럼 없음")
        print(df.columns.tolist())
        return

    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    print("")
    print("=================================")
    print("📦 BASIC")
    print("=================================")
    print("rows:", len(df))
    print("symbols:", df["symbol"].nunique())
    print("first:", df["date"].min().date())
    print("last:", df["date"].max().date())

    print("")
    print("=================================")
    print("📅 LAST 30 DATE ROW COUNTS")
    print("=================================")
    date_counts = df.groupby("date").size().sort_index()
    print(date_counts.tail(30).to_string())

    latest_date = df["date"].max()
    latest_df = df[df["date"] == latest_date].copy()

    print("")
    print("=================================")
    print("🚨 LATEST DATE CHECK")
    print("=================================")
    print("latest date:", latest_date.date())
    print("latest rows:", len(latest_df))
    print("latest symbols:", latest_df["symbol"].nunique())
    print(latest_df["symbol"].sort_values().head(200).to_list())

    print("")
    print("=================================")
    print("🧩 SYMBOL LAST DATE DISTRIBUTION")
    print("=================================")

    symbol_last = (
        df.groupby("symbol")["date"]
        .max()
        .reset_index()
        .sort_values("date", ascending=False)
    )

    print(symbol_last["date"].dt.date.value_counts().sort_index().tail(30).to_string())

    print("")
    print("=== most recent symbols ===")
    print(symbol_last.head(40).to_string(index=False))

    print("")
    print("=== oldest symbols ===")
    print(symbol_last.tail(40).to_string(index=False))

    print("")
    print("=================================")
    print("⚙️ CONFIG SYMBOL MATCH CHECK")
    print("=================================")

    config_symbols = load_config_symbols()
    hierarchy_symbols = set(df["symbol"].unique())

    print("config symbols:", len(config_symbols))
    print("hierarchy symbols:", len(hierarchy_symbols))

    if config_symbols:
        matched = sorted(config_symbols & hierarchy_symbols)
        missing = sorted(config_symbols - hierarchy_symbols)
        extra = sorted(hierarchy_symbols - config_symbols)

        print("matched:", len(matched))
        print("missing from hierarchy:", len(missing))
        print("extra in hierarchy:", len(extra))

        print("")
        print("=== missing sample ===")
        print(missing[:100])

        print("")
        print("=== extra sample ===")
        print(extra[:100])

    print("")
    print("=================================")
    print("🔍 LATEST KEY SAMPLE")
    print("=================================")

    key_cols = [
        "date",
        "symbol",
        "finalHierarchyState",
        "survivabilityBias",
        "monthlyTrendState",
        "weeklyTrendState",
        "dailyTrendState",
        "dailyContinuationState",
        "monthlyExhaustionState",
        "weeklyExhaustionState",
        "dailyExhaustionState",
    ]

    existing_cols = [c for c in key_cols if c in df.columns]

    print(
        latest_df[existing_cols].sort_values("symbol").head(80).to_string(index=False)
    )


if __name__ == "__main__":
    main()
