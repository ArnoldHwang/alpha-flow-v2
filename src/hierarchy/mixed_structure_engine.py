from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except Exception:
        return default


def classify_mixed_structure(row: dict) -> dict:
    """
    MIXED 구조 세분화 엔진.

    핵심:
    MIXED를 단순 중립 상태로 두지 않고
    continuation lifecycle 중 어디에 위치하는지 압축한다.
    """

    final_state = str(row.get("finalHierarchyState", ""))

    if "MIXED" not in final_state:
        return {
            "mixedSubtype": None,
            "mixedBias": None,
        }

    monthly_state = str(row.get("monthlyConfirmedContinuationState", ""))

    weekly_state = str(row.get("weeklyConfirmedContinuationState", ""))

    daily_state = str(row.get("dailyContinuationState", ""))

    stability_score = _safe_float(row.get("stateStabilityScore", 50))

    good_rate_5d = _safe_float(row.get("goodStateRate5d", 0))

    risk_rate_5d = _safe_float(row.get("riskStateRate5d", 0))

    # =====================================
    # GOOD MIXED
    # =====================================

    if (
        monthly_state
        in [
            "HEALTHY_CONTINUATION",
            "BASE_BUILDING",
        ]
        and weekly_state
        in [
            "HEALTHY_PULLBACK",
            "BASE_BUILDING",
            "PAUSE_OR_PULLBACK",
        ]
        and daily_state
        in [
            "HEALTHY_PULLBACK",
            "BASE_BUILDING",
            "RE_ACCELERATING_CONTINUATION",
        ]
        and stability_score >= 60
    ):
        return {
            "mixedSubtype": "MIXED_REACCUMULATION",
            "mixedBias": "GOOD",
        }

    # =====================================
    # RECOVERY MIXED
    # =====================================

    if (
        weekly_state == "DETERIORATING"
        and daily_state
        in [
            "BASE_BUILDING",
            "RE_ACCELERATING_CONTINUATION",
        ]
        and good_rate_5d >= 0.4
    ):
        return {
            "mixedSubtype": "MIXED_RECOVERY_ATTEMPT",
            "mixedBias": "TACTICAL",
        }

    # =====================================
    # LATE MIXED
    # =====================================

    if monthly_state == "LATE_STAGE_CONTINUATION" and weekly_state in [
        "HEALTHY_CONTINUATION",
        "RE_ACCELERATING_CONTINUATION",
    ]:
        return {
            "mixedSubtype": "MIXED_LATE_STAGE",
            "mixedBias": "CAUTION",
        }

    # =====================================
    # DISTRIBUTION MIXED
    # =====================================

    if (
        weekly_state == "DETERIORATING"
        and daily_state == "DETERIORATING"
        and risk_rate_5d >= 0.6
    ):
        return {
            "mixedSubtype": "MIXED_DISTRIBUTION",
            "mixedBias": "AVOID",
        }

    # =====================================
    # TRANSITION MIXED
    # =====================================

    return {
        "mixedSubtype": "MIXED_TRANSITION",
        "mixedBias": "NEUTRAL",
    }
