# src/pipeline/run_confirmed_daily_update.py
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


STEPS = [
    {
        "name": "BUILD TIMEFRAME STATES",
        "cmd": ["python", "src/states/build_timeframe_states.py"],
        "required": True,
    },
    {
        "name": "BUILD HIERARCHY STATES",
        "cmd": ["python", "src/hierarchy/build_hierarchy_states.py"],
        "required": True,
    },
    {
        "name": "BUILD STATE TRAJECTORY",
        "cmd": ["python", "src/trajectory/build_state_trajectory.py"],
        "required": True,
    },
    {
        "name": "BUILD TRANSITION PATHS",
        "cmd": ["python", "src/trajectory/build_transition_paths.py"],
        "required": True,
    },
    {
        "name": "ANALYZE TRANSITION EXPECTANCY",
        "cmd": ["python", "src/research/analyze_transition_expectancy.py"],
        "required": True,
    },
    {
        "name": "BUILD STATE TRANSITION MATRIX",
        "cmd": ["python", "src/research/build_state_transition_matrix.py"],
        "required": True,
    },
    {
        "name": "BUILD SURVIVABILITY ENGINE",
        "cmd": ["python", "src/survivability/build_survivability_engine.py"],
        "required": True,
    },
    {
        "name": "BUILD TIMEFRAME EXPECTANCY PROFILE",
        "cmd": ["python", "src/survivability/build_timeframe_expectancy_profile.py"],
        "required": True,
    },
    {
        "name": "BUILD LIVE STATE CACHE",
        "cmd": ["python", "src/live/build_live_state_engine.py"],
        "required": True,
    },
]


def print_header(title: str) -> None:
    print("")
    print("=================================")
    print(title)
    print("=================================")


def run_step(step: dict) -> bool:
    print_header(f"🚀 {step['name']}")
    print("cmd:", " ".join(step["cmd"]))

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)

    result = subprocess.run(
        step["cmd"],
        cwd=ROOT,
        text=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=env,
    )

    if result.returncode != 0:
        print("")
        print("=================================")
        print(f"❌ FAILED: {step['name']}")
        print("=================================")

        if step.get("required", True):
            return False

    print("")
    print(f"✅ DONE: {step['name']}")
    return True


def main() -> None:
    started_at = datetime.now()

    print_header("🧠 RUN CONFIRMED DAILY UPDATE PIPELINE")
    print(f"root: {ROOT}")
    print(f"startedAt: {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"steps: {len(STEPS)}")

    completed = []
    failed = []

    for step in STEPS:
        ok = run_step(step)

        if ok:
            completed.append(step["name"])
        else:
            failed.append(step["name"])
            break

    finished_at = datetime.now()
    elapsed = finished_at - started_at

    print_header("📌 PIPELINE SUMMARY")
    print(f"completed: {len(completed)}")
    print(f"failed: {len(failed)}")
    print(f"elapsed: {elapsed}")

    if completed:
        print("")
        print("✅ COMPLETED STEPS")
        for name in completed:
            print("-", name)

    if failed:
        print("")
        print("❌ FAILED STEPS")
        for name in failed:
            print("-", name)

        sys.exit(1)

    print("")
    print("=================================")
    print("✅ CONFIRMED DAILY UPDATE COMPLETE")
    print("=================================")
    print("")
    print("핵심 결과 파일:")
    print("- data/survivability/_survivability_summary.json")
    print("- data/survivability_profiles/_latest_timeframe_profiles.json")
    print("- data/live_states/_live_state_summary.json")
    print("- results/research/transition_expectancy_all.csv")
    print("- results/research/state_transition_matrix_all.csv")


if __name__ == "__main__":
    main()
