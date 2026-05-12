# src/live/build_live_decision_board_html.py

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "data" / "live_states" / "_live_decision_board.json"
OUTPUT_PATH = ROOT / "data" / "live_states" / "live_decision_board.html"


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print("=================================")
    print("🎨 BUILD LIVE SYMBOL MONITOR HTML")
    print("=================================")

    data = load_json(INPUT_PATH)
    generated_at = datetime.now(timezone.utc).isoformat()

    html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Alpha-Flow V2 Live Symbol Monitor</title>
  <style>
    :root {{
      --bg: #070b12;
      --panel: #0d1420;
      --panel2: #111b2a;
      --border: #203049;
      --text: #e6edf7;
      --muted: #8ea0b8;
      --green: #1ee88a;
      --orange: #ffad42;
      --red: #ff4d5e;
      --blue: #4ea1ff;
      --yellow: #ffcf5a;
      --gray: #94a3b8;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(37,99,235,0.20), transparent 34%),
        radial-gradient(circle at top right, rgba(30,232,138,0.10), transparent 30%),
        var(--bg);
      color: var(--text);
      font-family: Inter, Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 26px;
    }}

    .page {{
      max-width: 1500px;
      margin: 0 auto;
    }}

    .hero {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 20px;
      margin-bottom: 20px;
    }}

    h1 {{
      margin: 0;
      font-size: 32px;
      letter-spacing: -0.04em;
    }}

    .subtitle {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
    }}

    .status-box {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .badge {{
      padding: 9px 13px;
      border: 1px solid var(--border);
      background: rgba(13,20,32,0.88);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }}

    .live-dot {{
      display: inline-block;
      width: 8px;
      height: 8px;
      background: var(--green);
      border-radius: 50%;
      margin-right: 7px;
      box-shadow: 0 0 12px rgba(30,232,138,0.9);
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }}

    .summary-card {{
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
      box-shadow: 0 12px 32px rgba(0,0,0,0.25);
    }}

    .summary-card.confirming,
    .summary-card.watch {{
      border-color: rgba(30,232,138,0.35);
      background: linear-gradient(180deg, rgba(30,232,138,0.13), rgba(13,20,32,0.86));
    }}

    .summary-card.caution {{
      border-color: rgba(255,173,66,0.45);
      background: linear-gradient(180deg, rgba(255,173,66,0.14), rgba(13,20,32,0.86));
    }}

    .summary-card.risk {{
      border-color: rgba(255,77,94,0.45);
      background: linear-gradient(180deg, rgba(255,77,94,0.15), rgba(13,20,32,0.86));
    }}

    .summary-title {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }}

    .summary-count {{
      font-size: 34px;
      font-weight: 950;
      margin-top: 6px;
    }}

    .summary-desc {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 5px;
      line-height: 1.4;
    }}

    .group-section {{
      background: rgba(13,20,32,0.84);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 18px;
      margin-bottom: 22px;
      box-shadow: 0 14px 36px rgba(0,0,0,0.30);
    }}

    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }}

    .section-header h2 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: -0.03em;
    }}

    .section-header p {{
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}

    .section-count {{
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 13px;
      font-weight: 900;
    }}

    .table-wrap {{
      overflow-x: auto;
      border-radius: 16px;
      border: 1px solid var(--border);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 980px;
      background: rgba(7,11,18,0.55);
    }}

    th {{
      text-align: left;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      padding: 12px 14px;
      background: rgba(17,27,42,0.96);
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }}

    td {{
      padding: 12px 14px;
      border-bottom: 1px solid rgba(32,48,73,0.62);
      font-size: 13px;
      white-space: nowrap;
    }}

    tr:hover td {{
      background: rgba(78,161,255,0.07);
    }}

    .symbol {{
      font-weight: 950;
      color: white;
      font-size: 16px;
      letter-spacing: 0.02em;
    }}

    .pill {{
      display: inline-flex;
      padding: 6px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 900;
      border: 1px solid var(--border);
    }}

    .confirming, .watch {{ color: var(--green); }}
    .caution {{ color: var(--orange); }}
    .risk {{ color: var(--red); }}
    .neutral {{ color: var(--gray); }}

    .pill.confirming, .pill.watch {{
      background: rgba(30,232,138,0.12);
      border-color: rgba(30,232,138,0.34);
    }}

    .pill.caution {{
      background: rgba(255,173,66,0.14);
      border-color: rgba(255,173,66,0.36);
    }}

    .pill.risk {{
      background: rgba(255,77,94,0.14);
      border-color: rgba(255,77,94,0.36);
    }}

    .score, .move, .failure {{
      font-weight: 950;
    }}

    .score-hot {{ color: var(--yellow); text-shadow: 0 0 14px rgba(255,207,90,0.3); }}
    .score-good {{ color: var(--green); }}
    .score-mid {{ color: var(--blue); }}
    .score-weak {{ color: var(--orange); }}
    .score-bad {{ color: var(--red); }}

    .move-fire {{ color: var(--yellow); }}
    .move-up {{ color: var(--green); }}
    .move-down {{ color: var(--orange); }}
    .move-crash {{ color: var(--red); }}
    .move-flat {{ color: var(--gray); }}

    .failure-low {{ color: var(--green); }}
    .failure-mid {{ color: var(--orange); }}
    .failure-high {{ color: var(--red); }}

    .trend-good {{ color: var(--green); font-weight: 900; }}
    .trend-bad {{ color: var(--red); font-weight: 900; }}
    .trend-flat {{ color: var(--gray); font-weight: 800; }}

    .empty {{
      text-align: center;
      color: var(--muted);
      padding: 28px;
    }}

    @media (max-width: 1200px) {{
      .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}

    @media (max-width: 720px) {{
      body {{ padding: 16px; }}
      .hero {{ display: block; }}
      .status-box {{ justify-content: flex-start; margin-top: 14px; }}
      .summary-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <h1>🔥 Alpha-Flow V2 Live Symbol Monitor</h1>
        <div class="subtitle">상위 후보 실시간 감시판 — score / move / live state / trajectory / failure 중심</div>
      </div>
      <div class="status-box">
        <div class="badge"><span class="live-dot"></span>Auto Update ON</div>
        <div class="badge">refresh: <span id="refreshSec">5</span>s</div>
        <div class="badge">last update: <span id="lastUpdate">-</span></div>
      </div>
    </div>

    <div id="summary" class="summary-grid"></div>
    <div id="sections"></div>
  </div>

<script>
const JSON_PATH = "_live_decision_board.json";
const REFRESH_MS = 5000;
const MAX_ROWS = 30;

const GROUPS = [
  "ACTION_CONFIRMING",
  "ACTION_WATCH",
  "ACTION_CAUTION",
  "ACTION_RISK_OFF"
];

const META = {{
  ACTION_CONFIRMING: {{ title: "🔥 CONFIRMING", desc: "즉시 강한 재가속 확인 후보", cls: "confirming" }},
  ACTION_WATCH: {{ title: "🟢 WATCH", desc: "실시간 관찰 핵심 후보", cls: "watch" }},
  ACTION_CAUTION: {{ title: "🟠 CAUTION", desc: "회복은 있으나 구조 부담", cls: "caution" }},
  ACTION_RISK_OFF: {{ title: "🔴 RISK OFF", desc: "장중 실패/분산/붕괴 위험", cls: "risk" }}
}};

function esc(v) {{
  if (v === null || v === undefined) return "";
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}}

function num(v, d = 2) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return n.toFixed(d);
}}

function scoreClass(v) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return "score-mid";
  if (n >= 80) return "score-hot";
  if (n >= 60) return "score-good";
  if (n >= 40) return "score-mid";
  if (n >= 0) return "score-weak";
  return "score-bad";
}}

