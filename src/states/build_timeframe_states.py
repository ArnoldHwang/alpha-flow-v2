import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_DATA_PATH = "data/states"
HIERARCHY_DATA_PATH = "data/hierarchy"

HIERARCHY_VERSION = "hierarchy-state-v2.1-leak-safe"


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, rows):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def get_latest_confirmed_asof(rows, target_date):
    candidates = []

    for row in rows:
        if not row.get("isComplete"):
            continue

        if row.get("date") <= target_date:
            candidates.append(row)

    if not candidates:
        return None

    return candidates[-1]


def get_live_asof(rows, target_date):
    """
    as-of live:
    target_date 기준으로 알 수 있었던 진행 중 weekly/monthly 봉만 사용.

    예:
    2026-05-11 daily 판단
    → 2026-05-11 monthly live 사용 가능

    2021-01-04 daily 판단
    → 2026-05 monthly live 사용 불가
    """
    candidates = []

    for row in rows:
        if row.get("isComplete"):
            continue

        start = row.get("candleStart")
        end = row.get("candleEnd")

        if not start or not end:
            continue

        if start <= target_date <= end:
            candidates.append(row)

    if not candidates:
        return None

    return candidates[-1]


def classify_hierarchy_base(monthly, weekly, daily):
    monthly_state = monthly.get("continuationState") if monthly else "UNKNOWN"
    weekly_state = weekly.get("continuationState") if weekly else "UNKNOWN"
    daily_state = daily.get("continuationState") if daily else "UNKNOWN"

    if monthly_state == "TERMINAL_RISK" or weekly_state == "TERMINAL_RISK":
        return "TERMINAL_STRUCTURE_RISK"

    if (
        monthly_state == "LATE_STAGE_CONTINUATION"
        and weekly_state == "LATE_STAGE_CONTINUATION"
    ):
        return "AGING_CONTINUATION_STRUCTURE"

    if (
        monthly_state in ["HEALTHY_CONTINUATION", "BASE_BUILDING", "HEALTHY_PULLBACK"]
        and weekly_state
        in ["HEALTHY_CONTINUATION", "BASE_BUILDING", "HEALTHY_PULLBACK"]
        and daily_state in ["HEALTHY_CONTINUATION", "RE_ACCELERATING_CONTINUATION"]
    ):
        return "ELITE_CONTINUATION_STRUCTURE"

    if (
        monthly_state in ["HEALTHY_CONTINUATION", "LATE_STAGE_CONTINUATION"]
        and weekly_state == "HEALTHY_CONTINUATION"
        and daily_state in ["HEALTHY_CONTINUATION", "RE_ACCELERATING_CONTINUATION"]
    ):
        return "HEALTHY_BUT_MONTHLY_EXTENDED"

    if (
        monthly_state in ["HEALTHY_CONTINUATION", "BASE_BUILDING"]
        and weekly_state in ["PAUSE_OR_PULLBACK", "HEALTHY_PULLBACK", "BASE_BUILDING"]
        and daily_state in ["BASE_BUILDING", "HEALTHY_PULLBACK", "PAUSE_OR_PULLBACK"]
    ):
        return "CONSTRUCTIVE_PAUSE_STRUCTURE"

    if weekly_state == "DETERIORATING" or daily_state == "DETERIORATING":
        return "DETERIORATING_STRUCTURE"

    if monthly_state == "LATE_STAGE_CONTINUATION" and daily_state in [
        "RE_ACCELERATING_CONTINUATION",
        "HEALTHY_CONTINUATION",
    ]:
        return "LATE_STAGE_REACCELERATION"

    return "MIXED_STRUCTURE"


def classify_live_adjustment(base_state, monthly_live, weekly_live):
    monthly_live_state = monthly_live.get("continuationState") if monthly_live else None
    weekly_live_state = weekly_live.get("continuationState") if weekly_live else None

    risk_states = ["TERMINAL_RISK", "DETERIORATING"]
    strong_states = ["HEALTHY_CONTINUATION", "RE_ACCELERATING_CONTINUATION"]

    if monthly_live_state in risk_states or weekly_live_state in risk_states:
        return "LIVE_RISK_DOWNGRADE"

    if weekly_live_state in strong_states and base_state in [
        "ELITE_CONTINUATION_STRUCTURE",
        "CONSTRUCTIVE_PAUSE_STRUCTURE",
        "HEALTHY_BUT_MONTHLY_EXTENDED",
    ]:
        return "LIVE_CONFIRMATION"

    if (
        monthly_live_state == "LATE_STAGE_CONTINUATION"
        and weekly_live_state in strong_states
    ):
        return "LIVE_STRONG_BUT_LATE"

    return "NO_LIVE_ADJUSTMENT"


def build_final_hierarchy_state(base_state, live_adjustment):
    if live_adjustment == "LIVE_RISK_DOWNGRADE":
        return f"{base_state}_WITH_LIVE_RISK"

    if live_adjustment == "LIVE_CONFIRMATION":
        return f"{base_state}_CONFIRMED_BY_LIVE"

    if live_adjustment == "LIVE_STRONG_BUT_LATE":
        return f"{base_state}_LIVE_REACCELERATION_BUT_LATE"

    return base_state


