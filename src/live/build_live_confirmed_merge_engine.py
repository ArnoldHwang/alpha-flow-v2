# src/live/build_live_confirmed_merge_engine.py

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

SURVIVABILITY_PATH = (
    ROOT / "data" / "survivability_profiles" / "_latest_timeframe_profiles.json"
)
LIVE_STATE_PATH = ROOT / "data" / "live_states" / "_live_state_summary.json"
LIVE_QUOTES_PATH = ROOT / "data" / "live_feed" / "live_quotes.json"

OUTPUT_PATH = ROOT / "data" / "live_states" / "_live_confirmed_merge_summary.json"


def load_json(path, default):
    if not path.exists():
        print(f"⚠️ missing file: {path}")
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_str(value, default="UNKNOWN"):
    if value is None:
        return default
    return str(value)


def normalize_items(data):
    if isinstance(data, list):
        result = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if symbol:
                result[symbol] = item
        return result

    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            return normalize_items(data["items"])

        if isinstance(data.get("symbols"), list):
            return normalize_items(data["symbols"])

        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("symbol", key)
                result[key] = item
        return result

    return {}


def get_any(row, keys, default=None):
    for key in keys:
        if key in row and row.get(key) is not None:
            return row.get(key)
    return default


def score_survivability_bias(bias):
    bias = safe_str(bias, "NEUTRAL")

    table = {
        "HIGH": 30,
        "GOOD": 22,
        "GOOD_BUT_EXTENSION_RISK": 14,
        "TACTICAL_ONLY": 5,
        "CAUTION": -8,
        "NEUTRAL": 0,
        "AVOID": -25,
    }

    return table.get(bias, 0)


def score_trajectory(trajectory):
    trajectory = safe_str(trajectory, "NEUTRAL_TRAJECTORY")

    table = {
        "RECOVERY_TRAJECTORY": 24,
        "ACCELERATING_TRAJECTORY": 26,
        "STABLE_CONTINUATION": 16,
        "NEUTRAL_TRAJECTORY": 0,
        "VOLATILE_CHOP": -12,
        "DISTRIBUTION_TRAJECTORY": -26,
        "BREAKDOWN_PERSISTENCE": -35,
    }

    return table.get(trajectory, 0)


def classify_live_pressure(live_state, quote):
    live_move = safe_float(
        get_any(
            quote,
            [
                "dayChangePct",
                "changeRate",
                "changePct",
                "regularMarketChangePercent",
                "liveChangeRate",
            ],
            0,
        )
    )

    live_volume_ratio = safe_float(
        get_any(
            live_state,
            ["liveVolumeRatio", "volumeRatio", "volumeRatio20", "relativeVolume"],
            get_any(quote, ["volumeRatio"], 1),
        ),
        1,
    )

    breakout_pressure = safe_float(
        get_any(
            live_state,
            ["liveBreakoutPressure", "breakoutPressure", "reaccelerationPressure"],
            0,
        )
    )

    failure_pressure = safe_float(
        get_any(
            live_state,
            ["liveFailurePressure", "failurePressure", "breakdownPressure"],
            0,
        )
    )

    distribution_pressure = safe_float(
        get_any(
            live_state,
            ["liveDistributionPressure", "distributionPressure", "upperWickPressure"],
            0,
        )
    )

    if breakout_pressure == 0:
        if live_move >= 3:
            breakout_pressure += 30
        elif live_move >= 1.5:
            breakout_pressure += 18
        elif live_move >= 0.5:
            breakout_pressure += 8

    if failure_pressure == 0:
        if live_move <= -3:
            failure_pressure += 32
        elif live_move <= -1.5:
            failure_pressure += 18
        elif live_move <= -0.7:
            failure_pressure += 8

    if live_volume_ratio >= 1.8 and live_move > 1:
        breakout_pressure += 8

    if live_volume_ratio >= 1.8 and live_move < -1:
        failure_pressure += 10
        distribution_pressure += 8

    if live_move > 0:
        live_momentum_score = min(25, live_move * 5)
    else:
        live_momentum_score = max(-25, live_move * 5)

    return {
        "liveMove": round(live_move, 4),
        "liveVolumeRatio": round(live_volume_ratio, 4),
        "breakoutPressure": round(breakout_pressure, 4),
        "failurePressure": round(failure_pressure, 4),
        "distributionPressure": round(distribution_pressure, 4),
        "liveMomentumScore": round(live_momentum_score, 4),
    }


