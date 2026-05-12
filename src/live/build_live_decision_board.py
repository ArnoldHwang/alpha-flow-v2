# src/live/build_live_decision_board.py

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "data" / "live_states" / "_live_confirmed_merge_summary.json"
OUTPUT_PATH = ROOT / "data" / "live_states" / "_live_decision_board.json"


BOARD_GROUPS = [
    "ACTION_CONFIRMING",
    "ACTION_WATCH",
    "ACTION_CAUTION",
    "ACTION_RISK_OFF",
    "ACTION_AVOID",
    "ACTION_NEUTRAL",
]


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sort_group_items(items, group):
    if group in {"ACTION_CONFIRMING", "ACTION_WATCH"}:
        return sorted(
            items,
            key=lambda x: (
                x.get("mergedContinuationScore", 0),
                x.get("breakoutPressure", 0),
                x.get("liveMove", 0),
            ),
            reverse=True,
        )

    if group == "ACTION_CAUTION":
        return sorted(
            items,
            key=lambda x: (
                x.get("mergedContinuationScore", 0),
                -x.get("failurePressure", 0),
            ),
            reverse=True,
        )

    if group in {"ACTION_RISK_OFF", "ACTION_AVOID"}:
        return sorted(
            items,
            key=lambda x: (
                x.get("failurePressure", 0) + x.get("distributionPressure", 0),
                -x.get("mergedContinuationScore", 0),
            ),
            reverse=True,
        )

    return sorted(
        items,
        key=lambda x: x.get("mergedContinuationScore", 0),
        reverse=True,
    )


def compact_item(row):
    return {
        "symbol": row.get("symbol"),
        "decisionGroup": row.get("liveDecisionGroup"),
        "liveMergedState": row.get("liveMergedState"),
        "score": row.get("mergedContinuationScore"),
        "hierarchy": row.get("confirmedHierarchyState"),
        "trajectory": row.get("trajectoryState"),
        "bias": row.get("survivabilityBias"),
        "move": row.get("liveMove"),
        "breakoutPressure": row.get("breakoutPressure"),
        "failurePressure": row.get("failurePressure"),
        "distributionPressure": row.get("distributionPressure"),
    }


def build_board(items):
    grouped = {group: [] for group in BOARD_GROUPS}

    for row in items:
        group = row.get("liveDecisionGroup", "ACTION_NEUTRAL")
        if group not in grouped:
            group = "ACTION_NEUTRAL"

        grouped[group].append(compact_item(row))

    board = {}
    counts = {}

    for group in BOARD_GROUPS:
        sorted_items = sort_group_items(grouped[group], group)
        board[group] = sorted_items
        counts[group] = len(sorted_items)

    return board, counts


def main():
    print("=================================")
    print("📋 BUILD LIVE DECISION BOARD")
    print("=================================")

    data = load_json(INPUT_PATH)
    items = data.get("items", [])

    board, counts = build_board(items)

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceFile": str(INPUT_PATH),
        "totalSymbols": len(items),
        "counts": counts,
        "board": board,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ symbols: {len(items)}")
    print("")
    print("📊 decision board counts:")
    for group in BOARD_GROUPS:
        print(f"  {group}: {counts.get(group, 0)}")

    print("")
    print("🔥 ACTION_WATCH:")
    for row in board["ACTION_WATCH"][:15]:
        print(
            f"  {row['symbol']} | {row['liveMergedState']} | "
            f"score={row['score']} | move={row['move']} | "
            f"traj={row['trajectory']} | bias={row['bias']}"
        )

    print("")
    print("⚠️ ACTION_CAUTION:")
    for row in board["ACTION_CAUTION"][:15]:
        print(
            f"  {row['symbol']} | {row['liveMergedState']} | "
            f"score={row['score']} | move={row['move']} | "
            f"fail={row['failurePressure']} | bias={row['bias']}"
        )

    print("")
    print("🚫 ACTION_RISK_OFF:")
    for row in board["ACTION_RISK_OFF"][:15]:
        print(
            f"  {row['symbol']} | {row['liveMergedState']} | "
            f"score={row['score']} | move={row['move']} | "
            f"fail={row['failurePressure']} | traj={row['trajectory']}"
        )

    print("")
    print(f"💾 saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
