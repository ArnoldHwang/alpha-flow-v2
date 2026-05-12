# src/trajectory/build_transition_paths.py

import json
import os
from typing import Any, Dict, List

import pandas as pd

# =====================================
# PATH CONFIG
# =====================================

INPUT_DIR = "data/trajectory"
OUTPUT_DIR = "data/transition_paths"

PATH_WINDOWS = [3, 5, 10]


# =====================================
# UTILS
# =====================================


def safe_state(value: Any) -> str:
    if value is None:
        return "NA"

    if pd.isna(value):
        return "NA"

    text = str(value).strip()

    if text == "" or text.lower() == "nan":
        return "NA"

    return text


def build_path(values: List[Any]) -> str:
    return ">".join([safe_state(v) for v in values])


def load_json_records(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["records", "data", "rows", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]

        return [data]

    return []


def save_json_records(file_path: str, records: List[Dict[str, Any]]) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# =====================================
# PATH BUILDER
# =====================================


def add_state_paths(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").copy()

    path_sources = {
        "dailyContinuationState": "dailyStatePath",
        "finalHierarchyState": "hierarchyStatePath",
        "trajectoryState": "trajectoryStatePath",
        "survivabilityBias": "survivabilityBiasPath",
    }

    for source_col, output_prefix in path_sources.items():
        if source_col not in df.columns:
            continue

        states = df[source_col].tolist()

        for window in PATH_WINDOWS:
            output_col = f"{output_prefix}{window}"
            paths = []

            for idx in range(len(df)):
                start_idx = max(0, idx - window + 1)
                window_values = states[start_idx : idx + 1]

                if len(window_values) < window:
                    paths.append("INSUFFICIENT_HISTORY")
                else:
                    paths.append(build_path(window_values))

            df[output_col] = paths

    return df


def process_symbol_file(input_path: str, output_path: str) -> Dict[str, Any]:
    records = load_json_records(input_path)

    if not records:
        return {
            "status": "SKIPPED_EMPTY",
            "rows": 0,
            "symbol": os.path.basename(input_path),
        }

    df = pd.DataFrame(records)

    if "date" not in df.columns:
        return {
            "status": "SKIPPED_NO_DATE",
            "rows": len(df),
            "symbol": os.path.basename(input_path),
        }

    if "symbol" not in df.columns:
        file_symbol = os.path.basename(input_path).replace(".json", "")
        df["symbol"] = file_symbol

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    if df.empty:
        return {
            "status": "SKIPPED_BAD_DATE",
            "rows": 0,
            "symbol": os.path.basename(input_path),
        }

    result = add_state_paths(df)

    result["date"] = result["date"].dt.strftime("%Y-%m-%d")

    output_records = result.to_dict(orient="records")
    save_json_records(output_path, output_records)

    path_cols = [c for c in result.columns if "Path" in c]

    return {
        "status": "OK",
        "rows": len(result),
        "symbol": str(result["symbol"].iloc[-1]),
        "pathColumns": path_cols,
    }


# =====================================
# MAIN
# =====================================


def main() -> None:
    print("=================================")
    print("🧠 BUILD TRANSITION PATHS")
    print("=================================")

    if not os.path.exists(INPUT_DIR):
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    json_files = sorted(
        [
            file_name
            for file_name in os.listdir(INPUT_DIR)
            if file_name.endswith(".json")
        ]
    )

    if not json_files:
        raise FileNotFoundError(f"No json files found in: {INPUT_DIR}")

    print(f"inputDir: {INPUT_DIR}")
    print(f"outputDir: {OUTPUT_DIR}")
    print(f"files: {len(json_files):,}")

    summary = []
    total_rows = 0
    ok_count = 0
    skipped_count = 0
    created_path_columns = set()

    for file_name in json_files:
        input_path = os.path.join(INPUT_DIR, file_name)
        output_path = os.path.join(OUTPUT_DIR, file_name)

        result = process_symbol_file(input_path, output_path)
        summary.append(
            {
                "file": file_name,
                **result,
            }
        )

        if result["status"] == "OK":
            ok_count += 1
            total_rows += result["rows"]

            for col in result.get("pathColumns", []):
                created_path_columns.add(col)
        else:
            skipped_count += 1

    summary_path = os.path.join(OUTPUT_DIR, "_transition_path_summary.json")
    save_json_records(summary_path, summary)

    print("")
    print("=================================")
    print("✅ TRANSITION PATHS SAVED")
    print("=================================")
    print(f"okFiles: {ok_count:,}")
    print(f"skippedFiles: {skipped_count:,}")
    print(f"totalRows: {total_rows:,}")
    print(f"summary: {summary_path}")

    print("")
    print("=================================")
    print("🧩 CREATED PATH COLUMNS")
    print("=================================")

    for col in sorted(created_path_columns):
        print(col)

    print("")
    print("=================================")
    print("📌 SAMPLE OUTPUT FILES")
    print("=================================")

    for item in summary[:20]:
        print(f"{item['file']} | {item['status']} | rows={item['rows']}")

    print("")
    print("다음 실행:")
    print("python src/research/analyze_transition_expectancy.py")


if __name__ == "__main__":
    main()