def classify_merged_state(row):
    survivability_bias = row["survivabilityBias"]
    trajectory = row["trajectoryState"]

    live_move = row["liveMove"]
    breakout_pressure = row["breakoutPressure"]
    failure_pressure = row["failurePressure"]
    distribution_pressure = row["distributionPressure"]

    merged_score = row["mergedContinuationScore"]

    good_survivability = survivability_bias in {
        "HIGH",
        "GOOD",
        "GOOD_BUT_EXTENSION_RISK",
    }

    weak_survivability = survivability_bias in {
        "AVOID",
        "CAUTION",
    }

    recovery_like = trajectory in {
        "RECOVERY_TRAJECTORY",
        "ACCELERATING_TRAJECTORY",
    }

    stable_like = trajectory in {
        "STABLE_CONTINUATION",
    }

    distribution_like = trajectory in {
        "DISTRIBUTION_TRAJECTORY",
        "BREAKDOWN_PERSISTENCE",
    }

    chop_like = trajectory in {
        "VOLATILE_CHOP",
    }

    if failure_pressure >= 70 and live_move <= -2:
        return "LIVE_BREAKDOWN_CONFIRMING"

    if recovery_like and live_move <= -3:
        return "LIVE_RECOVERY_FAILING_INTRADAY"

    if distribution_like and (failure_pressure >= 18 or distribution_pressure >= 20):
        return "LIVE_DISTRIBUTION_CONTINUATION"

    if (
        good_survivability
        and recovery_like
        and breakout_pressure >= 25
        and live_move >= 1
    ):
        return "LIVE_REACCELERATION_CONFIRMING"

    if good_survivability and breakout_pressure >= 35 and live_move >= 2:
        return "LIVE_BREAKOUT_CONFIRMING"

    if recovery_like and merged_score >= 45 and failure_pressure < 18:
        return "LIVE_RECOVERY_CONFIRMING"

    if good_survivability and stable_like and failure_pressure < 20:
        return "LIVE_CONTINUATION_HOLDING"

    if (
        survivability_bias == "CAUTION"
        and recovery_like
        and merged_score >= 45
        and failure_pressure < 55
    ):
        return "LIVE_RECOVERY_UNDER_PRESSURE"

    if (
        survivability_bias in {"NEUTRAL", "GOOD_BUT_EXTENSION_RISK", "GOOD", "HIGH"}
        and recovery_like
        and merged_score >= 60
        and breakout_pressure >= 40
        and failure_pressure < 55
    ):
        if survivability_bias == "GOOD_BUT_EXTENSION_RISK":
            return "LIVE_RECOVERY_EXTENSION_WATCH"

        return "LIVE_RECOVERY_WATCHLIST"

    if weak_survivability and breakout_pressure >= 25 and failure_pressure >= 15:
        return "LIVE_FAKE_REACCELERATION_RISK"

    if chop_like and abs(live_move) >= 2:
        return "LIVE_VOLATILE_NOISE"

    return "LIVE_NEUTRAL"