function moveClass(v) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return "move-flat";
  if (n >= 5) return "move-fire";
  if (n >= 1) return "move-up";
  if (n <= -5) return "move-crash";
  if (n <= -1) return "move-down";
  return "move-flat";
}}

function failureClass(v) {{
  const n = Number(v);
  if (!Number.isFinite(n)) return "failure-mid";
  if (n >= 65) return "failure-high";
  if (n >= 45) return "failure-mid";
  return "failure-low";
}}

function trendClass(v) {{
  const s = String(v || "");
  if (s.includes("IMPROVING") || s.includes("BUILDING") || s.includes("STRONG")) return "trend-good";
  if (s.includes("DETERIORATING") || s.includes("WEAK") || s.includes("PERSISTING")) return "trend-bad";
  return "trend-flat";
}}

function sortedRows(items) {{
  return [...items].sort((a, b) => {{
    const scoreA = Number(a.score || 0);
    const scoreB = Number(b.score || 0);
    const moveA = Number(a.move || 0);
    const moveB = Number(b.move || 0);
    return (scoreB - scoreA) || (moveB - moveA);
  }}).slice(0, MAX_ROWS);
}}

function renderSummary(data) {{
  const counts = data.counts || {{}};

  document.getElementById("summary").innerHTML = GROUPS.map(group => {{
    const meta = META[group];
    const count = counts[group] || 0;

    return `
      <div class="summary-card ${{meta.cls}}">
        <div class="summary-title">${{meta.title}}</div>
        <div class="summary-count">${{count}}</div>
        <div class="summary-desc">${{meta.desc}}</div>
      </div>
    `;
  }}).join("");
}}

