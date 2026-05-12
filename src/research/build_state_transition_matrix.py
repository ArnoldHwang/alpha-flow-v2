# src/research/build_state_transition_matrix.py

import json
import os
from glob import glob
from typing import Any, Dict, List

import pandas as pd

INPUT_DIR = "data/transition_paths"
OUTPUT_DIR = "results/research"

STATE_COLUMNS = [
    "dailyContinuationState",
    "trajectoryState",
    "finalHierarchyState",
    "survivabilityBias",
]

FORWARD_STEPS = [1, 3, 5, 10]
MIN_ROWS = 20


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


def load_transition_data() -> pd.DataFrame:
    rows = []

    for file_path in sorted(glob(os.path.join(INPUT_DIR, "*.json"))):
        file_name = os.path.basename(file_path)

        if file_name.startswith("_"):
            continue

        try:
            rows.extend(load_json_records(file_path))
        except Exception as e:
            print(f"SKIP {file_name}: {e}")

    return pd.DataFrame(rows)


def safe_state(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NA"

    text = str(value).strip()

    if text == "" or text.lower() == "nan":
        return "NA"

    return text


def build_transition_matrix(
    df: pd.DataFrame,
    state_col: str,
    forward_step: int,
) -> pd.DataFrame:
    working = df[["symbol", "date", state_col]].copy()
    working[state_col] = working[state_col].apply(safe_state)

    working = working.sort_values(["symbol", "date"]).copy()

    next_col = f"next_{state_col}_{forward_step}d"

    working[next_col] = working.groupby("symbol")[state_col].shift(-forward_step)

    working[next_col] = working[next_col].apply(safe_state)

    working = working[(working[state_col] != "NA") & (working[next_col] != "NA")].copy()

    counts = working.groupby([state_col, next_col]).size().reset_index(name="count")

    totals = counts.groupby(state_col)["count"].sum().reset_index(name="total")

    result = counts.merge(totals, on=state_col, how="left")
    result["probability"] = (result["count"] / result["total"] * 100).round(2)

    result = result[result["total"] >= MIN_ROWS].copy()

    result = result.rename(
        columns={
            state_col: "currentState",
            next_col: "nextState",
        }
    )

    result["stateColumn"] = state_col
    result["forwardStep"] = forward_step

    result = result[
        [
            "stateColumn",
            "forwardStep",
            "currentState",
            "nextState",
            "count",
            "total",
            "probability",
        ]
    ]

    result = result.sort_values(
        ["stateColumn", "forwardStep", "currentState", "probability"],
        ascending=[True, True, True, False],
    )

    return result


def print_top_transitions(matrix: pd.DataFrame, title: str, limit: int = 40) -> None:
    print("")
    print("=================================")
    print(title)
    print("=================================")

    if matrix.empty:
        print("NO RESULT")
        return

    print(
        matrix[
            [
                "stateColumn",
                "forwardStep",
                "currentState",
                "nextState",
                "count",
                "total",
                "probability",
            ]
        ]
        .head(limit)
        .to_string(index=False)
    )


def print_state_view(matrix: pd.DataFrame, state_col: str, step: int) -> None:
    subset = matrix[
        (matrix["stateColumn"] == state_col) & (matrix["forwardStep"] == step)
    ].copy()

    if subset.empty:
        return

    print("")
    print("=================================")
    print(f"🧠 MATRIX VIEW | {state_col} | +{step}d")
    print("=================================")

    key_states = [
        "HEALTHY_CONTINUATION",
        "SOFT_PULLBACK",
        "HEALTHY_RESET",
        "REAL_BREAKDOWN",
        "PANIC_SELLING",
        "RECOVERY_TRAJECTORY",
        "ACCELERATING_TRAJECTORY",
        "STABLE_CONTINUATION",
        "DISTRIBUTION_TRAJECTORY",
        "BREAKDOWN_PERSISTENCE",
        "VOLATILE_CHOP",
        "MIXED_STRUCTURE",
        "AGING_CONTINUATION_STRUCTURE",
        "ELITE_CONTINUATION_STRUCTURE",
        "TERMINAL_STRUCTURE_RISK",
    ]

    for state in key_states:
        temp = subset[subset["currentState"] == state].copy()

        if temp.empty:
            continue

        print("")
        print(f"[{state}]")
        print(
            temp[
                [
                    "nextState",
                    "count",
                    "total",
                    "probability",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )


def main() -> None:
    print("=================================")
    print("🧠 BUILD STATE TRANSITION MATRIX")
    print("=================================")

    if not os.path.exists(INPUT_DIR):
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = load_transition_data()

    print(f"rows: {len(df):,}")
    print(f"columns: {len(df.columns):,}")

    if df.empty:
        raise ValueError("No transition path data loaded.")

    required = ["symbol", "date"]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["symbol", "date"]).copy()

    all_matrices = []

    for state_col in STATE_COLUMNS:
        if state_col not in df.columns:
            print(f"SKIP missing column: {state_col}")
            continue

        for step in FORWARD_STEPS:
            matrix = build_transition_matrix(
                df=df,
                state_col=state_col,
                forward_step=step,
            )

            if matrix.empty:
                continue

            output_path = os.path.join(
                OUTPUT_DIR,
                f"state_transition_matrix_{state_col}_{step}d.csv",
            )

            matrix.to_csv(output_path, index=False, encoding="utf-8-sig")

            print("")
            print(f"saved: {output_path}")

            all_matrices.append(matrix)

            print_state_view(matrix, state_col, step)

    if all_matrices:
        merged = pd.concat(all_matrices, ignore_index=True)

        merged_path = os.path.join(
            OUTPUT_DIR,
            "state_transition_matrix_all.csv",
        )

        merged.to_csv(merged_path, index=False, encoding="utf-8-sig")

        high_prob = merged[
            (merged["probability"] >= 40) & (merged["total"] >= 100)
        ].copy()

        high_prob = high_prob.sort_values(
            ["probability", "total"],
            ascending=[False, False],
        )

        print_top_transitions(
            high_prob,
            "🔥 HIGH PROBABILITY TRANSITIONS",
            limit=60,
        )

        print("")
        print(f"mergedSaved: {merged_path}")

    print("")
    print("=================================")
    print("✅ DONE")
    print("=================================")


if __name__ == "__main__":
    main()
