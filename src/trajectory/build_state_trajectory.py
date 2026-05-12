import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

HIERARCHY_DIR = ROOT / "data" / "hierarchy"
OUTPUT_DIR = ROOT / "data" / "trajectory"

LOOKBACK_DAYS = 10


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_serializer(obj):
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")

    return str(obj)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            default=json_serializer,
        )


def classify_trajectory(states):
    recent = list(states)[-LOOKBACK_DAYS:]

    if len(recent) < 3:
        return "INSUFFICIENT_HISTORY"

    # =====================================
    # RECOVERY
    # =====================================

    recovery_pattern = [
        "SOFT_PULLBACK",
        "HEALTHY_RESET",
        "BASE_BUILDING",
        "HEALTHY_CONTINUATION",
    ]

    recovery_hits = sum(1 for s in recent if s in recovery_pattern)

    if "HEALTHY_CONTINUATION" in recent[-3:] and recovery_hits >= 5:
        return "RECOVERY_TRAJECTORY"

    # =====================================
    # REACCELERATION
    # =====================================

    if recent.count("RE_ACCELERATING_CONTINUATION") >= 2:
        return "ACCELERATING_TRAJECTORY"

    # =====================================
    # STABLE CONTINUATION
    # =====================================

    healthy_count = sum(
        1
        for s in recent
        if s
        in [
            "HEALTHY_CONTINUATION",
            "BASE_BUILDING",
        ]
    )

    if healthy_count >= 7:
        return "STABLE_CONTINUATION"

    # =====================================
    # DISTRIBUTION
    # =====================================

    distribution_count = sum(
        1
        for s in recent
        if s
        in [
            "LATE_STAGE_CONTINUATION",
            "TERMINAL_RISK",
            "REAL_BREAKDOWN",
            "PANIC_SELLING",
        ]
    )

    if distribution_count >= 5:
        return "DISTRIBUTION_TRAJECTORY"

    # =====================================
    # BREAKDOWN PERSISTENCE
    # =====================================

    breakdown_count = sum(
        1
        for s in recent
        if s
        in [
            "REAL_BREAKDOWN",
            "PANIC_SELLING",
        ]
    )

    if breakdown_count >= 4:
        return "BREAKDOWN_PERSISTENCE"

    # =====================================
    # VOLATILE CHOP
    # =====================================

    unique_states = len(set(recent))

    if unique_states >= 6:
        return "VOLATILE_CHOP"

    return "NEUTRAL_TRAJECTORY"


def process_symbol(path):
    rows = load_json(path)

    df = pd.DataFrame(rows)

    if df.empty:
        return

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    trajectory_rows = []

    history = []

    for _, row in df.iterrows():
        current_state = row.get("dailyContinuationState")

        history.append(current_state)

        trajectory = classify_trajectory(history)

        row_dict = dict(row)

        row_dict["trajectoryState"] = trajectory

        trajectory_rows.append(row_dict)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    save_path = OUTPUT_DIR / path.name

    save_json(
        save_path,
        trajectory_rows,
    )

    print(f"✅ {path.stem} trajectory complete")


def main():
    print("=================================")
    print("🧠 BUILD STATE TRAJECTORY")
    print("=================================")

    files = sorted(HIERARCHY_DIR.glob("*.json"))

    print(f"symbols: {len(files)}")

    for path in files:
        process_symbol(path)

    print("")
    print("=================================")
    print("✅ TRAJECTORY COMPLETE")
    print("=================================")


if __name__ == "__main__":
    main()