function renderTable(group, items) {{
  const meta = META[group];
  const rows = sortedRows(items || []);

  let body = rows.map(item => `
    <tr>
      <td class="symbol">${{esc(item.symbol)}}</td>
      <td><span class="score ${{scoreClass(item.score)}}">${{num(item.score)}}</span></td>
      <td><span class="move ${{moveClass(item.move)}}">${{num(item.move)}}%</span></td>
      <td><span class="pill ${{meta.cls}}">${{esc(item.liveMergedState)}}</span></td>
      <td>${{esc(item.trajectory)}}</td>
      <td><span class="${{trendClass(item.livePressureTrend)}}">${{esc(item.livePressureTrend || "-")}}</span></td>
      <td><span class="failure ${{failureClass(item.failurePressure)}}">${{num(item.failurePressure)}}</span></td>
    </tr>
  `).join("");

  if (!body) {{
    body = `<tr><td colspan="7" class="empty">No symbols</td></tr>`;
  }}

  return `
    <section class="group-section">
      <div class="section-header">
        <div>
          <h2>${{meta.title}}</h2>
          <p>${{meta.desc}}</p>
        </div>
        <span class="section-count">${{items.length}}</span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Score</th>
              <th>Move</th>
              <th>Live State</th>
              <th>Trajectory</th>
              <th>Trend</th>
              <th>Failure</th>
            </tr>
          </thead>
          <tbody>${{body}}</tbody>
        </table>
      </div>
    </section>
  `;
}}

function renderSections(data) {{
  const board = data.board || {{}};

  document.getElementById("sections").innerHTML = GROUPS.map(group => {{
    return renderTable(group, board[group] || []);
  }}).join("");
}}

async function loadBoard() {{
  try {{
    const url = JSON_PATH + "?t=" + Date.now();
    const res = await fetch(url);

    if (!res.ok) throw new Error("fetch failed: " + res.status);

    const data = await res.json();

    renderSummary(data);
    renderSections(data);

    document.getElementById("lastUpdate").textContent = new Date().toLocaleTimeString();
  }} catch (e) {{
    document.getElementById("lastUpdate").textContent = "ERROR";
    console.error(e);
  }}
}}

document.getElementById("refreshSec").textContent = String(REFRESH_MS / 1000);

loadBoard();
setInterval(loadBoard, REFRESH_MS);
</script>
</body>
</html>
"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ saved: {OUTPUT_PATH}")
    print(f"generatedAt: {generated_at}")


if __name__ == "__main__":
    main()