def classify_live_decision_group(live_merged_state):
    if live_merged_state in {
        "LIVE_REACCELERATION_CONFIRMING",
        "LIVE_BREAKOUT_CONFIRMING",
    }:
        return "ACTION_CONFIRMING"

    if live_merged_state in {
        "LIVE_RECOVERY_WATCHLIST",
        "LIVE_RECOVERY_EXTENSION_WATCH",
        "LIVE_RECOVERY_CONFIRMING",
        "LIVE_CONTINUATION_HOLDING",
    }:
        return "ACTION_WATCH"

    if live_merged_state in {
        "LIVE_RECOVERY_UNDER_PRESSURE",
        "LIVE_VOLATILE_NOISE",
    }:
        return "ACTION_CAUTION"

    if live_merged_state in {
        "LIVE_RECOVERY_FAILING_INTRADAY",
        "LIVE_DISTRIBUTION_CONTINUATION",
        "LIVE_BREAKDOWN_CONFIRMING",
    }:
        return "ACTION_RISK_OFF"

    if live_merged_state in {
        "LIVE_FAKE_REACCELERATION_RISK",
    }:
        return "ACTION_AVOID"

    return "ACTION_NEUTRAL"


def build_merge_row(symbol, profile, live_state, quote):
    survivability_bias = safe_str(
        get_any(
            profile,
            ["survivabilityBias", "finalSurvivabilityBias", "bias"],
            "NEUTRAL",
        )
    )

    hierarchy_state = safe_str(
        get_any(
            profile,
            ["finalHierarchyState", "hierarchyState", "state"],
            "UNKNOWN",
        )
    )

    trajectory_state = safe_str(
        get_any(
            profile,
            ["trajectoryState", "trajectoryType", "stateTrajectory"],
            get_any(
                live_state, ["trajectoryState", "trajectoryType"], "NEUTRAL_TRAJECTORY"
            ),
        )
    )

    continuation_score = safe_float(
        get_any(
            profile,
            [
                "continuationSurvivabilityScore",
                "survivabilityScore",
                "finalScore",
                "score",
            ],
            0,
        )
    )

    pressure = classify_live_pressure(live_state, quote)

    survivability_score = score_survivability_bias(survivability_bias)
    trajectory_score = score_trajectory(trajectory_state)

    merged_score = (
        continuation_score
        + survivability_score
        + trajectory_score
        + pressure["liveMomentumScore"]
        + pressure["breakoutPressure"] * 0.45
        - pressure["failurePressure"] * 0.65
        - pressure["distributionPressure"] * 0.35
    )

    row = {
        "symbol": symbol,
        "confirmedHierarchyState": hierarchy_state,
        "survivabilityBias": survivability_bias,
        "trajectoryState": trajectory_state,
        "confirmedSurvivabilityScore": round(continuation_score, 4),
        "survivabilityBiasScore": round(survivability_score, 4),
        "trajectoryScore": round(trajectory_score, 4),
        **pressure,
        "mergedContinuationScore": round(merged_score, 4),
    }

    row["liveMergedState"] = classify_merged_state(row)
    row["liveDecisionGroup"] = classify_live_decision_group(row["liveMergedState"])

    return row


