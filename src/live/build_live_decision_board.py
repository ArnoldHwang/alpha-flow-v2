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


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0.0, high=100.0):
    value = safe_float(value)
    return max(low, min(high, value))


def calc_live_adjusted_score(row):
    """
    confirmed 구조 중심.
    live pressure는 보조 가중치.

    목표:
    continuation survivability 기반은 유지하면서
    장중 deterioration만 적당히 반영.
    """

    confirmed_score = safe_float(row.get("mergedContinuationScore"))

    live_move = safe_float(row.get("liveMove"))
    breakout = safe_float(row.get("breakoutPressure"))
    failure = safe_float(row.get("failurePressure"))
    distribution = safe_float(row.get("distributionPressure"))

    live_state = row.get("liveMergedState") or ""
    group = row.get("liveDecisionGroup") or "ACTION_NEUTRAL"

    # =========================
    # 핵심:
    # confirmed survivability 중심
    # =========================
    score = confirmed_score

    # =========================
    # move 영향 축소
    # =========================
    if live_move >= 5:
        score += 12
    elif live_move >= 3:
        score += 8
    elif live_move >= 1.5:
        score += 5
    elif live_move >= 0.5:
        score += 2
    elif live_move > -0.5:
        score -= 1
    elif live_move > -1.5:
        score -= 3
    elif live_move > -3:
        score -= 6
    else:
        score -= 10

    # =========================
    # breakout pressure
    # =========================
    if breakout >= 70:
        score += 5
    elif breakout >= 55:
        score += 3
    elif breakout < 40:
        score -= 3

    # =========================
    # failure / distribution
    # =========================
    if failure >= 70:
        score -= 20
    elif failure >= 60:
        score -= 14
    elif failure >= 50:
        score -= 8
    elif failure >= 45:
        score -= 4

    if distribution >= 50:
        score -= 14
    elif distribution >= 35:
        score -= 8
    elif distribution >= 20:
        score -= 4

    # =========================
    # live state
    # =========================
    if live_state == "LIVE_RECOVERY_EXTENSION_WATCH":
        score += 4

    elif live_state == "LIVE_RECOVERY_WATCHLIST":
        score += 2

    elif live_state == "LIVE_RECOVERY_UNDER_PRESSURE":
        score -= 6

    elif live_state == "LIVE_RECOVERY_FAILING_INTRADAY":
        score -= 14

    elif live_state == "LIVE_BREAKDOWN_CONFIRMING":
        score -= 22

    elif live_state == "LIVE_DISTRIBUTION_CONTINUATION":
        score -= 16

    # =========================
    # group
    # =========================
    if group == "ACTION_CONFIRMING":
        score += 4

    elif group == "ACTION_CAUTION":
        score -= 3

    elif group in {"ACTION_RISK_OFF", "ACTION_AVOID"}:
        score -= 10

    elif group == "ACTION_NEUTRAL":
        score -= 5

    # =========================
    # 과대평가 방지
    # =========================
    if live_move < 0:
        score = min(score, 88)

    if failure >= 50:
        score = min(score, 86)

    if group in {"ACTION_RISK_OFF", "ACTION_AVOID"}:
        score = min(score, 70)

    return round(clamp(score), 2)


def sort_group_items(items, group):
    if group in {"ACTION_CONFIRMING", "ACTION_WATCH"}:
        return sorted(
            items,
            key=lambda x: (
                x.get("score", 0),
                x.get("move", 0),
                -x.get("failurePressure", 0),
            ),
            reverse=True,
        )

    if group == "ACTION_CAUTION":
        return sorted(
            items,
            key=lambda x: (
                x.get("score", 0),
                -x.get("failurePressure", 0),
            ),
            reverse=True,
        )

    if group in {"ACTION_RISK_OFF", "ACTION_AVOID"}:
        return sorted(
            items,
            key=lambda x: (
                x.get("failurePressure", 0) + x.get("distributionPressure", 0),
                -x.get("score", 0),
            ),
            reverse=True,
        )

    return sorted(
        items,
        key=lambda x: x.get("score", 0),
        reverse=True,
    )


def compact_item(row):
    confirmed_score = row.get("mergedContinuationScore")
    live_adjusted_score = calc_live_adjusted_score(row)

    return {
        "symbol": row.get("symbol"),
        "decisionGroup": row.get("liveDecisionGroup"),
        "liveMergedState": row.get("liveMergedState"),
        # 중요:
        # confirmedScore = 구조 점수
        # score = live 화면 표시용 보정 점수
        "confirmedScore": confirmed_score,
        "score": live_adjusted_score,
        "hierarchy": row.get("confirmedHierarchyState"),
        "trajectory": row.get("trajectoryState"),
        "bias": row.get("survivabilityBias"),
        # V2 survivability interpretation
        # riskProfile = 위험 성격
        # expectancyProfile = 어떤 시간축 기대값이 강한가
        # continuationProfile = continuation이 아직 살아있는지
        "survivabilityScore": row.get("continuationSurvivabilityScore"),
        "failureRisk": row.get("continuationFailureRisk"),
        "riskProfile": row.get("riskProfile"),
        "expectancyProfile": row.get("expectancyProfile"),
        "continuationProfile": row.get("continuationProfile"),
        "survivabilityInterpretation": row.get("survivabilityInterpretation"),
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
            f"score={row['score']} | confirmed={row['confirmedScore']} | "
            f"surv={row.get('survivabilityScore')} | "
            f"move={row['move']} | fail={row['failurePressure']} | "
            f"traj={row['trajectory']} | "
            f"profile={row.get('continuationProfile')}"
        )

    print("")
    print("⚠️ ACTION_CAUTION:")
    for row in board["ACTION_CAUTION"][:15]:
        print(
            f"  {row['symbol']} | {row['liveMergedState']} | "
            f"score={row['score']} | confirmed={row['confirmedScore']} | "
            f"move={row['move']} | fail={row['failurePressure']} | "
            f"bias={row['bias']}"
        )

    print("")
    print("🚫 ACTION_RISK_OFF:")
    for row in board["ACTION_RISK_OFF"][:15]:
        print(
            f"  {row['symbol']} | {row['liveMergedState']} | "
            f"score={row['score']} | confirmed={row['confirmedScore']} | "
            f"move={row['move']} | fail={row['failurePressure']} | "
            f"traj={row['trajectory']}"
        )

    print("")
    print(f"💾 saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
