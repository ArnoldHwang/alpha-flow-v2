# src/live/run_live_server.py

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = Path(__file__).resolve().parents[2]
LIVE_STATES_DIR = ROOT / "data" / "live_states"

VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
PYTHON_EXE = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


LIVE_STEPS = [
    {
        "name": "LIVE PRICE FEED",
        "cmd": [PYTHON_EXE, "src/live/live_price_feed.py"],
    },
    {
        "name": "LIVE CONFIRMED MERGE",
        "cmd": [PYTHON_EXE, "src/live/build_live_confirmed_merge_engine.py"],
    },
    {
        "name": "LIVE DECISION BOARD",
        "cmd": [PYTHON_EXE, "src/live/build_live_decision_board.py"],
    },
    {
        "name": "LIVE DECISION HTML",
        "cmd": [PYTHON_EXE, "src/live/build_live_decision_board_html.py"],
    },
]


def print_header(title: str) -> None:
    print("")
    print("=================================")
    print(title)
    print("=================================")


def run_http_server(port: int) -> None:
    os.chdir(LIVE_STATES_DIR)

    server = ThreadingHTTPServer(
        ("localhost", port),
        SimpleHTTPRequestHandler,
    )

    print_header("🌐 LIVE DASHBOARD SERVER")
    print(f"url: http://localhost:{port}/live_decision_board.html")
    print(f"dir: {LIVE_STATES_DIR}")

    server.serve_forever()


def run_step(step: dict) -> bool:
    print("")
    print(f"🚀 {step['name']}")
    print("cmd:", " ".join(step["cmd"]))

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)

    started = time.time()

    result = subprocess.run(
        step["cmd"],
        cwd=ROOT,
        text=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=env,
    )

    elapsed = round(time.time() - started, 2)

    if result.returncode != 0:
        print(f"❌ FAILED: {step['name']}")
        return False

    print(f"✅ DONE: {step['name']} ({elapsed}s)")
    return True


def print_live_summary() -> None:
    board_path = ROOT / "data" / "live_states" / "_live_decision_board.json"

    if not board_path.exists():
        print("⚠️ board file not found yet")
        return

    try:
        import json

        with open(board_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        counts = data.get("counts", {})
        board = data.get("board", {})

        print("")
        print("📊 LIVE BOARD")

        for key in [
            "ACTION_CONFIRMING",
            "ACTION_WATCH",
            "ACTION_CAUTION",
            "ACTION_RISK_OFF",
            "ACTION_AVOID",
            "ACTION_NEUTRAL",
        ]:
            print(f"  {key}: {counts.get(key, 0)}")

        print("")
        print("🔥 WATCH TOP")
        for row in board.get("ACTION_WATCH", [])[:10]:
            print(
                f"  {row['symbol']} | "
                f"{row['liveMergedState']} | "
                f"score={row['score']} | "
                f"move={row['move']}%"
            )

        print("")
        print("⚠️ RISK TOP")
        for row in board.get("ACTION_RISK_OFF", [])[:10]:
            print(
                f"  {row['symbol']} | "
                f"{row['liveMergedState']} | "
                f"move={row['move']}% | "
                f"fail={row['failurePressure']}"
            )

    except Exception as e:
        print(f"⚠️ summary read fail: {e}")


def run_live_loop(interval: int) -> None:
    loop_count = 0

    while True:
        loop_count += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print("")
        print("======================================================")
        print(f"🕒 LOOP #{loop_count} | {now}")
        print("======================================================")

        loop_started = time.time()
        failed = False

        for step in LIVE_STEPS:
            ok = run_step(step)

            if not ok:
                failed = True
                break

        elapsed = round(time.time() - loop_started, 2)

        if failed:
            print_header("❌ LOOP FAILED")
        else:
            print_live_summary()
            print_header(f"✅ LIVE LOOP COMPLETE ({elapsed}s)")

        print("")
        print(f"⏳ sleeping {interval}s...")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="dashboard server port",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=180,
        help="live loop interval seconds",
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open browser automatically",
    )

    args = parser.parse_args()

    interval = max(60, args.interval)

    LIVE_STATES_DIR.mkdir(parents=True, exist_ok=True)

    url = f"http://localhost:{args.port}/live_decision_board.html"

    print_header("🔥 ALPHA-FLOW V2 LIVE SERVER")
    print(f"root: {ROOT}")
    print(f"python: {PYTHON_EXE}")
    print(f"interval: {interval}s")
    print(f"url: {url}")

    server_thread = Thread(
        target=run_http_server,
        args=(args.port,),
        daemon=True,
    )
    server_thread.start()

    time.sleep(1)

    if not args.no_browser:
        webbrowser.open(url)

    run_live_loop(interval)


if __name__ == "__main__":
    main()
