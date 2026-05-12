# src/research/analyze_transition_expectancy.py

import json
import os
from glob import glob
from typing import Any, Dict, List, Optional

import pandas as pd

INPUT_DIR = "data/transition_paths"
PRICE_SEARCH_ROOT = "data"
OUTPUT_DIR = "results/research"

MIN_ROWS = 30
HORIZONS = [1, 3, 5, 10, 20, 30, 60]

TARGET_PATH_COLUMNS = [
    "dailyStatePath3",
    "dailyStatePath5",
    "trajectoryStatePath3",
    "trajectoryStatePath5",
    "hierarchyStatePath3",
]


def load_json_records(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["records", "data", "rows", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]

    return []


def load_json_dir(input_dir: str) -> pd.DataFrame:
    rows = []

    for file_path in sorted(glob(os.path.join(input_dir, "*.json"))):
        file_name = os.path.basename(file_path)

        if file_name.startswith("_"):
            continue

        try:
            rows.extend(load_json_records(file_path))
        except Exception as e:
            print(f"SKIP {file_name}: {e}")

    return pd.DataFrame(rows)


def find_price_col(df: pd.DataFrame) -> Optional[str]:
    candidates = [
        "adjClose",
        "close",
        "Close",
        "price",
        "c",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    return None


def find_symbol_col(df: pd.DataFrame) -> Optional[str]:
    for col in ["symbol", "ticker", "Symbol"]:
        if col in df.columns:
            return col
    return None


def find_date_col(df: pd.DataFrame) -> Optional[str]:
    for col in ["date", "Date", "datetime", "time"]:
        if col in df.columns:
            return col
    return None


def build_price_dataframe() -> pd.DataFrame:
    print("")
    print("=================================")
    print("🔎 FIND PRICE DATA")
    print("=================================")

    price_rows = []
    scanned_files = 0
    used_files = 0

    json_files = sorted(
        glob(os.path.join(PRICE_SEARCH_ROOT, "**", "*.json"), recursive=True)
    )

    for file_path in json_files:
        normalized = file_path.replace("\\", "/")

        if "/transition_paths/" in normalized:
            continue

        if "/monthly/" in normalized or "/weekly/" in normalized:
            continue

        file_name = os.path.basename(file_path)

        if file_name.startswith("_"):
            continue

        scanned_files += 1

        try:
            records = load_json_records(file_path)
        except Exception:
            continue

        if not records:
            continue

        temp = pd.DataFrame(records)

        symbol_col = find_symbol_col(temp)
        date_col = find_date_col(temp)
        price_col = find_price_col(temp)

        if not symbol_col or not date_col or not price_col:
            continue

        temp = temp[[symbol_col, date_col, price_col]].copy()
        temp.columns = ["symbol", "date", "price"]

        temp["symbol"] = temp["symbol"].astype(str)
        temp["date"] = pd.to_datetime(temp["date"], errors="coerce")
        temp["price"] = pd.to_numeric(temp["price"], errors="coerce")

        temp = temp.dropna(subset=["symbol", "date", "price"])

        if temp.empty:
            continue

        price_rows.append(temp)
        used_files += 1

    print(f"scannedJsonFiles: {scanned_files:,}")
    print(f"usedPriceFiles: {used_files:,}")

    if not price_rows:
        raise ValueError(
            "가격 데이터가 있는 json을 못 찾았다. "
            "data 폴더 안에 symbol/date/close 또는 adjClose 있는 원천 파일 위치 확인 필요."
        )

    price_df = pd.concat(price_rows, ignore_index=True)
    price_df = price_df.drop_duplicates(subset=["symbol", "date"], keep="last")
    price_df = price_df.sort_values(["symbol", "date"]).copy()

    print(f"priceRows: {len(price_df):,}")
    print(f"priceSymbols: {price_df['symbol'].nunique():,}")
    print(f"priceDateMin: {price_df['date'].min().date()}")
    print(f"priceDateMax: {price_df['date'].max().date()}")

    return price_df


def attach_price(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "symbol" not in df.columns:
        raise ValueError("transition path 데이터에 symbol 컬럼이 없다.")

    if "date" not in df.columns:
        raise ValueError("transition path 데이터에 date 컬럼이 없다.")

    df["symbol"] = df["symbol"].astype(str)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    existing_price_col = find_price_col(df)

    if existing_price_col:
        df["price"] = pd.to_numeric(df[existing_price_col], errors="coerce")
        valid = df["price"].notna().sum()

        if valid > 0:
            print("")
            print("=================================")
            print("📌 PRICE FOUND IN TRANSITION DATA")
            print("=================================")
            print(f"priceColumn: {existing_price_col}")
            print(f"validPriceRows: {valid:,}")
            return df

    price_df = build_price_dataframe()

    before = len(df)

    merged = df.merge(
        price_df,
        on=["symbol", "date"],
        how="left",
    )

    matched = merged["price"].notna().sum()

    print("")
    print("=================================")
    print("🔗 PRICE MERGE RESULT")
    print("=================================")
    print(f"transitionRows: {before:,}")
    print(f"matchedPriceRows: {matched:,}")
    print(f"missingPriceRows: {before - matched:,}")

    if matched == 0:
        raise ValueError(
            "symbol/date 기준 가격 병합이 0건이다. "
            "transition_paths의 date 형식과 원천 가격 json의 date 형식/심볼명이 다른지 확인 필요."
        )

    return merged


def add_future_returns(df: pd.DataFrame) -> pd.DataFrame:
    df = attach_price(df)

    df = df.dropna(subset=["symbol", "date", "price"]).copy()
    df = df.sort_values(["symbol", "date"]).copy()

    print("")
    print("=================================")
    print("📌 BUILD FUTURE RETURNS")
    print("=================================")

    for h in HORIZONS:
        col = f"futureReturn{h}d"

        df[col] = (
            df.groupby("symbol")["price"]
            .shift(-h)
            .sub(df["price"])
            .div(df["price"])
            .mul(100)
        )

        valid = df[col].notna().sum()
        print(f"created: {col} | validRows={valid:,}")

    return df


def grade_expectancy(win_rate: float, avg_return: float, rows: int) -> str:
    if rows < MIN_ROWS:
        return "LOW_SAMPLE"

    if win_rate >= 58 and avg_return >= 3:
        return "HIGH_EXPECTANCY"

    if win_rate >= 54 and avg_return >= 1.5:
        return "GOOD_EXPECTANCY"

    if win_rate >= 51 and avg_return >= 0:
        return "MILD_EXPECTANCY"

    if avg_return < 0 or win_rate < 48:
        return "NEGATIVE_EXPECTANCY"

    return "MIXED_EXPECTANCY"


def analyze_path_column(df: pd.DataFrame, path_col: str) -> pd.DataFrame:
    if path_col not in df.columns:
        return pd.DataFrame()

    working = df[df[path_col].notna()].copy()
    working = working[working[path_col] != "INSUFFICIENT_HISTORY"]

    results = []

    for path, group in working.groupby(path_col):
        if len(group) < MIN_ROWS:
            continue

        row = {
            "pathColumn": path_col,
            "path": path,
            "rows": len(group),
        }

        for h in HORIZONS:
            ret_col = f"futureReturn{h}d"
            values = pd.to_numeric(group[ret_col], errors="coerce").dropna()

            if len(values) == 0:
                continue

            win_rate = round((values > 0).mean() * 100, 2)
            avg_return = round(values.mean(), 2)
            median_return = round(values.median(), 2)

            row[f"winRate_{h}d"] = win_rate
            row[f"avgReturn_{h}d"] = avg_return
            row[f"medianReturn_{h}d"] = median_return
            row[f"expectancyGrade_{h}d"] = grade_expectancy(
                win_rate,
                avg_return,
                len(values),
            )

        results.append(row)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    if "avgReturn_20d" in result_df.columns:
        result_df = result_df.sort_values(
            ["avgReturn_20d", "winRate_20d", "rows"],
            ascending=[False, False, False],
        )
    else:
        result_df = result_df.sort_values("rows", ascending=False)

    return result_df


def print_table(title: str, df: pd.DataFrame, limit: int = 25) -> None:
    print("")
    print("=================================")
    print(title)
    print("=================================")

    if df.empty:
        print("NO RESULT")
        return

    cols = [
        "path",
        "rows",
        "winRate_5d",
        "winRate_20d",
        "winRate_60d",
        "avgReturn_5d",
        "avgReturn_20d",
        "avgReturn_60d",
        "expectancyGrade_5d",
        "expectancyGrade_20d",
    ]

    existing = [c for c in cols if c in df.columns]
    print(df[existing].head(limit).to_string(index=False))


def main() -> None:
    print("=================================")
    print("🧠 ANALYZE TRANSITION EXPECTANCY")
    print("=================================")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = load_json_dir(INPUT_DIR)

    print(f"rows: {len(df):,}")
    print(f"columns: {len(df.columns):,}")

    if df.empty:
        raise ValueError("No transition path data loaded.")

    df = add_future_returns(df)

    all_results = []

    for path_col in TARGET_PATH_COLUMNS:
        result_df = analyze_path_column(df, path_col)

        print_table(f"🔥 TOP EXPECTANCY - {path_col}", result_df)

        if result_df.empty:
            continue

        output_path = os.path.join(
            OUTPUT_DIR,
            f"transition_expectancy_{path_col}.csv",
        )

        result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"saved: {output_path}")

        all_results.append(result_df)

    if all_results:
        merged = pd.concat(all_results, ignore_index=True)

        merged_path = os.path.join(
            OUTPUT_DIR,
            "transition_expectancy_all.csv",
        )

        merged.to_csv(merged_path, index=False, encoding="utf-8-sig")

        global_top = merged.sort_values(
            ["avgReturn_20d", "winRate_20d", "rows"],
            ascending=[False, False, False],
        )

        print_table("🚀 GLOBAL TOP TRANSITION PATHS", global_top, limit=40)
        print(f"mergedSaved: {merged_path}")

    print("")
    print("=================================")
    print("✅ DONE")
    print("=================================")


if __name__ == "__main__":
    main()
