from __future__ import annotations

from collections import Counter
from typing import Any

STABILITY_VERSION = "state-stability-v1.0"


GOOD_STATES = {
    "ELITE_CONTINUATION_STRUCTURE",
    "ELITE_CONTINUATION_STRUCTURE_CONFIRMED_BY_LIVE",
    "CONSTRUCTIVE_PAUSE_STRUCTURE",
    "HEALTHY_BUT_MONTHLY_EXTENDED",
}

RISK_STATES = {
    "DETERIORATING_STRUCTURE",
    "DETERIORATING_STRUCTURE_WITH_LIVE_RISK",
    "TERMINAL_STRUCTURE_RISK",
}

LATE_STATES = {
    "AGING_CONTINUATION_STRUCTURE",
    "LATE_STAGE_REACCELERATION",
    "MIXED_STRUCTURE_LIVE_REACCELERATION_BUT_LATE",
}

NEUTRAL_STATES = {
    "MIXED_STRUCTURE",
}


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default

    text = str(value).strip()

    if text.lower() in {"", "nan", "none", "null"}:
        return default

    return text


def _last_n_states(history: list[dict[str, Any]], n: int) -> list[str]:
    states: list[str] = []

    for row in history[-n:]:
        state = _safe_str(row.get("finalHierarchyState"))
        if state:
            states.append(state)

    return states


def _count_groups(states: list[str]) -> dict[str, int]:
    return {
        "good": sum(1 for state in states if state in GOOD_STATES),
        "risk": sum(1 for state in states if state in RISK_STATES),
        "late": sum(1 for state in states if state in LATE_STATES),
        "neutral": sum(1 for state in states if state in NEUTRAL_STATES),
    }


def _dominant_state(states: list[str]) -> str:
    if not states:
        return "UNKNOWN"

    counter = Counter(states)
    return counter.most_common(1)[0][0]


