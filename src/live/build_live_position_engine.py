# src/live/build_live_position_engine.py


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def attach_live_position_engine(items):
    output = []

    for row in items:
        new_row = dict(row)
        new_row.update(classify_live_position(new_row))
        output.append(new_row)

    return output


def classify_live_position(row):
    hierarchy = str(row.get("confirmedHierarchyState") or "")
    trajectory = str(row.get("trajectoryState") or "")
    bias = str(row.get("survivabilityBias") or "")
    profile = str(row.get("continuationProfile") or "")
    curve = str(row.get("expectancyCurveCluster") or "")
    action = str(row.get("preferredAction") or "")

    score = safe_float(row.get("confirmedContinuationScore"))
    live_move = safe_float(row.get("liveMove"))
    failure = safe_float(row.get("failurePressure"))
    distribution = safe_float(row.get("distributionPressure"))
    survivability = safe_float(row.get("continuationSurvivabilityScore"))

    high_position_category = "MIXED_HIGH_POSITION"
    entry_timing_state = "WAIT_FOR_CONFIRMATION"
    continuation_stage = "MID_CONTINUATION"

    # 위험 후반부
    if (
        "TERMINAL" in hierarchy
        or "LATE_STAGE" in hierarchy
        or "BREAKDOWN" in trajectory
        or failure >= 65
    ):
        high_position_category = "TERMINAL_OR_DANGEROUS_HIGH"
        entry_timing_state = "DO_NOT_CHASE"
        continuation_stage = "LATE_STAGE_EXHAUSTION"

    # 매물 증가형 고점
    elif (
        "DISTRIBUTION" in hierarchy
        or "DISTRIBUTION" in trajectory
        or distribution >= 40
    ):
        high_position_category = "DISTRIBUTION_HIGH_RISK"
        entry_timing_state = "WAIT_FOR_PULLBACK_RECLAIM"
        continuation_stage = "DISTRIBUTION_PHASE"

    # 월봉 부담 있지만 살아있는 고점
    elif "MONTHLY_EXTENDED" in hierarchy or bias == "GOOD_BUT_EXTENSION_RISK":
        high_position_category = "HEALTHY_BUT_EXTENDED_HIGH"
        entry_timing_state = "SMALL_SIZE_OR_PULLBACK_ONLY"
        continuation_stage = "EXTENDED_CONTINUATION"

    # 기관형 좋은 고점
    elif (
        survivability >= 70
        and score >= 75
        and failure <= 45
        and distribution <= 30
        and (
            "INSTITUTIONAL" in curve
            or "DRIFT" in curve
            or "ALIVE" in profile
            or "ELITE" in hierarchy
        )
    ):
        high_position_category = "INSTITUTIONAL_HIGH_CONTINUATION"
        entry_timing_state = "TREND_FOLLOW_WITH_RISK_CONTROL"
        continuation_stage = "HEALTHY_CONTINUATION"

    # 조정 후 재가속
    elif "RECOVERY" in trajectory and "ALIVE" in profile and failure <= 50:
        high_position_category = "RECOVERY_REACCELERATION_HIGH"
        entry_timing_state = "WATCH_REACCELERATION_CONFIRMATION"
        continuation_stage = "REACCELERATION_PHASE"

    # 빠른 단기 스윙형
    elif curve in {
        "FAST_IGNITION_SHORT_SWING",
        "BURST_AND_FADE",
        "TACTICAL_SWING_THEN_DECAY",
    } or action in {
        "SHORT_SWING_FAST_PROFIT",
        "DAY1_TO_DAY5_ONLY",
    }:
        high_position_category = "TACTICAL_FAST_SWING_HIGH"
        entry_timing_state = "SHORT_TERM_ONLY"
        continuation_stage = "TACTICAL_MOMENTUM_PHASE"

    # 낮은 위치 또는 판단 부족
    elif score < 60 or survivability < 45:
        high_position_category = "UNPROVEN_POSITION"
        entry_timing_state = "RESEARCH_ONLY"
        continuation_stage = "UNCONFIRMED_STRUCTURE"

    # 장중 강하지만 추격 주의
    if live_move >= 5 and high_position_category not in {
        "INSTITUTIONAL_HIGH_CONTINUATION",
        "RECOVERY_REACCELERATION_HIGH",
    }:
        entry_timing_state = "DO_NOT_CHASE_SPIKE"

    return {
        "highPositionCategory": high_position_category,
        "entryTimingState": entry_timing_state,
        "continuationStage": continuation_stage,
    }