def summarize(rows):
    state_counts = {}
    decision_group_counts = {}
    trajectory_counts = {}

    for row in rows:
        state = row.get("liveMergedState", "UNKNOWN")
        decision_group = row.get("liveDecisionGroup", "UNKNOWN")
        trajectory = row.get("trajectoryState", "UNKNOWN")

        state_counts[state] = state_counts.get(state, 0) + 1
        decision_group_counts[decision_group] = (
            decision_group_counts.get(decision_group, 0) + 1
        )
        trajectory_counts[trajectory] = trajectory_counts.get(trajectory, 0) + 1

    top_candidates = [
        row
        for row in rows
        if row["liveMergedState"]
        in {
            "LIVE_REACCELERATION_CONFIRMING",
            "LIVE_BREAKOUT_CONFIRMING",
            "LIVE_RECOVERY_CONFIRMING",
            "LIVE_CONTINUATION_HOLDING",
            "LIVE_RECOVERY_UNDER_PRESSURE",
            "LIVE_RECOVERY_WATCHLIST",
            "LIVE_RECOVERY_EXTENSION_WATCH",
        }
    ]

    risk_candidates = [
        row
        for row in rows
        if row["liveMergedState"]
        in {
            "LIVE_DISTRIBUTION_CONTINUATION",
            "LIVE_BREAKDOWN_CONFIRMING",
            "LIVE_RECOVERY_FAILING_INTRADAY",
            "LIVE_FAKE_REACCELERATION_RISK",
        }
    ]

    top_candidates = sorted(
        top_candidates,
        key=lambda x: x.get("mergedContinuationScore", 0),
        reverse=True,
    )[:30]

    risk_candidates = sorted(
        risk_candidates,
        key=lambda x: x.get("failurePressure", 0) + x.get("distributionPressure", 0),
        reverse=True,
    )[:30]

    return {
        "stateCounts": dict(
            sorted(state_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        "decisionGroupCounts": dict(
            sorted(decision_group_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        "trajectoryCounts": dict(
            sorted(trajectory_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        "topLiveContinuationCandidates": top_candidates,
        "topLiveRiskCandidates": risk_candidates,
    }


def main():
    print("=================================")
    print("🧠 LIVE + CONFIRMED MERGE ENGINE")
    print("=================================")

    profiles_raw = load_json(SURVIVABILITY_PATH, {})
    live_states_raw = load_json(LIVE_STATE_PATH, {})
    live_quotes_raw = load_json(LIVE_QUOTES_PATH, {})

    profiles = normalize_items(profiles_raw)
    live_states = normalize_items(live_states_raw)
    live_quotes = normalize_items(live_quotes_raw)

    symbols = sorted(
        set(profiles.keys()) | set(live_states.keys()) | set(live_quotes.keys())
    )

    rows = []

    for symbol in symbols:
        profile = profiles.get(symbol, {})
        live_state = live_states.get(symbol, {})
        quote = live_quotes.get(symbol, {})

        row = build_merge_row(symbol, profile, live_state, quote)
        rows.append(row)

    rows = sorted(
        rows,
        key=lambda x: x.get("mergedContinuationScore", 0),
        reverse=True,
    )

    summary = summarize(rows)

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceFiles": {
            "survivabilityProfiles": str(SURVIVABILITY_PATH),
            "liveStates": str(LIVE_STATE_PATH),
            "liveQuotes": str(LIVE_QUOTES_PATH),
        },
        "totalSymbols": len(rows),
        "summary": summary,
        "items": rows,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ symbols: {len(rows)}")
    print("")

    print("📊 liveDecisionGroup:")
    for k, v in summary["decisionGroupCounts"].items():
        print(f"  {k}: {v}")

    print("")
    print("📊 liveMergedState:")
    for k, v in summary["stateCounts"].items():
        print(f"  {k}: {v}")

    print("")
    print("🔥 top live continuation candidates:")
    for row in summary["topLiveContinuationCandidates"][:15]:
        print(
            f"  {row['symbol']} | {row['liveDecisionGroup']} | "
            f"{row['liveMergedState']} | "
            f"score={row['mergedContinuationScore']} | "
            f"traj={row['trajectoryState']} | "
            f"bias={row['survivabilityBias']} | "
            f"move={row['liveMove']}"
        )

    print("")
    print("⚠️ top live risk candidates:")
    for row in summary["topLiveRiskCandidates"][:15]:
        print(
            f"  {row['symbol']} | {row['liveDecisionGroup']} | "
            f"{row['liveMergedState']} | "
            f"score={row['mergedContinuationScore']} | "
            f"traj={row['trajectoryState']} | "
            f"bias={row['survivabilityBias']} | "
            f"move={row['liveMove']} | "
            f"fail={row['failurePressure']} | "
            f"dist={row['distributionPressure']}"
        )

    print("")
    print(f"💾 saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
