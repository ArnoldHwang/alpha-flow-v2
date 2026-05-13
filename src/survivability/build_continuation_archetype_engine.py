# src/survivability/build_continuation_archetype_engine.py

import json
from glob import glob
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "data" / "survivability"
OUTPUT_DIR = ROOT / "data" / "survivability_archetypes"
OUTPUT_SUMMARY_PATH = OUTPUT_DIR / "_archetype_summary.json"


def load_json_records(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["records", "data", "rows", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]

    return []


def save_json_records(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_state(value: Any, default: str = "UNKNOWN") -> str:
    if value is None or pd.isna(value):
        return default

    text = str(value).strip()

    if text == "" or text.lower() == "nan":
        return default

    return text


def classify_preferred_timeframe(row: Dict[str, Any]) -> str:
    expectancy_profile = safe_state(row.get("expectancyProfile"))
    timeframe_type = safe_state(row.get("timeframeExpectancyType"))

    avg5 = safe_float(row.get("selectedAvgReturn5d"), 0)
    avg10 = safe_float(row.get("selectedAvgReturn10d"), 0)
    avg20 = safe_float(row.get("selectedAvgReturn20d"), 0)
    avg60 = safe_float(row.get("selectedAvgReturn60d"), 0)

    if expectancy_profile == "SHORT_SWING_BURST":
        return "1D_5D"

    if expectancy_profile == "SWING_CONTINUATION":
        return "5D_20D"

    if expectancy_profile == "MIDTERM_SURVIVABILITY":
        return "10D_30D"

    if expectancy_profile == "LONG_DRIFT_CONTINUATION":
        return "30D_60D"

    if "TACTICAL_BURST" in timeframe_type:
        return "1D_10D"

    if "INSTITUTIONAL_DRIFT" in timeframe_type:
        return "20D_60D"

    scores = {
        "1D_5D": avg5,
        "5D_10D": avg10,
        "10D_20D": avg20,
        "30D_60D": avg60,
    }

    best = max(scores.items(), key=lambda x: x[1])

    return best[0]


def classify_archetype(row: Dict[str, Any]) -> str:
    trajectory = safe_state(row.get("trajectoryState"))
    hierarchy = safe_state(row.get("finalHierarchyState"))
    daily = safe_state(row.get("dailyContinuationState"))
    risk = safe_state(row.get("riskProfile"))
    continuation = safe_state(row.get("continuationProfile"))
    expectancy = safe_state(row.get("expectancyProfile"))
    bias = safe_state(row.get("survivabilityBias"))

    score = safe_float(row.get("continuationSurvivabilityScore"), 0)
    failure = safe_float(row.get("continuationFailureRisk"), 50)

    avg5 = safe_float(row.get("selectedAvgReturn5d"), 0)
    avg10 = safe_float(row.get("selectedAvgReturn10d"), 0)
    avg20 = safe_float(row.get("selectedAvgReturn20d"), 0)
    avg60 = safe_float(row.get("selectedAvgReturn60d"), 0)

    preferred = classify_preferred_timeframe(row)

    # 1. 명확한 붕괴/분산
    if risk in {"STRUCTURAL_BREAKDOWN_RISK", "EXTREME_FAILURE_RISK"}:
        return "DISTRIBUTION_BREAKDOWN"

    if trajectory == "BREAKDOWN_PERSISTENCE":
        return "DISTRIBUTION_BREAKDOWN"

    if trajectory == "DISTRIBUTION_TRAJECTORY" and failure >= 55:
        return "DISTRIBUTION_BREAKDOWN"

    if trajectory == "DISTRIBUTION_TRAJECTORY":
        return "DISTRIBUTION_PRESSURE"

    # 2. 회복 후 재가속
    if (
        trajectory == "RECOVERY_TRAJECTORY"
        and continuation == "RECOVERY_REACCELERATION_ALIVE"
    ):
        return "RECOVERY_REACCELERATION"

    if trajectory == "RECOVERY_TRAJECTORY" and score >= 50 and failure <= 55:
        return "RECOVERY_WATCH"

    # 3. 가속 continuation
    if trajectory == "ACCELERATING_TRAJECTORY" and failure <= 55:
        if expectancy == "SHORT_SWING_BURST" or avg5 >= 4:
            return "TACTICAL_BURST_CONTINUATION"
        return "ACCELERATING_CONTINUATION"

    # 4. 터미널/후반부 continuation
    if hierarchy == "TERMINAL_STRUCTURE_RISK" and failure <= 60:
        if avg20 >= 6 or avg5 >= 4:
            return "TACTICAL_PARABOLIC_CONTINUATION"
        return "LATE_STAGE_CONTINUATION"

    # 5. 기관형 장기 drift
    if (
        preferred == "30D_60D"
        and failure <= 40
        and score >= 48
        and trajectory in {"NEUTRAL_TRAJECTORY", "STABLE_CONTINUATION"}
    ):
        return "INSTITUTIONAL_DRIFT"

    if (
        preferred == "30D_60D"
        and failure <= 42
        and score >= 48
        and hierarchy in {"MIXED_STRUCTURE", "CONSTRUCTIVE_PAUSE_STRUCTURE"}
    ):
        return "STEALTH_CONTINUATION"

    # 6. 오래됐지만 살아있는 continuation
    if hierarchy in {"AGING_CONTINUATION_STRUCTURE", "HEALTHY_BUT_MONTHLY_EXTENDED"}:
        if (
            avg60 >= 8
            or expectancy == "LONG_DRIFT_CONTINUATION"
            or preferred == "30D_60D"
        ):
            return "INSTITUTIONAL_DRIFT"
        return "AGING_BUT_SURVIVING"

    # 7. 건설적 pause 세분화
    if hierarchy == "CONSTRUCTIVE_PAUSE_STRUCTURE":
        if failure <= 35 and score >= 45:
            return "LOW_VOLATILITY_BASE"
        return "CONSTRUCTIVE_PAUSE"

    if daily in {
        "BASE_BUILDING",
        "PAUSE_OR_PULLBACK",
        "HEALTHY_RESET",
        "SOFT_PULLBACK",
    }:
        if failure <= 35 and score >= 45:
            return "LOW_VOLATILITY_BASE"
        if failure <= 45:
            return "CONSTRUCTIVE_PAUSE"

    # 8. 조용한 continuation
    if (
        failure <= 40
        and score >= 48
        and trajectory in {"NEUTRAL_TRAJECTORY", "STABLE_CONTINUATION"}
    ):
        return "STEALTH_CONTINUATION"

    # 9. 구조적 continuation
    if bias in {"HIGH", "GOOD", "GOOD_BUT_EXTENSION_RISK"} and failure <= 50:
        return "STRUCTURAL_CONTINUATION"

    if score >= 60 and failure <= 45:
        return "STRUCTURAL_CONTINUATION"

    # 10. 변동성/혼조
    if trajectory == "VOLATILE_CHOP":
        return "VOLATILE_CHOP_CONTINUATION"

    # 11. 낮은 위험이지만 힘이 약한 장기 drift
    if preferred == "30D_60D" and failure <= 40 and score >= 45:
        return "SLOW_DRIFT_CONTINUATION"

    return "UNCLASSIFIED_CONTINUATION"


def classify_archetype_bias(archetype: str) -> str:
    if archetype in {
        "RECOVERY_REACCELERATION",
        "ACCELERATING_CONTINUATION",
        "STRUCTURAL_CONTINUATION",
        "INSTITUTIONAL_DRIFT",
        "STEALTH_CONTINUATION",
    }:
        return "POSITIVE"

    if archetype in {
        "TACTICAL_BURST_CONTINUATION",
        "TACTICAL_PARABOLIC_CONTINUATION",
        "AGING_BUT_SURVIVING",
        "SLOW_DRIFT_CONTINUATION",
    }:
        return "TACTICAL_POSITIVE"

    if archetype in {
        "CONSTRUCTIVE_PAUSE",
        "LOW_VOLATILITY_BASE",
        "RECOVERY_WATCH",
    }:
        return "WATCH_POSITIVE"

    if archetype in {
        "DISTRIBUTION_PRESSURE",
        "VOLATILE_CHOP_CONTINUATION",
    }:
        return "CAUTION"

    if archetype == "DISTRIBUTION_BREAKDOWN":
        return "RISK_OFF"

    return "NEUTRAL"


def classify_archetype_risk(row: Dict[str, Any], archetype: str) -> str:
    failure = safe_float(row.get("continuationFailureRisk"), 50)
    risk_profile = safe_state(row.get("riskProfile"))

    if archetype == "DISTRIBUTION_BREAKDOWN":
        return "VERY_HIGH"

    if risk_profile in {"STRUCTURAL_BREAKDOWN_RISK", "EXTREME_FAILURE_RISK"}:
        return "VERY_HIGH"

    if archetype in {"TACTICAL_PARABOLIC_CONTINUATION", "LATE_STAGE_CONTINUATION"}:
        return "HIGH"

    if failure >= 60:
        return "HIGH"

    if failure >= 45:
        return "MEDIUM"

    return "LOW"


def build_archetype_interpretation(row: Dict[str, Any]) -> str:
    archetype = safe_state(row.get("continuationArchetype"))
    preferred = safe_state(row.get("preferredTimeframe"))
    risk = safe_state(row.get("archetypeRisk"))

    ko_map = {
        "RECOVERY_REACCELERATION": "재축적/회복 이후 다시 가속될 수 있는 continuation 구조",
        "RECOVERY_WATCH": "회복 흐름은 있으나 아직 확정 강도는 부족한 관찰 구조",
        "ACCELERATING_CONTINUATION": "추세가 다시 강해지는 가속 continuation 구조",
        "TACTICAL_BURST_CONTINUATION": "단기 폭발 가능성이 있는 전술형 continuation 구조",
        "TACTICAL_PARABOLIC_CONTINUATION": "후반부 과열이지만 단기 수익 가능성이 남은 고위험 continuation 구조",
        "LATE_STAGE_CONTINUATION": "후반부 continuation으로 수익 기회와 피로 위험이 공존하는 구조",
        "INSTITUTIONAL_DRIFT": "느리지만 오래 지속될 수 있는 기관형 continuation 구조",
        "AGING_BUT_SURVIVING": "오래된 추세지만 아직 완전히 죽지 않은 생존형 continuation 구조",
        "CONSTRUCTIVE_PAUSE": "건강한 숨고르기/베이스 형성 가능성이 있는 구조",
        "STRUCTURAL_CONTINUATION": "상위 구조가 아직 살아있는 일반 continuation 구조",
        "DISTRIBUTION_PRESSURE": "매물/분산 압력이 생기고 있어 주의가 필요한 구조",
        "DISTRIBUTION_BREAKDOWN": "구조 붕괴 또는 분산 지속 위험이 높은 회피 구조",
        "VOLATILE_CHOP_CONTINUATION": "변동성 큰 혼조 continuation 구조",
        "UNCLASSIFIED_CONTINUATION": "아직 명확한 continuation 타입으로 분류되지 않은 구조",
        "STEALTH_CONTINUATION": "겉으로 강하지는 않지만 조용히 살아있는 continuation 구조",
        "LOW_VOLATILITY_BASE": "낮은 변동성으로 베이스를 만드는 안정형 continuation 준비 구조",
        "SLOW_DRIFT_CONTINUATION": "강한 폭발력은 없지만 천천히 이어질 수 있는 저위험 drift 구조",
        "LATE_STAGE_DRIFT": "후반부 추세가 느리게 이어지는 구조",
    }

    desc = ko_map.get(archetype, "분류되지 않은 continuation 구조")

    return f"{desc} | 선호 시간축: {preferred} | 위험도: {risk}"


def enrich_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []

    for source in records:
        row = dict(source)

        archetype = classify_archetype(row)

        row["continuationArchetype"] = archetype
        row["archetypeBias"] = classify_archetype_bias(archetype)
        row["preferredTimeframe"] = classify_preferred_timeframe(row)
        row["archetypeRisk"] = classify_archetype_risk(row, archetype)
        row["archetypeInterpretation"] = build_archetype_interpretation(row)

        enriched.append(row)

    return enriched


def process_symbol_file(path: Path) -> Dict[str, Any]:
    records = load_json_records(path)

    if not records:
        return {
            "file": path.name,
            "status": "SKIPPED_EMPTY",
            "rows": 0,
        }

    enriched = enrich_records(records)

    output_path = OUTPUT_DIR / path.name
    save_json_records(output_path, enriched)

    latest = enriched[-1]

    return {
        "file": path.name,
        "symbol": safe_state(latest.get("symbol"), path.stem),
        "status": "OK",
        "rows": len(enriched),
        "latestDate": latest.get("date"),
        "latestArchetype": latest.get("continuationArchetype"),
        "latestArchetypeBias": latest.get("archetypeBias"),
        "latestPreferredTimeframe": latest.get("preferredTimeframe"),
        "latestArchetypeRisk": latest.get("archetypeRisk"),
        "latestSurvivabilityScore": latest.get("continuationSurvivabilityScore"),
        "latestFailureRisk": latest.get("continuationFailureRisk"),
    }


def main() -> None:
    print("=================================")
    print("🧬 BUILD CONTINUATION ARCHETYPE ENGINE")
    print("=================================")

    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"input dir not found: {INPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files = sorted(
        Path(p)
        for p in glob(str(INPUT_DIR / "*.json"))
        if not Path(p).name.startswith("_")
    )

    if not input_files:
        raise FileNotFoundError(f"no input json files found: {INPUT_DIR}")

    summaries = []

    for path in input_files:
        result = process_symbol_file(path)
        summaries.append(result)

    save_json_records(OUTPUT_SUMMARY_PATH, summaries)

    df = pd.DataFrame(summaries)
    ok = df[df["status"] == "OK"].copy()

    print(f"files: {len(input_files):,}")
    print(f"ok: {len(ok):,}")
    print(f"summary: {OUTPUT_SUMMARY_PATH}")

    if not ok.empty:
        print("")
        print("📊 latestArchetype:")
        print(ok["latestArchetype"].value_counts(dropna=False).to_string())

        print("")
        print("📊 latestPreferredTimeframe:")
        print(ok["latestPreferredTimeframe"].value_counts(dropna=False).to_string())

        print("")
        print("🔥 latest top archetypes:")
        cols = [
            "symbol",
            "latestDate",
            "latestArchetype",
            "latestArchetypeBias",
            "latestPreferredTimeframe",
            "latestArchetypeRisk",
            "latestSurvivabilityScore",
            "latestFailureRisk",
        ]
        print(
            ok.sort_values(
                ["latestArchetypeBias", "latestSurvivabilityScore"],
                ascending=[True, False],
            )[cols]
            .head(40)
            .to_string(index=False)
        )

    print("")
    print("✅ DONE")


if __name__ == "__main__":
    main()
