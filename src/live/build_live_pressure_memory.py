# src/live/build_live_pressure_memory.py

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

BOARD_PATH = ROOT / "data" / "live_states" / "_live_decision_board.json"
MEMORY_PATH = ROOT / "data" / "live_states" / "_live_pressure_memory.json"

MAX_MEMORY_PER_SYMBOL = 60


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_str(value, default=""):
    if value is None:
        return default
    return str(value)


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def flatten_board(board_data):
    board = board_data.get("board", {})
    rows = []

    if isinstance(board, dict):
        for group, group_rows in board.items():
            if not isinstance(group_rows, list):
                continue

            for row in group_rows:
                if isinstance(row, dict):
                    new_row = dict(row)
                    new_row["_boardGroup"] = group
                    rows.append(new_row)

    return rows


def rebuild_board(board_data, rows):
    new_board = {}

    for row in rows:
        group = row.get("_boardGroup") or row.get("decisionGroup") or "ACTION_NEUTRAL"

        clean_row = dict(row)
        clean_row.pop("_boardGroup", None)

        if group not in new_board:
            new_board[group] = []

        new_board[group].append(clean_row)

    board_data["board"] = new_board
    board_data["counts"] = {group: len(items) for group, items in new_board.items()}

    board_data["memoryUpdatedAt"] = now_iso()
    board_data["memoryPath"] = str(MEMORY_PATH)

    return board_data


def build_memory_point(row, board_generated_at):
    return {
        "time": now_iso(),
        "boardGeneratedAt": board_generated_at,
        "symbol": safe_str(row.get("symbol")),
        # live state
        "liveMergedState": safe_str(
            row.get("liveMergedState"),
            "LIVE_NEUTRAL",
        ),
        "decisionGroup": safe_str(
            row.get("decisionGroup") or row.get("_boardGroup"),
            "ACTION_NEUTRAL",
        ),
        # board score
        "score": safe_float(row.get("score")),
        "move": safe_float(row.get("move")),
        "failurePressure": safe_float(row.get("failurePressure")),
        # optional live fields
        "livePressureScore": safe_float(row.get("livePressureScore", row.get("score"))),
        "priceChangePct": safe_float(row.get("priceChangePct", row.get("move"))),
        "volumePressure": safe_float(row.get("volumePressure")),
        # confirmed context
        "trajectoryType": safe_str(
            row.get("trajectoryType"),
            "NEUTRAL_TRAJECTORY",
        ),
        "finalHierarchyState": safe_str(
            row.get("finalHierarchyState"),
            "MIXED_STRUCTURE",
        ),
        "survivabilityBias": safe_str(
            row.get("survivabilityBias"),
            "NEUTRAL",
        ),
    }


def summarize_symbol_pressure(symbol_memory):
    if not symbol_memory:
        return {
            "livePressureTrend": "NO_MEMORY",
            "livePressureDelta": 0.0,
            "recentStatePath": "",
            "recentDecisionPath": "",
            "memoryCount": 0,
            "recoveryPersistenceCount": 0,
            "deteriorationPersistenceCount": 0,
        }

    recent = symbol_memory[-5:]

    first_score = safe_float(recent[0].get("livePressureScore"))
    last_score = safe_float(recent[-1].get("livePressureScore"))
    delta = round(last_score - first_score, 4)

    states = [safe_str(x.get("liveMergedState"), "LIVE_NEUTRAL") for x in recent]
    decisions = [safe_str(x.get("decisionGroup"), "ACTION_NEUTRAL") for x in recent]

    bad_states = {
        "LIVE_RECOVERY_UNDER_PRESSURE",
        "LIVE_RECOVERY_FAILING_INTRADAY",
        "LIVE_BREAKDOWN_CONFIRMING",
        "LIVE_DISTRIBUTION_CONTINUATION",
    }

    good_states = {
        "LIVE_RECOVERY_WATCHLIST",
        "LIVE_RECOVERY_EXTENSION_WATCH",
        "LIVE_REACCELERATION_CONFIRMING",
        "LIVE_CONTINUATION_HOLDING",
    }

    recent_bad_count = sum(1 for s in states if s in bad_states)
    recent_good_count = sum(1 for s in states if s in good_states)

    # 최근 흐름 기준 연속 recovery count
    recovery_persistence_count = 0
    for s in reversed(states):
        if s in good_states:
            recovery_persistence_count += 1
        else:
            break

    # 최근 흐름 기준 연속 deterioration count
    deterioration_persistence_count = 0
    for s in reversed(states):
        if s in bad_states:
            deterioration_persistence_count += 1
        else:
            break

    if deterioration_persistence_count >= 3:
        trend = "DETERIORATION_PERSISTING"
    elif recovery_persistence_count >= 3 and delta >= 0:
        trend = "RECOVERY_PRESSURE_BUILDING"
    elif recent_bad_count >= 3:
        trend = "DETERIORATION_CLUSTER"
    elif recent_good_count >= 3 and delta >= 0:
        trend = "RECOVERY_CLUSTER"
    elif delta >= 10:
        trend = "IMPROVING_PRESSURE"
    elif delta <= -10:
        trend = "DETERIORATING_PRESSURE"
    elif last_score >= 70:
        trend = "PERSISTENT_STRONG_PRESSURE"
    elif last_score <= 35:
        trend = "PERSISTENT_WEAK_PRESSURE"
    else:
        trend = "STABLE_PRESSURE"

    return {
        "livePressureTrend": trend,
        "livePressureDelta": delta,
        "recentStatePath": " -> ".join(states),
        "recentDecisionPath": " -> ".join(decisions),
        "memoryCount": len(symbol_memory),
        "recoveryPersistenceCount": recovery_persistence_count,
        "deteriorationPersistenceCount": deterioration_persistence_count,
    }


def main():
    print("=================================")
    print("🧠 LIVE PRESSURE MEMORY")
    print("=================================")

    board_data = load_json(BOARD_PATH, {})
    if not board_data:
        print(f"❌ board not found: {BOARD_PATH}")
        return

    rows = flatten_board(board_data)
    if not rows:
        print("⚠️ board rows empty")
        return

    memory = load_json(MEMORY_PATH, {})

    for row in rows:
        symbol = safe_str(row.get("symbol"))
        if not symbol:
            continue

        point = build_memory_point(
            row,
            board_data.get("generatedAt"),
        )

        existing = memory.get(symbol, [])

        # 같은 board generatedAt이면 중복 저장 금지
        if existing:
            last_point = existing[-1]

            if last_point.get("boardGeneratedAt") == point.get("boardGeneratedAt"):
                continue

        if symbol not in memory:
            memory[symbol] = []

        memory[symbol].append(point)
        memory[symbol] = memory[symbol][-MAX_MEMORY_PER_SYMBOL:]

    enriched_rows = []

    for row in rows:
        symbol = safe_str(row.get("symbol"))
        summary = summarize_symbol_pressure(memory.get(symbol, []))

        new_row = dict(row)
        new_row.update(summary)

        enriched_rows.append(new_row)

    board_data = rebuild_board(board_data, enriched_rows)

    save_json(MEMORY_PATH, memory)
    save_json(BOARD_PATH, board_data)

    print(f"✅ memory saved: {MEMORY_PATH}")
    print(f"✅ board enriched: {BOARD_PATH}")
    print(f"symbols: {len(memory)}")
    print(f"rows: {len(rows)}")


if __name__ == "__main__":
    main()