def build_survivability_bias(final_state):
    if "LIVE_RISK" in final_state:
        return "REDUCE_RISK"

    if final_state.startswith("ELITE_CONTINUATION_STRUCTURE"):
        return "HIGH"

    if final_state.startswith("CONSTRUCTIVE_PAUSE_STRUCTURE"):
        return "GOOD"

    if final_state.startswith("HEALTHY_BUT_MONTHLY_EXTENDED"):
        return "GOOD_BUT_EXTENSION_RISK"

    if final_state.startswith("LATE_STAGE_REACCELERATION"):
        return "TACTICAL_ONLY"

    if final_state.startswith("AGING_CONTINUATION_STRUCTURE"):
        return "CAUTION"

    if final_state.startswith("DETERIORATING_STRUCTURE"):
        return "AVOID"

    if final_state.startswith("TERMINAL_STRUCTURE_RISK"):
        return "AVOID"

    return "NEUTRAL"


def build_hierarchy_row(
    symbol,
    daily_row,
    weekly_confirmed,
    monthly_confirmed,
    weekly_live,
    monthly_live,
):
    now_iso = datetime.now(timezone.utc).isoformat()

    base_state = classify_hierarchy_base(
        monthly_confirmed,
        weekly_confirmed,
        daily_row,
    )

    live_adjustment = classify_live_adjustment(
        base_state,
        monthly_live,
        weekly_live,
    )

    final_state = build_final_hierarchy_state(
        base_state,
        live_adjustment,
    )

    survivability_bias = build_survivability_bias(final_state)

    return {
        "symbol": symbol,
        "date": daily_row.get("date"),
        "dailyDate": daily_row.get("date"),
        "weeklyConfirmedDate": (
            weekly_confirmed.get("date") if weekly_confirmed else None
        ),
        "monthlyConfirmedDate": (
            monthly_confirmed.get("date") if monthly_confirmed else None
        ),
        "weeklyLiveDate": weekly_live.get("date") if weekly_live else None,
        "monthlyLiveDate": monthly_live.get("date") if monthly_live else None,
        "assetType": daily_row.get("assetType"),
        "sector": daily_row.get("sector"),
        "themes": daily_row.get("themes", []),
        "betaType": daily_row.get("betaType"),
        "marketCapGroup": daily_row.get("marketCapGroup"),
        "dailyContinuationState": daily_row.get("continuationState"),
        "weeklyConfirmedContinuationState": (
            weekly_confirmed.get("continuationState") if weekly_confirmed else None
        ),
        "monthlyConfirmedContinuationState": (
            monthly_confirmed.get("continuationState") if monthly_confirmed else None
        ),
        "weeklyLiveContinuationState": (
            weekly_live.get("continuationState") if weekly_live else None
        ),
        "monthlyLiveContinuationState": (
            monthly_live.get("continuationState") if monthly_live else None
        ),
        "dailyTrendState": daily_row.get("trendState"),
        "weeklyTrendState": (
            weekly_confirmed.get("trendState") if weekly_confirmed else None
        ),
        "monthlyTrendState": (
            monthly_confirmed.get("trendState") if monthly_confirmed else None
        ),
        "dailyExhaustionState": daily_row.get("exhaustionState"),
        "weeklyExhaustionState": (
            weekly_confirmed.get("exhaustionState") if weekly_confirmed else None
        ),
        "monthlyExhaustionState": (
            monthly_confirmed.get("exhaustionState") if monthly_confirmed else None
        ),
        "hierarchyBaseState": base_state,
        "liveAdjustmentState": live_adjustment,
        "finalHierarchyState": final_state,
        "survivabilityBias": survivability_bias,
        "hierarchyVersion": HIERARCHY_VERSION,
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }


def process_symbol(file_name):
    symbol = file_name.replace(".json", "")

    daily_path = os.path.join(STATE_DATA_PATH, "daily", file_name)
    weekly_path = os.path.join(STATE_DATA_PATH, "weekly", file_name)
    monthly_path = os.path.join(STATE_DATA_PATH, "monthly", file_name)

    if not os.path.exists(weekly_path) or not os.path.exists(monthly_path):
        print(f"⚠️ missing weekly/monthly for {symbol}")
        return

    daily_rows = load_json(daily_path)
    weekly_rows = load_json(weekly_path)
    monthly_rows = load_json(monthly_path)

    hierarchy_rows = []

    for daily_row in daily_rows:
        if not daily_row.get("isComplete"):
            continue

        target_date = daily_row.get("date")

        weekly_confirmed = get_latest_confirmed_asof(weekly_rows, target_date)
        monthly_confirmed = get_latest_confirmed_asof(monthly_rows, target_date)

        weekly_live = get_live_asof(weekly_rows, target_date)
        monthly_live = get_live_asof(monthly_rows, target_date)

        if not weekly_confirmed or not monthly_confirmed:
            continue

        hierarchy_rows.append(
            build_hierarchy_row(
                symbol=symbol,
                daily_row=daily_row,
                weekly_confirmed=weekly_confirmed,
                monthly_confirmed=monthly_confirmed,
                weekly_live=weekly_live,
                monthly_live=monthly_live,
            )
        )

    save_path = os.path.join(HIERARCHY_DATA_PATH, f"{symbol}.json")
    save_json(save_path, hierarchy_rows)

    print(f"✅ {symbol} | hierarchy rows: {len(hierarchy_rows)}")


def main():
    print("=================================")
    print("🧠 ALPHA-FLOW V2 BUILD HIERARCHY STATES")
    print("=================================")

    daily_folder = os.path.join(STATE_DATA_PATH, "daily")

    files = [f for f in os.listdir(daily_folder) if f.endswith(".json")]

    for file_name in files:
        process_symbol(file_name)

    print("")
    print("=================================")
    print("✅ HIERARCHY BUILD COMPLETE")
    print("=================================")


if __name__ == "__main__":
    main()
