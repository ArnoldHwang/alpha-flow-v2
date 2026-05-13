# src/live/build_live_market_context.py

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

BOARD_PATH = ROOT / "data" / "live_states" / "_live_decision_board.json"
OUTPUT_PATH = ROOT / "data" / "live_states" / "_live_market_context.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def flatten_board(board_data):
    rows = []

    for group, items in board_data.get("board", {}).items():
        if not isinstance(items, list):
            continue

        for row in items:
            if isinstance(row, dict):
                new_row = dict(row)
                new_row["_boardGroup"] = group
                rows.append(new_row)

    return rows


def rebuild_board(board_data, rows):
    board = {}

    for row in rows:
        group = row.get("_boardGroup") or row.get("decisionGroup") or "ACTION_NEUTRAL"

        clean = dict(row)
        clean.pop("_boardGroup", None)

        if group not in board:
            board[group] = []

        board[group].append(clean)

    board_data["board"] = board
    board_data["counts"] = {k: len(v) for k, v in board.items()}
    board_data["marketContextUpdatedAt"] = now_iso()

    return board_data


def detect_market_context(rows):
    if not rows:
        return {
            "marketContinuationEnvironment": "UNKNOWN_MARKET_ENVIRONMENT",
            "marketPressureState": "UNKNOWN_PRESSURE",
            "riskEnvironment": "UNKNOWN_RISK",
            "marketFitBias": "NEUTRAL",
            "marketContextScore": 50.0,
            "marketContextInterpretation": "시장 환경 데이터가 부족하다.",
        }

    confirming = sum(1 for r in rows if r.get("decisionGroup") == "ACTION_CONFIRMING")
    watch = sum(1 for r in rows if r.get("decisionGroup") == "ACTION_WATCH")
    caution = sum(1 for r in rows if r.get("decisionGroup") == "ACTION_CAUTION")
    risk_off = sum(1 for r in rows if r.get("decisionGroup") == "ACTION_RISK_OFF")
    avoid = sum(1 for r in rows if r.get("decisionGroup") == "ACTION_AVOID")

    total = max(len(rows), 1)

    avg_score = sum(safe_float(r.get("score")) for r in rows) / total
    avg_confirmed = sum(safe_float(r.get("confirmedScore")) for r in rows) / total
    avg_failure = sum(safe_float(r.get("failurePressure")) for r in rows) / total
    avg_move = sum(safe_float(r.get("move")) for r in rows) / total

    strong_ratio = (confirming + watch) / total
    weak_ratio = (risk_off + avoid) / total

    score = 50.0
    score += strong_ratio * 35
    score -= weak_ratio * 35
    score += min(max(avg_move, -3), 3) * 4

    if avg_failure >= 55:
        score -= 18
    elif avg_failure >= 45:
        score -= 10
    elif avg_failure <= 35:
        score += 8

    if avg_confirmed >= 70:
        score += 8

    score = max(0.0, min(100.0, round(score, 2)))

    if score >= 75 and strong_ratio >= 0.45:
        continuation_env = "CONTINUATION_FRIENDLY_ENVIRONMENT"
        fit_bias = "FAVORABLE"
        interpretation = "현재 시장은 상승 지속 후보가 많이 살아있는 우호 환경이다."
    elif score >= 60:
        continuation_env = "SELECTIVE_CONTINUATION_ENVIRONMENT"
        fit_bias = "SELECTIVE"
        interpretation = "시장 전체는 나쁘지 않지만 종목별 선별이 필요한 환경이다."
    elif score >= 42:
        continuation_env = "MIXED_MARKET_ENVIRONMENT"
        fit_bias = "NEUTRAL"
        interpretation = "시장 방향성이 섞여 있어 강한 종목만 분리해서 봐야 한다."
    else:
        continuation_env = "CONTINUATION_UNFRIENDLY_ENVIRONMENT"
        fit_bias = "UNFAVORABLE"
        interpretation = (
            "시장 환경이 상승 지속에 불리하다. 좋은 종목도 실패 압력을 크게 봐야 한다."
        )

    if avg_failure >= 55 or weak_ratio >= 0.35:
        pressure_state = "MARKET_UNDER_PRESSURE"
    elif strong_ratio >= 0.45 and avg_move >= 0:
        pressure_state = "MARKET_RECOVERY_PRESSURE_BUILDING"
    else:
        pressure_state = "MARKET_STABLE_PRESSURE"

    if weak_ratio >= 0.35 or avg_failure >= 55:
        risk_env = "RISK_OFF_OR_DISTRIBUTION_ENVIRONMENT"
    elif score >= 70:
        risk_env = "RISK_ON_CONTINUATION_ENVIRONMENT"
    else:
        risk_env = "NEUTRAL_RISK_ENVIRONMENT"

    return {
        "marketContinuationEnvironment": continuation_env,
        "marketPressureState": pressure_state,
        "riskEnvironment": risk_env,
        "marketFitBias": fit_bias,
        "marketContextScore": score,
        "marketContextInterpretation": interpretation,
        "marketStats": {
            "total": total,
            "confirming": confirming,
            "watch": watch,
            "caution": caution,
            "riskOff": risk_off,
            "avoid": avoid,
            "avgScore": round(avg_score, 2),
            "avgConfirmedScore": round(avg_confirmed, 2),
            "avgFailurePressure": round(avg_failure, 2),
            "avgMove": round(avg_move, 2),
            "strongRatio": round(strong_ratio, 4),
            "weakRatio": round(weak_ratio, 4),
        },
    }


def attach_market_context_to_rows(rows, context):
    enriched = []

    for row in rows:
        new_row = dict(row)
        new_row["marketContinuationEnvironment"] = context.get(
            "marketContinuationEnvironment"
        )
        new_row["marketPressureState"] = context.get("marketPressureState")
        new_row["riskEnvironment"] = context.get("riskEnvironment")
        new_row["marketFitBias"] = context.get("marketFitBias")
        new_row["marketContextScore"] = context.get("marketContextScore")
        new_row["marketContextInterpretation"] = context.get(
            "marketContextInterpretation"
        )
        enriched.append(new_row)

    return enriched


def main():
    print("=================================")
    print("🌎 BUILD LIVE MARKET CONTEXT")
    print("=================================")

    board_data = load_json(BOARD_PATH, {})
    if not board_data:
        print(f"❌ board not found: {BOARD_PATH}")
        return

    rows = flatten_board(board_data)
    context = detect_market_context(rows)

    enriched_rows = attach_market_context_to_rows(rows, context)
    board_data = rebuild_board(board_data, enriched_rows)

    board_data["marketContext"] = context

    output = {
        "generatedAt": now_iso(),
        **context,
    }

    save_json(OUTPUT_PATH, output)
    save_json(BOARD_PATH, board_data)

    print(f"✅ market: {context['marketContinuationEnvironment']}")
    print(f"✅ pressure: {context['marketPressureState']}")
    print(f"✅ risk: {context['riskEnvironment']}")
    print(f"✅ score: {context['marketContextScore']}")
    print(f"💾 saved: {OUTPUT_PATH}")
    print(f"💾 board enriched: {BOARD_PATH}")


if __name__ == "__main__":
    main()