def build_state_stability(
    current_row: dict[str, Any],
    symbol_history: list[dict[str, Any]],
    short_window: int = 5,
    medium_window: int = 10,
) -> dict[str, Any]:
    """
    상태 안정성 엔진.

    current_row:
        현재 날짜의 hierarchy row.

    symbol_history:
        현재 날짜 이전까지의 같은 symbol hierarchy history.
        중요: 현재 row를 넣기 전 history를 넘겨야 lookahead leakage가 없다.

    short_window:
        최근 5개 확정 row 기준 안정성.

    medium_window:
        최근 10개 확정 row 기준 안정성.
    """

    current_state = _safe_str(current_row.get("finalHierarchyState"), "UNKNOWN")
    current_bias = _safe_str(current_row.get("survivabilityBias"), "NEUTRAL")

    confirmed_history = symbol_history + [current_row]

    short_states = _last_n_states(confirmed_history, short_window)
    medium_states = _last_n_states(confirmed_history, medium_window)

    short_counts = _count_groups(short_states)
    medium_counts = _count_groups(medium_states)

    short_total = max(len(short_states), 1)
    medium_total = max(len(medium_states), 1)

    short_good_rate = short_counts["good"] / short_total
    short_risk_rate = short_counts["risk"] / short_total
    short_late_rate = short_counts["late"] / short_total

    medium_good_rate = medium_counts["good"] / medium_total
    medium_risk_rate = medium_counts["risk"] / medium_total
    medium_late_rate = medium_counts["late"] / medium_total

    dominant_short_state = _dominant_state(short_states)
    dominant_medium_state = _dominant_state(medium_states)

    stability_score = 50.0

    stability_score += short_good_rate * 30
    stability_score += medium_good_rate * 20

    stability_score -= short_risk_rate * 35
    stability_score -= medium_risk_rate * 20

    stability_score -= short_late_rate * 10
    stability_score -= medium_late_rate * 5

    if current_state in GOOD_STATES:
        stability_score += 10

    if current_state in RISK_STATES:
        stability_score -= 20

    if current_state in LATE_STATES:
        stability_score -= 8

    stability_score = max(0.0, min(100.0, round(stability_score, 2)))

    stable_state = current_state
    stable_bias = current_bias
    stability_label = "NORMAL"
    stability_reason = "no_stability_override"

    # 핵심 1:
    # 현재 MIXED지만 최근 5~10일 good 상태가 많으면
    # 단기 노이즈로 보고 완충한다.
    if current_state == "MIXED_STRUCTURE":
        if short_counts["good"] >= 3 and medium_risk_rate < 0.3:
            stable_state = "MIXED_BUT_GOOD_STRUCTURE_HOLDING"
            stable_bias = "GOOD_HOLDING"
            stability_label = "GOOD_STRUCTURE_HOLDING"
            stability_reason = "mixed_current_but_recent_good_persistence"

        elif short_counts["late"] >= 3 and medium_risk_rate < 0.4:
            stable_state = "MIXED_BUT_LATE_STRUCTURE_HOLDING"
            stable_bias = "CAUTION"
            stability_label = "LATE_STRUCTURE_HOLDING"
            stability_reason = "mixed_current_but_recent_late_persistence"

    # 핵심 2:
    # 현재 ELITE인데 최근 good persistence가 약하면
    # 과도한 ELITE 판정을 한 단계 낮춘다.
    elif current_state.startswith("ELITE"):
        if short_counts["good"] < 2:
            stable_state = "ELITE_BUT_UNSTABLE"
            stable_bias = "GOOD_BUT_CONFIRMATION_NEEDED"
            stability_label = "ELITE_UNSTABLE"
            stability_reason = "elite_current_but_weak_recent_good_persistence"

        elif medium_risk_rate >= 0.3:
            stable_state = "ELITE_BUT_RISKY_BACKDROP"
            stable_bias = "CAUTION"
            stability_label = "ELITE_RISKY_BACKDROP"
            stability_reason = "elite_current_but_medium_risk_backdrop"

    # 핵심 3:
    # 현재 DETERIORATING이지만 최근 good 상태가 강하면
    # 바로 AVOID가 아니라 deterioration confirmation 필요로 둔다.
    elif current_state.startswith("DETERIORATING"):
        if short_counts["good"] >= 3 and medium_risk_rate < 0.4:
            stable_state = "DETERIORATING_BUT_GOOD_STRUCTURE_NOT_BROKEN"
            stable_bias = "CAUTION"
            stability_label = "DETERIORATION_NOT_CONFIRMED"
            stability_reason = "deteriorating_current_but_recent_good_persistence"

    # 핵심 4:
    # TERMINAL은 완충하지 않는다.
    # terminal은 위험 우선 원칙.
    elif current_state == "TERMINAL_STRUCTURE_RISK":
        stable_state = current_state
        stable_bias = "AVOID"
        stability_label = "TERMINAL_CONFIRMED"
        stability_reason = "terminal_risk_has_priority"

    return {
        "stabilityVersion": STABILITY_VERSION,
        "stableHierarchyState": stable_state,
        "stableSurvivabilityBias": stable_bias,
        "stateStabilityLabel": stability_label,
        "stateStabilityReason": stability_reason,
        "stateStabilityScore": stability_score,
        "dominantState5d": dominant_short_state,
        "dominantState10d": dominant_medium_state,
        "goodStateCount5d": short_counts["good"],
        "riskStateCount5d": short_counts["risk"],
        "lateStateCount5d": short_counts["late"],
        "goodStateRate5d": round(short_good_rate, 4),
        "riskStateRate5d": round(short_risk_rate, 4),
        "lateStateRate5d": round(short_late_rate, 4),
        "goodStateCount10d": medium_counts["good"],
        "riskStateCount10d": medium_counts["risk"],
        "lateStateCount10d": medium_counts["late"],
        "goodStateRate10d": round(medium_good_rate, 4),
        "riskStateRate10d": round(medium_risk_rate, 4),
        "lateStateRate10d": round(medium_late_rate, 4),
    }
