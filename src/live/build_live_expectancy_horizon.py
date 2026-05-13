# src/live/build_live_expectancy_horizon.py


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def attach_live_expectancy_horizon(items):
    output = []

    for row in items:
        new_row = dict(row)
        new_row.update(classify_expectancy_horizon(new_row))
        output.append(new_row)

    return output


def grade(score):
    if score >= 80:
        return "VERY_HIGH"
    if score >= 65:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    if score >= 35:
        return "LOW"
    return "VERY_LOW"


def classify_expectancy_horizon(row):
    trajectory = str(row.get("trajectoryState") or "")
    hierarchy = str(row.get("confirmedHierarchyState") or "")
    profile = str(row.get("continuationProfile") or "")
    curve = str(row.get("expectancyCurveCluster") or "")
    action = str(row.get("preferredAction") or "")
    stage = str(row.get("continuationStage") or "")
    high_position = str(row.get("highPositionCategory") or "")

    confirmed = safe_float(row.get("confirmedContinuationScore"))
    live_move = safe_float(row.get("liveMove"))
    failure = safe_float(row.get("failurePressure"))
    distribution = safe_float(row.get("distributionPressure"))
    survivability = safe_float(row.get("continuationSurvivabilityScore"))
    recovery_count = safe_float(row.get("recoveryPersistenceCount"))
    deterioration_count = safe_float(row.get("deteriorationPersistenceCount"))

    short_score = 45.0
    swing_score = 45.0
    mid_score = 45.0

    # 단기: 장중 힘, 재가속, recovery에 민감
    if confirmed >= 85:
        short_score += 12
    if live_move >= 2:
        short_score += 16
    elif live_move >= 1:
        short_score += 10
    if "RECOVERY" in trajectory or "REACCELERATION" in trajectory:
        short_score += 14
    if recovery_count >= 2:
        short_score += 8
    if curve in {"FAST_IGNITION_SHORT_SWING", "BURST_AND_FADE"}:
        short_score += 12
    if action in {"SHORT_SWING_FAST_PROFIT", "DAY1_TO_DAY5_ONLY"}:
        short_score += 10

    # 스윙: 구조 + 실패압력 + 3~20일 기대 곡선
    if confirmed >= 80:
        swing_score += 12
    if survivability >= 55:
        swing_score += 12
    if failure <= 45:
        swing_score += 10
    elif failure >= 55:
        swing_score -= 14
    if distribution <= 25:
        swing_score += 8
    if curve in {
        "HIGH_QUALITY_SWING_CONTINUATION",
        "IGNITION_TO_SWING_CONTINUATION",
        "MIDTERM_SWING_EXPANSION",
        "DELAYED_SWING_ACCELERATION",
    }:
        swing_score += 18
    if "RECOVERY" in trajectory:
        swing_score += 8

    # 중기: survivability, hierarchy, 낮은 실패압력, 기관형 drift에 민감
    if survivability >= 70:
        mid_score += 22
    elif survivability >= 55:
        mid_score += 12
    elif survivability < 45:
        mid_score -= 18

    if "ELITE_CONTINUATION" in hierarchy or "HEALTHY" in hierarchy:
        mid_score += 14
    if "AGING" in hierarchy or "TERMINAL" in hierarchy or "LATE_STAGE" in hierarchy:
        mid_score -= 18
    if failure <= 40:
        mid_score += 10
    elif failure >= 50:
        mid_score -= 14
    if distribution >= 35:
        mid_score -= 12
    if curve in {
        "INSTITUTIONAL_DRIFT_CONTINUATION",
        "SLOW_COMPOUNDING_CONTINUATION",
        "LONG_TAIL_CONTINUATION",
    }:
        mid_score += 18
    if profile == "LOW_SURVIVABILITY_STRUCTURE":
        mid_score -= 14

    # 위치 리스크 보정
    if high_position in {"TERMINAL_OR_DANGEROUS_HIGH", "DISTRIBUTION_HIGH_RISK"}:
        short_score -= 8
        swing_score -= 16
        mid_score -= 22

    if high_position == "TACTICAL_FAST_SWING_HIGH":
        short_score += 12
        swing_score -= 8
        mid_score -= 16

    if high_position == "INSTITUTIONAL_HIGH_CONTINUATION":
        swing_score += 8
        mid_score += 16

    if deterioration_count >= 2:
        short_score -= 10
        swing_score -= 14
        mid_score -= 16

    short_score = max(0.0, min(100.0, round(short_score, 2)))
    swing_score = max(0.0, min(100.0, round(swing_score, 2)))
    mid_score = max(0.0, min(100.0, round(mid_score, 2)))

    scores = {
        "SHORT_TERM": short_score,
        "SWING": swing_score,
        "MID_TERM": mid_score,
    }

    best = max(scores, key=scores.get)

    if best == "SHORT_TERM":
        label = "TACTICAL_SHORT_TERM_BURST"
        text = "단기 장중/1~3일 momentum 기대가 가장 강한 상태"
    elif best == "SWING":
        label = "SWING_CONTINUATION_SETUP"
        text = "3~20일 스윙 continuation 기대가 상대적으로 강한 상태"
    else:
        label = "MID_TERM_SURVIVABILITY_SETUP"
        text = "20~60일 중기 survivability 기대가 상대적으로 강한 상태"

    return {
        "shortTermExpectancyScore": short_score,
        "swingExpectancyScore": swing_score,
        "midTermExpectancyScore": mid_score,
        "shortTermExpectancyGrade": grade(short_score),
        "swingExpectancyGrade": grade(swing_score),
        "midTermExpectancyGrade": grade(mid_score),
        "dominantExpectancyHorizon": label,
        "dominantExpectancyText": text,
    }
