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
    print("🎨 BUILD LIVE DECISION BOARD HTML")
    print("=================================")

    _ = load_json(INPUT_PATH)
    generated_at = datetime.now(timezone.utc).isoformat()

    # 중요:
    # 이 파일은 live decision board JSON을 사람이 보기 좋은 한글 운용 보드로 표시한다.
    # 내부 엔진 상태명은 유지하되, 화면에서는 직관적인 한글 해석을 우선 노출한다.
    html = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Alpha-Flow V2 실시간 운용 보드</title>
  <style>
    :root {
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
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(37,99,235,0.20), transparent 34%),
        radial-gradient(circle at top right, rgba(30,232,138,0.10), transparent 30%),
        var(--bg);
      color: var(--text);
      font-family: Inter, Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 26px;
    }

    .page { max-width: 1560px; margin: 0 auto; }

    .hero {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 20px;
      margin-bottom: 20px;
    }

    h1 { margin: 0; font-size: 32px; letter-spacing: -0.04em; }
    .subtitle { margin-top: 8px; color: var(--muted); font-size: 14px; line-height: 1.5; }

    .status-box { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
    .badge {
      padding: 9px 13px;
      border: 1px solid var(--border);
      background: rgba(13,20,32,0.88);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }
    .live-dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      background: var(--green);
      border-radius: 50%;
      margin-right: 7px;
      box-shadow: 0 0 12px rgba(30,232,138,0.9);
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }

    .summary-card {
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
      box-shadow: 0 12px 32px rgba(0,0,0,0.25);
    }
    .summary-card.confirming,
    .summary-card.watch {
      border-color: rgba(30,232,138,0.35);
      background: linear-gradient(180deg, rgba(30,232,138,0.13), rgba(13,20,32,0.86));
    }
    .summary-card.caution {
      border-color: rgba(255,173,66,0.45);
      background: linear-gradient(180deg, rgba(255,173,66,0.14), rgba(13,20,32,0.86));
    }
    .summary-card.risk {
      border-color: rgba(255,77,94,0.45);
      background: linear-gradient(180deg, rgba(255,77,94,0.15), rgba(13,20,32,0.86));
    }
    .summary-title { color: var(--muted); font-size: 13px; font-weight: 800; }
    .summary-count { font-size: 34px; font-weight: 950; margin-top: 6px; }
    .summary-desc { color: var(--muted); font-size: 12px; margin-top: 5px; line-height: 1.4; }

    .layout { display: grid; grid-template-columns: minmax(0, 1fr) 430px; gap: 18px; align-items: start; }
    .layout.sidebar-closed { grid-template-columns: 1fr; }
    .layout.sidebar-closed .detail-panel { display: none; }

    .group-section {
      background: rgba(13,20,32,0.84);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 18px;
      margin-bottom: 22px;
      box-shadow: 0 14px 36px rgba(0,0,0,0.30);
    }
    .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
    .section-header h2 { margin: 0; font-size: 22px; letter-spacing: -0.03em; }
    .section-header p { margin: 5px 0 0; color: var(--muted); font-size: 13px; }
    .section-count {
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 13px;
      font-weight: 900;
    }

    .table-wrap { overflow-x: auto; border-radius: 16px; border: 1px solid var(--border); }
    table { width: 100%; border-collapse: collapse; min-width: 1260px; background: rgba(7,11,18,0.55); }
    th {
      text-align: left;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      padding: 12px 14px;
      background: rgba(17,27,42,0.96);
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }
    td {
      padding: 12px 14px;
      border-bottom: 1px solid rgba(32,48,73,0.62);
      font-size: 13px;
      white-space: nowrap;
      vertical-align: top;
    }
    tr { cursor: pointer; }
    tr:hover td { background: rgba(78,161,255,0.07); }
    tr.selected td { background: rgba(30,232,138,0.08); }

    .symbol { font-weight: 950; color: white; font-size: 16px; letter-spacing: 0.02em; }
    .pill {
      display: inline-flex;
      padding: 6px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 900;
      border: 1px solid var(--border);
      white-space: normal;
      line-height: 1.35;
    }
    .confirming, .watch { color: var(--green); }
    .caution { color: var(--orange); }
    .risk { color: var(--red); }
    .neutral { color: var(--gray); }
    .pill.confirming, .pill.watch { background: rgba(30,232,138,0.12); border-color: rgba(30,232,138,0.34); }
    .pill.caution { background: rgba(255,173,66,0.14); border-color: rgba(255,173,66,0.36); }
    .pill.risk { background: rgba(255,77,94,0.14); border-color: rgba(255,77,94,0.36); }
    .pill.neutral { background: rgba(148,163,184,0.12); border-color: rgba(148,163,184,0.30); }

    .score, .move, .failure { font-weight: 950; }
    .score-hot { color: var(--yellow); text-shadow: 0 0 14px rgba(255,207,90,0.3); }
    .score-good { color: var(--green); }
    .score-mid { color: var(--blue); }
    .score-weak { color: var(--orange); }
    .score-bad { color: var(--red); }
    .move-fire { color: var(--yellow); }
    .move-up { color: var(--green); }
    .move-down { color: var(--orange); }
    .move-crash { color: var(--red); }
    .move-flat { color: var(--gray); }
    .failure-low { color: var(--green); }
    .failure-mid { color: var(--orange); }
    .failure-high { color: var(--red); }

    .subline, .profile-line {
      margin-top: 4px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.45;
      white-space: normal;
      max-width: 300px;
    }
    .empty { text-align: center; color: var(--muted); padding: 28px; }

    .detail-panel {
      position: sticky;
      top: 18px;
      background: rgba(13,20,32,0.92);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 18px;
      box-shadow: 0 14px 36px rgba(0,0,0,0.35);
      max-height: calc(100vh - 42px);
      overflow-y: auto;
      scrollbar-width: thin;
    }
    .detail-panel::-webkit-scrollbar { width: 8px; }
    .detail-panel::-webkit-scrollbar-thumb { background: rgba(142,160,184,0.45); border-radius: 999px; }
    .detail-title { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
    .detail-symbol { font-size: 28px; font-weight: 950; letter-spacing: -0.03em; }
    .detail-grade {
      font-size: 13px;
      font-weight: 900;
      padding: 8px 11px;
      border-radius: 999px;
      background: rgba(30,232,138,0.12);
      border: 1px solid rgba(30,232,138,0.34);
      color: var(--green);
      white-space: nowrap;
    }
    .detail-help { color: var(--muted); font-size: 13px; line-height: 1.55; margin-bottom: 16px; }
    .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px; }
    .metric { background: rgba(7,11,18,0.56); border: 1px solid rgba(32,48,73,0.72); border-radius: 14px; padding: 12px; }
    .metric-label { color: var(--muted); font-size: 11px; font-weight: 800; margin-bottom: 7px; }
    .metric-value { font-size: 18px; font-weight: 950; }
    .explain-box { margin:12px 0; background: rgba(7,11,18,0.56); border: 1px solid rgba(32,48,73,0.72); border-radius: 16px; padding: 14px; }
    .explain-title { font-size: 14px; font-weight: 950; margin-bottom: 8px; }
    .explain-list { margin: 0; padding-left: 18px; color: var(--text); font-size: 13px; line-height: 1.65; }
    .top-interpretation { font-size: 13px; line-height: 1.65; color: var(--text); }
    .verdict { margin-top: 12px; padding: 14px; border-radius: 16px; border: 1px solid var(--border); background: rgba(255,255,255,0.035); }
    .verdict.good { border-color: rgba(30,232,138,0.36); background: rgba(30,232,138,0.10); }
    .verdict.watch { border-color: rgba(255,207,90,0.36); background: rgba(255,207,90,0.08); }
    .verdict.bad { border-color: rgba(255,77,94,0.36); background: rgba(255,77,94,0.08); }
    .verdict-title { font-weight: 950; margin-bottom: 5px; }
    .verdict-text { color: var(--muted); font-size: 13px; line-height: 1.55; }
    .signal-banner { margin-bottom: 12px; padding: 13px 14px; border-radius: 16px; border: 1px solid var(--border); font-weight: 950; line-height: 1.45; }
    .signal-buy { color: var(--green); background: rgba(30,232,138,0.12); border-color: rgba(30,232,138,0.38); }
    .signal-watch { color: var(--yellow); background: rgba(255,207,90,0.10); border-color: rgba(255,207,90,0.34); }
    .signal-risk { color: var(--red); background: rgba(255,77,94,0.10); border-color: rgba(255,77,94,0.34); }

    .position-banner {
      margin-bottom: 12px;
      padding: 13px 14px;
      border-radius: 16px;
      border: 1px solid var(--border);
      line-height: 1.55;
      font-size: 13px;
      background: rgba(255,255,255,0.035);
    }
    .position-banner.safe { border-color: rgba(30,232,138,0.34); background: rgba(30,232,138,0.08); }
    .position-banner.watch { border-color: rgba(255,207,90,0.36); background: rgba(255,207,90,0.08); }
    .position-banner.danger { border-color: rgba(255,77,94,0.38); background: rgba(255,77,94,0.09); }
    .position-title { font-weight: 950; margin-bottom: 4px; }
    .position-text { color: var(--muted); }

    @media (max-width: 1200px) {
      .summary-grid { grid-template-columns: repeat(2, 1fr); }
      .layout { grid-template-columns: 1fr; }
      .detail-panel { position: relative; top: auto; }
    }
    @media (max-width: 720px) {
      body { padding: 16px; }
      .hero { display: block; }
      .status-box { justify-content: flex-start; margin-top: 14px; }
      .summary-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: 1fr; }
    }
        .market-status-bar {
      margin-bottom: 18px;
      padding: 14px 18px;
      border-radius: 16px;
      background: rgba(13,20,32,0.78);
      border: 1px solid rgba(32,48,73,0.9);
      box-shadow: 0 12px 28px rgba(0,0,0,0.22);
    }

    .market-status-main {
      font-size: 16px;
      font-weight: 950;
      color: var(--text);
    }

    .market-status-sub {
      margin-top: 6px;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.45;
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <h1>🔥 Alpha-Flow V2 실시간 운용 보드</h1>
        <div class="subtitle">상승 지속 후보 실시간 운용판 — 원천 구조, 장중 힘, 실패 압력, 스윙 기대 구간을 함께 표시</div>
      </div>
      <div class="status-box">
        <div class="badge"><span class="live-dot"></span>자동 갱신 ON</div>
        <div class="badge">새로고침: <span id="refreshSec">5</span>초</div>
        <div class="badge">최근 업데이트: <span id="lastUpdate">-</span></div>
      </div>
    </div>
    <div id="marketStatusBar" class="market-status-bar"></div>

    <div id="summary" class="summary-grid"></div>

    <div id="mainLayout" class="layout sidebar-closed">
      <div id="sections"></div>
      <aside id="detailPanel" class="detail-panel">
        <div class="detail-title">
          <div class="detail-symbol">종목 선택</div>
          <div class="detail-grade">대기</div>
        </div>
        <div class="detail-help">
          왼쪽 표에서 종목을 누르면 원천 구조, 장중 힘, 상승 지속 가능성, 스윙 기대 구간을 한글로 풀어서 보여준다.
        </div>
      </aside>
    </div>
  </div>

<script>
const JSON_PATH = "_live_decision_board.json";
const REFRESH_MS = 5000;
const MAX_ROWS = 30;

let CURRENT_DATA = null;
let SELECTED_SYMBOL = null;

const GROUPS = [
  "ACTION_CONFIRMING",
  "ACTION_WATCH",
  "ACTION_CAUTION",
  "ACTION_RISK_OFF"
];

const META = {
  ACTION_CONFIRMING: { title: "🔥 장중 강세 유지", desc: "장중 힘이 붙은 우선 감시 후보", cls: "confirming" },
  ACTION_WATCH: { title: "🟢 관찰", desc: "상승 지속 가능성을 계속 볼 후보", cls: "watch" },
  ACTION_CAUTION: { title: "🟠 주의", desc: "회복은 있으나 구조 부담이 있는 후보", cls: "caution" },
  ACTION_RISK_OFF: { title: "🔴 위험 회피", desc: "장중 실패·매물·하락 전환 위험 후보", cls: "risk" }
};

function esc(v) {
  if (v === null || v === undefined) return "";
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function nval(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function num(v, d = 2) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "-";
  return n.toFixed(d);
}

function scoreClass(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "score-mid";
  if (n >= 88) return "score-hot";
  if (n >= 70) return "score-good";
  if (n >= 50) return "score-mid";
  if (n >= 0) return "score-weak";
  return "score-bad";
}

function liveDelta(item) {
  return nval(item.score) - nval(item.confirmedScore);
}

function deltaText(item) {
  const d = liveDelta(item);
  if (d > 0) return "+" + d.toFixed(2);
  return d.toFixed(2);
}

function deltaClass(item) {
  const d = liveDelta(item);
  if (d >= 5) return "move-fire";
  if (d >= 1) return "move-up";
  if (d <= -5) return "move-crash";
  if (d <= -1) return "move-down";
  return "move-flat";
}

function moveClass(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "move-flat";
  if (n >= 5) return "move-fire";
  if (n >= 1) return "move-up";
  if (n <= -5) return "move-crash";
  if (n <= -1) return "move-down";
  return "move-flat";
}

function failureClass(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "failure-mid";
  if (n >= 65) return "failure-high";
  if (n >= 45) return "failure-mid";
  return "failure-low";
}

function groupKo(v) {
  if (v === "ACTION_CONFIRMING") return "강한 확인 후보";
  if (v === "ACTION_WATCH") return "관찰 후보";
  if (v === "ACTION_CAUTION") return "주의 후보";
  if (v === "ACTION_RISK_OFF") return "위험 회피 후보";
  return "중립";
}

function stateKo(v) {
  const s = String(v || "");
  if (s.includes("REACCELERATION_CONFIRMING")) return "장중 재가속이 확인되는 중";
  if (s.includes("RECOVERY_EXTENSION")) return "회복 후 다시 힘이 붙는 상태";
  if (s.includes("RECOVERY_WATCHLIST")) return "회복 초입 관찰 상태";
  if (s.includes("UNDER_PRESSURE")) return "장중 압박이 생긴 상태";
  if (s.includes("FAILING")) return "장중 회복 실패 위험";
  if (s.includes("BREAKDOWN")) return "하락 전환 위험이 확인되는 상태";
  if (s.includes("DISTRIBUTION")) return "매물 부담이 커지는 상태";
  if (s.includes("CONTINUATION_HOLDING")) return "상승 지속 흐름이 유지되는 상태";
  return "중립 상태";
}

function trajectoryKo(v) {
  const s = String(v || "");

  if (s.includes("RECOVERY")) {
    return "조정 후 다시 살아나는 흐름";
  }

  if (s.includes("ACCELERATION")) {
    return "상승 힘이 강해지는 흐름";
  }

  if (s.includes("DISTRIBUTION")) {
    return "매물/차익실현 압력이 증가하는 흐름";
  }

  if (s.includes("BREAKDOWN")) {
    return "상승 흐름이 무너지는 방향";
  }

  if (s.includes("AGING")) {
    return "상승 흐름이 점점 둔화되는 상태";
  }

  return "최근 흐름 방향 해석 부족";
}

function hierarchyKo(v) {
  const s = String(v || "");

  if (s.includes("ELITE_CONTINUATION")) {
    return "상위 시간축까지 매우 강한 상승 구조";
  }

  if (s.includes("MONTHLY_EXTENDED")) {
    return "월봉 기준 이미 많이 오른 위치";
  }

  if (s.includes("HEALTHY")) {
    return "상위 구조는 건강하게 유지되는 상태";
  }

  if (s.includes("AGING")) {
    return "상위 상승 구조가 둔화되는 상태";
  }

  if (s.includes("DISTRIBUTION")) {
    return "상위 구조에서 매물 압력이 증가하는 상태";
  }

  if (s.includes("TERMINAL")) {
    return "상승 후반부 exhaustion 위험 구간";
  }

  return "상위 시간축 구조 해석 부족";
}

function profileKo(v) {
  const s = String(v || "");
  if (s === "RECOVERY_REACCELERATION_ALIVE") return "회복 후 다시 살아나는 흐름";
  if (s === "TACTICAL_PARABOLIC_ALIVE") return "후반부 고위험 상승 흐름이 아직 살아있음";
  if (s === "CONTINUATION_STILL_ALIVE") return "상승 지속 구조가 아직 유지됨";
  if (s === "ACCELERATION_ALIVE") return "상승 가속이 유지되는 상태";
  if (s === "CONTINUATION_BREAKING") return "상승 지속 구조가 깨지는 중";
  if (s === "LOW_SURVIVABILITY_STRUCTURE") return "오래 유지될 가능성이 낮은 구조";
  if (s === "UNCERTAIN_CONTINUATION") return "방향은 있지만 확신은 부족한 상태";
  if (s === "HIGH_SURVIVABILITY_STRUCTURE") return "오래 유지될 가능성이 높은 구조";
  return "지속 가능성 해석 부족";
}

function riskKo(v) {
  const s = String(v || "");
  if (s === "CONTROLLED_RISK") return "위험이 아직 통제되는 구간";
  if (s === "ELEVATED_RISK") return "위험이 높아지는 구간";
  if (s === "HIGH_VOLATILITY_EXTENSION_RISK") return "변동성이 큰 후반부 상승 부담";
  if (s === "DISTRIBUTION_RISK") return "매물 출회 위험";
  if (s === "STRUCTURAL_BREAKDOWN_RISK") return "구조적 하락 전환 위험";
  if (s === "EXTREME_FAILURE_RISK") return "실패 위험이 매우 큰 상태";
  if (s === "LATE_STAGE_REVERSAL_RISK") return "후반부 반전 위험";
  return "위험 해석 부족";
}

function expectancyKo(v) {
  const s = String(v || "");
  if (s === "SHORT_SWING_BURST") return "짧은 급등 기대 중심";
  if (s === "SWING_CONTINUATION") return "스윙 상승 지속 기대 중심";
  if (s === "MIDTERM_SURVIVABILITY") return "중기 생존 기대 중심";
  if (s === "LONG_DRIFT_CONTINUATION") return "느리지만 길게 이어지는 상승 기대";
  if (s === "NEGATIVE_EXPECTANCY") return "기대값이 불리한 상태";
  if (s === "MIXED_EXPECTANCY") return "시간축별 기대값이 섞인 상태";
  return "기대값 해석 부족";
}

function archetypeKo(v) {
  const s = String(v || "");
  if (s === "STRUCTURAL_CONTINUATION") return "구조적으로 천천히 이어지는 상승형";
  if (s === "RECOVERY_WATCH") return "회복 초입 감시형";
  if (s === "RECOVERY_REACCELERATION") return "조정 후 다시 힘이 붙는 재가속형";
  if (s === "LOW_VOLATILITY_BASE") return "조용히 힘을 모으는 바닥 다지기형";
  if (s === "DISTRIBUTION_PRESSURE") return "매물 부담이 커지는 상승형";
  if (s === "DISTRIBUTION_BREAKDOWN") return "매물 부담 후 하락 전환 위험형";
  if (s === "SLOW_DRIFT_CONTINUATION") return "천천히 우상향하는 지속형";
  if (s === "INSTITUTIONAL_DRIFT") return "기관성 느린 우상향형";
  if (s === "ACCELERATING_CONTINUATION") return "상승 가속형";
  if (s === "TACTICAL_PARABOLIC_CONTINUATION") return "후반부 고위험 고수익 상승형";
  if (s === "LATE_STAGE_CONTINUATION") return "후반부 상승 지속형. 수익 가능성과 위험이 같이 큰 상태";
  return "상태 유형 해석 부족";
}

function operatingModeKo(v) {
  const s = String(v || "");
  if (s === "LONG_SURVIVABILITY_CONTINUATION") return "20~60일 이상 흐름 유지 기대";
  if (s === "MIDTERM_CONTINUATION") return "10~20일 중기 스윙 기대";
  if (s === "SHORT_TERM_BREAKOUT") return "1~5일 빠른 돌파 기대";
  if (s === "SHORT_SWING_CONTINUATION") return "3~10일 짧은 스윙 기대";
  if (s === "SWING_TO_MIDTERM_CONTINUATION") return "10~20일 스윙 지속 기대";
  if (s === "TACTICAL_MOMENTUM") return "짧은 힘으로 대응하는 전술 구간";
  if (s === "TACTICAL_HIGH_RISK_CONTINUATION") return "후반부 고위험 단기 대응 구간";
  if (s === "TACTICAL_DISTRIBUTION_BOUNCE") return "매물 부담 속 짧은 반등 대응";
  if (s === "DISTRIBUTION_RISK_REVIEW") return "매물 부담 검토 필요";
  if (s === "REGIME_CONSTRAINED_REVIEW") return "시장 환경 때문에 보수적 확인 필요";
  if (s === "NO_EXPECTANCY_DATA") return "검증 데이터 부족";
  return "운용 방식 해석 부족";
}

function curveKo(v) {
  const s = String(v || "");
  if (s === "FAST_IGNITION_SHORT_SWING") return "초반에 힘이 빨리 붙는 짧은 스윙형";
  if (s === "HIGH_QUALITY_SWING_CONTINUATION") return "3~20일 스윙 흐름이 건강한 구조";
  if (s === "IGNITION_TO_SWING_CONTINUATION") return "초반 힘이 스윙 흐름으로 이어지는 구조";
  if (s === "INSTITUTIONAL_DRIFT_CONTINUATION") return "기관형으로 천천히 우상향할 가능성";
  if (s === "SLOW_COMPOUNDING_CONTINUATION") return "느리지만 꾸준히 쌓이는 상승 구조";
  if (s === "MIDTERM_SWING_EXPANSION") return "10~20일 구간에서 확장 가능성";
  if (s === "LONG_TAIL_CONTINUATION") return "초반보다 뒤쪽에서 살아나는 긴 꼬리형";
  if (s === "BURST_AND_FADE") return "초반 급등 후 힘이 빠질 수 있는 구조";
  if (s === "TACTICAL_SWING_THEN_DECAY") return "짧은 상승 후 피로가 올 수 있는 구조";
  if (s === "DELAYED_SWING_ACCELERATION") return "늦게 힘이 붙는 스윙 구조";
  if (s === "DELAYED_RECOVERY_CONTINUATION") return "초반은 약하지만 뒤늦게 회복할 수 있는 구조";
  if (s === "WEAK_OR_NEGATIVE_CURVE") return "기대값이 약하거나 불리한 구조";
  if (s === "LOW_SAMPLE_RESEARCH_ONLY") return "비슷한 과거 사례가 부족한 상태";
  if (s === "MIXED_EXPECTANCY_CURVE") return "시간축별 기대값이 섞인 상태";
  return "기대 곡선 해석 부족";
}

function actionKo(v) {
  const s = String(v || "");
  if (s === "PRIMARY_SWING_CANDIDATE") return "핵심 스윙 후보";
  if (s === "SHORT_SWING_FAST_PROFIT") return "짧게 먹고 빠지는 스윙형";
  if (s === "SLOW_SWING_OR_HOLD_WITH_TRAIL") return "천천히 보되 추세 깨지면 줄이는 보유형";
  if (s === "TACTICAL_10D_20D_EXIT_AWARE") return "10~20일 대응하되 피로 신호 확인";
  if (s === "WATCH_FOR_CONFIRMATION") return "추가 확인 후 접근";
  if (s === "WATCHLIST") return "관찰 리스트";
  if (s === "DAY1_TO_DAY5_ONLY") return "1~5일 짧은 대응형";
  if (s === "AVOID") return "회피 우선";
  if (s === "RESEARCH_ONLY") return "과거 사례 부족으로 참고만";
  if (s === "NO_CURVE_DATA") return "기대 곡선 데이터 없음";
  return "중립 관찰";
}

function swingGradeKo(v) {
  const s = String(v || "");
  if (s === "ELITE_SWING_EXPECTANCY") return "스윙 기대값 매우 강함";
  if (s === "HIGH_SWING_EXPECTANCY") return "스윙 기대값 강함";
  if (s === "GOOD_SWING_EXPECTANCY") return "스윙 기대값 양호";
  if (s === "MIXED_SWING_EXPECTANCY") return "스윙 기대값 혼합";
  if (s === "WEAK_SWING_EXPECTANCY") return "스윙 기대값 약함";
  if (s === "LOW_SAMPLE_RESEARCH_ONLY") return "과거 사례 부족";
  return "스윙 기대값 해석 부족";
}

function biasKo(v) {
  const s = String(v || "");
  if (s === "HIGH") return "상승 흐름이 유지될 가능성이 높음";
  if (s === "GOOD") return "상승 흐름 유지 가능성이 양호함";
  if (s === "GOOD_BUT_EXTENSION_RISK") return "좋지만 이미 오른 부담이 있어 추격 주의";
  if (s === "NEUTRAL") return "중립. 추가 확인 필요";
  if (s === "CAUTION") return "주의. 구조 약화 가능성 있음";
  if (s === "AVOID") return "회피 우선. 실패 위험이 큼";
  if (s === "TACTICAL_ONLY") return "짧은 전술 대응만 가능한 상태";
  return "판단 편향 해석 부족";
}
function highPositionKo(v) {
  const s = String(v || "");

  if (s === "GOOD_HIGH_POSITION") {
    return "좋은 고점 상승 지속 구조";
  }

  if (s === "HEALTHY_HIGH_POSITION_BUT_ENTRY_RISK") {
    return "건강하지만 진입 부담 있는 고점";
  }

  if (s === "BAD_HIGH_POSITION") {
    return "위험한 고점 구조";
  }

  if (s === "HIGH_POSITION_DISTRIBUTION_RISK") {
    return "고점 매물 증가 위험";
  }

  if (s === "LOW_SAMPLE_RESEARCH_ONLY") {
    return "과거 사례 부족";
  }

  if (s === "NO_HIGH_POSITION_DATA") {
    return "고점 품질 판단 데이터 부족";
  }

  return "혼합형 고점 구조";
}
function highPositionCategoryKo(v) {
  const s = String(v || "");

  if (s === "INSTITUTIONAL_HIGH_CONTINUATION") {
    return "기관성 continuation이 살아있는 높은 위치";
  }

  if (s === "HEALTHY_BUT_EXTENDED_HIGH") {
    return "좋지만 이미 많이 오른 continuation";
  }

  if (s === "RECOVERY_REACCELERATION_HIGH") {
    return "조정 후 다시 살아나는 재가속 구조";
  }

  if (s === "TACTICAL_FAST_SWING_HIGH") {
    return "짧게 강하게 움직이는 전술형 고점";
  }

  if (s === "DISTRIBUTION_HIGH_RISK") {
    return "매물 부담이 증가하는 위험 구간";
  }

  if (s === "TERMINAL_OR_DANGEROUS_HIGH") {
    return "후반부 exhaustion 위험이 큰 고점";
  }

  if (s === "UNPROVEN_POSITION") {
    return "아직 검증 부족한 위치";
  }

  return "혼합형 continuation 위치";
}


function entryTimingKo(v) {
  const s = String(v || "");

  if (s === "TREND_FOLLOW_WITH_RISK_CONTROL") {
    return "추세 따라가되 손절 기준 반드시 필요";
  }

  if (s === "WATCH_REACCELERATION_CONFIRMATION") {
    return "재가속 확인 후 접근";
  }

  if (s === "SMALL_SIZE_OR_PULLBACK_ONLY") {
    return "추격보다 눌림/소액 접근이 유리";
  }

  if (s === "SHORT_TERM_ONLY") {
    return "짧은 단기 대응만 적합";
  }

  if (s === "DO_NOT_CHASE") {
    return "지금 추격은 위험";
  }

  if (s === "DO_NOT_CHASE_SPIKE") {
    return "급등 추격 금지";
  }

  if (s === "WAIT_FOR_PULLBACK_RECLAIM") {
    return "눌림 후 회복 여부 확인 필요";
  }

  if (s === "RESEARCH_ONLY") {
    return "참고용 관찰 상태";
  }

  return "추가 확인 필요";
}


function continuationStageKo(v) {
  const s = String(v || "");

  if (s === "HEALTHY_CONTINUATION") {
    return "건강한 continuation 진행 구간";
  }

  if (s === "REACCELERATION_PHASE") {
    return "재가속 초기 단계";
  }

  if (s === "EXTENDED_CONTINUATION") {
    return "상당히 진행된 continuation";
  }

  if (s === "TACTICAL_MOMENTUM_PHASE") {
    return "짧은 momentum 대응 구간";
  }

  if (s === "DISTRIBUTION_PHASE") {
    return "distribution 증가 단계";
  }

  if (s === "LATE_STAGE_EXHAUSTION") {
    return "후반부 exhaustion 단계";
  }

  if (s === "UNCONFIRMED_STRUCTURE") {
    return "아직 확정 부족";
  }

  return "중간 continuation 단계";
}
function pressureTrendKo(v) {
  const s = String(v || "");

  if (s === "RECOVERY_PRESSURE_BUILDING") {
    return "회복 압력이 계속 강화되는 중";
  }

  if (s === "RECOVERY_CLUSTER") {
    return "최근 recovery 흐름이 반복되는 중";
  }

  if (s === "DETERIORATION_PERSISTING") {
    return "약화 흐름이 계속 누적되는 중";
  }

  if (s === "DETERIORATION_CLUSTER") {
    return "최근 deterioration 흐름이 반복되는 중";
  }

  if (s === "IMPROVING_PRESSURE") {
    return "실시간 압력이 빠르게 좋아지는 중";
  }

  if (s === "DETERIORATING_PRESSURE") {
    return "실시간 압력이 빠르게 악화되는 중";
  }

  if (s === "PERSISTENT_STRONG_PRESSURE") {
    return "강한 장중 압력이 유지되는 상태";
  }

  if (s === "PERSISTENT_WEAK_PRESSURE") {
    return "약한 장중 압력이 계속 유지되는 상태";
  }

  if (s === "STABLE_PRESSURE") {
    return "장중 압력 변화가 크지 않은 상태";
  }

  return "실시간 압력 해석 부족";
}
function liveStateShortKo(v) {
  const s = String(v || "");

  if (s === "LIVE_REACCELERATION_CONFIRMING") {
    return "재가속 확인";
  }

  if (s === "LIVE_RECOVERY_EXTENSION_WATCH") {
    return "회복 후 확장";
  }

  if (s === "LIVE_RECOVERY_WATCHLIST") {
    return "회복 관찰";
  }

  if (s === "LIVE_CONTINUATION_HOLDING") {
    return "상승 유지";
  }

  if (s === "LIVE_RECOVERY_UNDER_PRESSURE") {
    return "회복 약화";
  }

  if (s === "LIVE_RECOVERY_FAILING_INTRADAY") {
    return "회복 실패";
  }

  if (s === "LIVE_DISTRIBUTION_CONTINUATION") {
    return "매물 증가";
  }

  if (s === "LIVE_BREAKDOWN_CONFIRMING") {
    return "하락 전환";
  }

  return "중립";
}

function expectancyGradeKo(v) {
  const s = String(v || "");

  if (s === "VERY_HIGH") return "매우 높음";
  if (s === "HIGH") return "높음";
  if (s === "MEDIUM") return "보통";
  if (s === "LOW") return "낮음";
  if (s === "VERY_LOW") return "매우 낮음";

  return "-";
}
function recentStatePathKo(v) {
  const raw = String(v || "");

  if (!raw) {
    return "-";
  }

  return raw
    .split(" -> ")
    .map(x => liveStateShortKo(x))
    .join(" → ");
}
function horizonOneLine(item) {
  const h = String(item.bestSwingWindow || item.bestHorizon || "");
  const curve = String(item.expectancyCurveCluster || "");

  if (curve === "FAST_IGNITION_SHORT_SWING") return "3~10일 안에 빠르게 움직일 가능성을 보는 상태";
  if (curve === "INSTITUTIONAL_DRIFT_CONTINUATION") return "20~60일 동안 천천히 우상향할 가능성을 보는 상태";
  if (curve === "SLOW_COMPOUNDING_CONTINUATION") return "짧게 폭발하기보다 천천히 쌓이는 흐름을 보는 상태";
  if (curve === "MIDTERM_SWING_EXPANSION") return "10~20일 구간에서 확장 가능성을 보는 상태";
  if (curve === "LONG_TAIL_CONTINUATION") return "초반보다 뒤쪽에서 살아날 가능성을 보는 상태";
  if (curve === "BURST_AND_FADE") return "초반 급등 후 힘이 빠질 수 있어 짧게 봐야 하는 상태";
  if (curve === "LOW_SAMPLE_RESEARCH_ONLY") return "비슷한 과거 사례가 부족해 참고용으로만 보는 상태";

  if (h === "1d") return "오늘~내일 반응을 주로 보는 상태";
  if (h === "3d") return "3일 안의 빠른 반응을 보는 상태";
  if (h === "5d") return "1주 안의 짧은 스윙을 보는 상태";
  if (h === "10d") return "약 2주 스윙을 보는 상태";
  if (h === "20d") return "약 1개월 스윙 흐름을 보는 상태";
  if (h === "30d") return "1~2개월 중기 흐름을 보는 상태";
  if (h === "60d") return "2~3개월 동안 흐름 유지 가능성을 보는 상태";

  return "아직 뚜렷한 우위 시간축이 부족한 상태";
}

function topInterpretation(item) {
  return `${actionKo(item.preferredAction)} · ${curveKo(item.expectancyCurveCluster)} · ${horizonOneLine(item)} · ${profileKo(item.continuationProfile)}`;
}

function extensionRisk(item) {
  const hierarchy = String(item.hierarchy || "");
  const bias = String(item.bias || "");
  const profile = String(item.continuationProfile || "");
  const curve = String(item.expectancyCurveCluster || "");

  const score = nval(item.score);
  const confirmed = nval(item.confirmedScore);
  const move = nval(item.move);
  const failure = nval(item.failurePressure);
  const survival = nval(item.survivabilityScore);
  const distribution = nval(item.distributionPressure);

  let risk = 0;
  const reasons = [];

  if (hierarchy.includes("MONTHLY_EXTENDED")) {
    risk += 28;
    reasons.push("상위 시간축에서 이미 많이 오른 위치");
  }

  if (hierarchy.includes("TERMINAL") || hierarchy.includes("LATE_STAGE")) {
    risk += 30;
    reasons.push("후반부 과열/피로 구간 가능성");
  }

  if (hierarchy.includes("AGING")) {
    risk += 16;
    reasons.push("상승 흐름이 오래 진행된 상태");
  }

  if (bias === "GOOD_BUT_EXTENSION_RISK" || bias === "TACTICAL_ONLY") {
    risk += 22;
    reasons.push("좋지만 추격 부담이 있는 판정");
  }

  if (profile === "LOW_SURVIVABILITY_STRUCTURE") {
    risk += 18;
    reasons.push("오래 유지될 가능성이 낮게 평가됨");
  }

  if (score >= 85 && confirmed >= 80 && move >= 2) {
    risk += 18;
    reasons.push("점수와 장중 상승률이 동시에 높아 추격 매수 유혹이 큰 구간");
  }

  if (failure >= 45) {
    risk += 18;
    reasons.push("실패 압력이 중간 이상");
  }

  if (distribution >= 30) {
    risk += 14;
    reasons.push("매물 압력이 존재");
  }

  if (curve === "FAST_IGNITION_SHORT_SWING" || curve === "BURST_AND_FADE" || curve === "TACTICAL_SWING_THEN_DECAY") {
    risk += 16;
    reasons.push("짧게 움직인 뒤 힘이 약해질 수 있는 기대 곡선");
  }

  if (risk >= 65) {
    return {
      cls: "danger",
      label: "고점 추격 위험 큼",
      text: "점수는 높아도 현재 위치가 높거나 실패 압력이 있어 바로 따라붙기보다 눌림·재가속 확인이 필요하다.",
      reasons
    };
  }

  if (risk >= 38) {
    return {
      cls: "watch",
      label: "추격 주의",
      text: "구조는 살아있지만 가격 위치 부담이 있다. 신규 진입은 분할·짧은 손절 기준이 필요하다.",
      reasons
    };
  }

  return {
    cls: "safe",
    label: "추격 부담 낮음",
    text: "현재 정보 기준으로는 고점 추격 위험보다 구조 유지 여부를 우선 확인하면 되는 구간이다.",
    reasons
  };
}

function positionKo(item) {
  const e = extensionRisk(item);
  return e.label;
}
function marketEnvironmentKo(v) {
  const s = String(v || "");

  if (s === "CONTINUATION_FRIENDLY_ENVIRONMENT") {
    return "상승 지속 종목이 살아남기 좋은 시장";
  }

  if (s === "SELECTIVE_CONTINUATION_ENVIRONMENT") {
    return "강한 종목만 선별적으로 살아남는 시장";
  }

  if (s === "MIXED_MARKET_ENVIRONMENT") {
    return "상승/약세 흐름이 섞여 있는 혼합 시장";
  }

  if (s === "CONTINUATION_UNFRIENDLY_ENVIRONMENT") {
    return "상승 지속 구조에 불리한 시장";
  }

  return "시장 환경 해석 부족";
}


function marketPressureKo(v) {
  const s = String(v || "");

  if (s === "MARKET_RECOVERY_PRESSURE_BUILDING") {
    return "시장 전체 recovery 압력이 강화되는 중";
  }

  if (s === "MARKET_STABLE_PRESSURE") {
    return "시장 압력 변화가 크지 않은 상태";
  }

  if (s === "MARKET_UNDER_PRESSURE") {
    return "시장 전체 실패 압력이 증가하는 상태";
  }

  return "시장 압력 해석 부족";
}


function marketRiskKo(v) {
  const s = String(v || "");

  if (s === "RISK_ON_CONTINUATION_ENVIRONMENT") {
    return "growth continuation에 우호적인 위험 선호 환경";
  }

  if (s === "NEUTRAL_RISK_ENVIRONMENT") {
    return "중립적인 위험 환경";
  }

  if (s === "RISK_OFF_OR_DISTRIBUTION_ENVIRONMENT") {
    return "risk-off 또는 distribution 위험 환경";
  }

  return "시장 위험 해석 부족";
}
function entryGuideKo(item) {
  const e = extensionRisk(item);
  const action = String(item.preferredAction || "");
  const curve = String(item.expectancyCurveCluster || "");

  if (e.cls === "danger") {
    if (curve === "FAST_IGNITION_SHORT_SWING") {
      return "신규 추격은 위험. 들어간다면 3~10일 짧은 스윙 전제로 빠른 익절/손절 기준이 필요하다.";
    }
    return "신규 추격보다는 눌림 후 다시 힘이 붙는지 확인하는 쪽이 안전하다.";
  }

  if (e.cls === "watch") {
    if (action === "SLOW_SWING_OR_HOLD_WITH_TRAIL") {
      return "한 번에 따라붙기보다 작게 보거나, 눌림 후 추세가 유지되는지 확인하는 접근이 맞다.";
    }
    return "관찰 우선. 장중 고점 돌파보다 눌림 이후 회복력이 더 중요하다.";
  }

  return "위치 부담은 크지 않다. 다만 실패 압력과 시장 상태가 같이 좋아지는지 확인해야 한다.";
}

function verdictFor(item) {
  const score = nval(item.score);
  const confirmed = nval(item.confirmedScore);
  const delta = liveDelta(item);
  const failure = nval(item.failurePressure);
  const group = String(item.decisionGroup || "");
  const profile = String(item.continuationProfile || "");

  if (score >= 88 && confirmed >= 80 && delta >= 0 && failure <= 45 && group !== "ACTION_RISK_OFF") {
    return {
      cls: "good",
      title: "매수 검토 가능",
      text: "원천 구조와 장중 흐름이 같이 좋다. 다만 실제 매수는 시장 지수, 손절 기준, 진입 가격까지 같이 확인해야 한다."
    };
  }

  if (profile.includes("ALIVE") && score >= 70 && failure <= 55) {
    return {
      cls: "watch",
      title: "우선 관찰 후보",
      text: "상승 지속성은 살아있지만 장중 보정 또는 실패 압력 확인이 더 필요하다."
    };
  }

  if (group === "ACTION_RISK_OFF" || failure >= 55) {
    return {
      cls: "bad",
      title: "매수 보류",
      text: "점수보다 실패 압력이나 장중 약화가 더 중요하다. 지금은 따라가기보다 관찰이 안전하다."
    };
  }

  return {
    cls: "watch",
    title: "관찰 후보",
    text: "구조는 살아있지만 장중 확인이 충분하지 않다. 상승률, 실패 압력, 시장 상태가 더 좋아지는지 확인해야 한다."
  };
}

function signalFor(item) {
  const score = nval(item.score);
  const confirmed = nval(item.confirmedScore);
  const delta = liveDelta(item);
  const failure = nval(item.failurePressure);
  const group = String(item.decisionGroup || "");
  const profile = String(item.continuationProfile || "");

  if (score >= 90 && confirmed >= 85 && delta >= 0 && failure <= 45 && group !== "ACTION_RISK_OFF") {
    return { cls: "signal-buy", text: "🟢 강한 매수 검토: 원천 구조와 장중 힘이 같이 맞는다." };
  }

  if (score >= 80 && confirmed >= 80 && failure <= 50 && profile.includes("ALIVE")) {
    return { cls: "signal-watch", text: "🟡 우선 감시: 상승 지속성은 살아있지만 추가 확인이 필요하다." };
  }

  if (group === "ACTION_RISK_OFF" || failure >= 55) {
    return { cls: "signal-risk", text: "🔴 보류: 실패 압력이나 장중 약화가 보여서 추격은 위험하다." };
  }

  return { cls: "signal-watch", text: "🟡 관찰: 아직 확실한 매수 확인은 부족하다." };
}

function explainReasons(item) {
  const reasons = [];
  const score = nval(item.score);
  const confirmed = nval(item.confirmedScore);
  const delta = liveDelta(item);
  const move = nval(item.move);
  const failure = nval(item.failurePressure);
  const breakout = nval(item.breakoutPressure);
  const distribution = nval(item.distributionPressure);
  const profile = String(item.continuationProfile || "");

  if (confirmed >= 85) reasons.push("원천 구조 점수가 높다. 확정봉 기준 상승 지속 구조가 강하다.");
  else if (confirmed >= 70) reasons.push("원천 구조는 양호하지만 최상급은 아니다.");
  else reasons.push("원천 구조 점수가 강하지 않다.");

  if (delta > 3) reasons.push(`장중 보정이 +${delta.toFixed(2)}점으로 원천 구조를 더 강화하고 있다.`);
  else if (delta > 0) reasons.push(`장중 보정이 +${delta.toFixed(2)}점으로 약하게 우호적이다.`);
  else if (delta < -5) reasons.push(`장중 보정이 ${delta.toFixed(2)}점으로 크게 깎이고 있다. 장중 약화가 강하다.`);
  else if (delta < 0) reasons.push(`장중 보정이 ${delta.toFixed(2)}점으로 소폭 부정적이다.`);
  else reasons.push("장중 보정 영향은 거의 중립이다.");

  if (score >= 88) {
    if (delta >= 0) reasons.push("실시간 보정 점수가 높고 장중 흐름도 우호적이다.");
    else if (delta <= -5) reasons.push("점수는 높지만 장중 보정이 크게 약화되고 있어 추가 확인이 필요하다.");
    else reasons.push("점수는 높지만 장중 흐름은 아직 완전히 강하지 않다.");
  } else if (score >= 70) reasons.push("실시간 보정 점수는 양호하다.");
  else reasons.push("실시간 보정 점수는 아직 강한 매수 판단까지 부족하다.");

  if (move >= 2) reasons.push("현재 상승률이 강하다. 장중 수급 확인이 붙고 있다.");
  else if (move >= 0.5) reasons.push("현재 상승률은 약하지만 플러스 흐름이다.");
  else if (move > -0.5) reasons.push("현재 움직임은 거의 보합이다. 추가 확인이 필요하다.");
  else reasons.push("현재 움직임이 음수다. 장중 힘이 약할 수 있다.");

  if (failure >= 55) reasons.push("실패 압력이 높다. 추격 매수 위험이 크다.");
  else if (failure >= 45) reasons.push("실패 압력이 중간 이상이다. 매수 전 추가 확인이 필요하다.");
  else reasons.push("실패 압력이 낮은 편이다.");

  if (breakout >= 55) reasons.push("돌파 압력이 양호하다.");
  if (distribution >= 30) reasons.push("매물 부담이 존재한다.");
  if (profile) reasons.push(`상승 지속성: ${profileKo(profile)}`);
  if (item.expectancyCurveCluster) reasons.push(`스윙 기대 구조: ${curveKo(item.expectancyCurveCluster)}`);
  if (item.preferredAction) reasons.push(`권장 대응: ${actionKo(item.preferredAction)}`);

  const ext = extensionRisk(item);
  reasons.push(`현재 위치 판단: ${ext.label}`);
  if (ext.reasons.length > 0) {
    reasons.push(`추격 위험 근거: ${ext.reasons.slice(0, 3).join(" / ")}`);
  }

  return reasons;
}

function sortedRows(items) {
  return [...items].sort((a, b) => {
    const scoreA = Number(a.score || 0);
    const scoreB = Number(b.score || 0);
    const moveA = Number(a.move || 0);
    const moveB = Number(b.move || 0);
    return (scoreB - scoreA) || (moveB - moveA);
  }).slice(0, MAX_ROWS);
}
function renderMarketStatus(data) {
  const market = data.marketContext || {};

  document.getElementById("marketStatusBar").innerHTML = `
    <div class="market-status-main">
      현재 감시 종목 상태: ${esc(marketEnvironmentKo(market.marketContinuationEnvironment))}
    </div>
    <div class="market-status-sub">
      ${esc(marketPressureKo(market.marketPressureState))}
      ·
      ${esc(marketRiskKo(market.riskEnvironment))}
      · 점수 ${esc(market.marketContextScore || "-")}
    </div>
  `;
}
function renderSummary(data) {
  const counts = data.counts || {};

  document.getElementById("summary").innerHTML = GROUPS.map(group => {
    const meta = META[group];
    const count = counts[group] || 0;

    return `
      <div class="summary-card ${meta.cls}">
        <div class="summary-title">${meta.title}</div>
        <div class="summary-count">${count}</div>
        <div class="summary-desc">${meta.desc}</div>
      </div>
    `;
  }).join("");
}

function renderDetail(item) {
  const panel = document.getElementById("detailPanel");

  if (!item) {
    panel.innerHTML = `
      <div class="detail-title">
        <div class="detail-symbol">종목 선택</div>
        <div class="detail-grade">대기</div>
      </div>
      <div class="detail-help">
        왼쪽 표에서 종목을 누르면 원천 구조, 장중 힘, 상승 지속 가능성, 스윙 기대 구간을 한글로 풀어서 보여준다.
      </div>
    `;
    return;
  }

  const verdict = verdictFor(item);
  const signal = signalFor(item);
  const reasons = explainReasons(item);

  panel.innerHTML = `
    <div class="detail-title">
      <div class="detail-symbol">${esc(item.symbol)}</div>
      <div class="detail-grade">${groupKo(item.decisionGroup)}</div>
    </div>

    <div class="detail-help">
      매수 버튼이 아니라 판단 근거 확인용이다. 점수가 높아도 원천 구조, 장중 힘, 실패 압력, 시장 상태를 같이 봐야 한다.
    </div>

    <div class="signal-banner ${signal.cls}">${signal.text}</div>

    <div class="position-banner ${extensionRisk(item).cls}">
      <div class="position-title">📍 현재 위치 판단: ${esc(extensionRisk(item).label)}</div>
      <div class="position-text">${esc(extensionRisk(item).text)}</div>
      <div class="position-text" style="margin-top:6px;">진입 가이드: ${esc(entryGuideKo(item))}</div>
    </div>

    <div class="explain-box">
      <div class="explain-title">한 줄 운용 해석</div>
      <div class="top-interpretation">${esc(topInterpretation(item))}</div>
    </div>

    <div class="metric-grid">
      <div class="metric">
        <div class="metric-label">구조 + 장중 강도 점수<br><span style="font-size:11px;color:#8ea0b8;">현재 구조와 장중 흐름의 강도</span></div>
        <div class="metric-value ${scoreClass(item.score)}">${num(item.score)}</div>
        <div style="margin-top:6px;font-size:12px;line-height:1.45;color:#8ea0b8;">
          원천 구조 점수: <span class="${scoreClass(item.confirmedScore)}" style="font-weight:900;">${num(item.confirmedScore)}</span><br>
          장중 보정: <span class="${deltaClass(item)}" style="font-weight:900;">${deltaText(item)}</span>
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">지속 가능성 점수<br><span style="font-size:11px;color:#8ea0b8;">상승 흐름이 버틸 가능성</span></div>
        <div class="metric-value ${scoreClass(item.survivabilityScore)}">${num(item.survivabilityScore)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">${esc(profileKo(item.continuationProfile))}</div>
      </div>
            <div class="metric">
        <div class="metric-label">실전 진입 판단<br><span style="font-size:11px;color:#8ea0b8;">현재 위치 기준 대응 해석</span></div>
        <div class="metric-value" style="font-size:18px;">
          ${esc(positionKo(item))}
        </div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${esc(entryGuideKo(item))}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">단기 기대값<br><span style="font-size:11px;color:#8ea0b8;">1~3일 단기 강세 흐름 기대</span></div>
        <div class="metric-value ${scoreClass(item.shortTermExpectancyScore)}">${num(item.shortTermExpectancyScore)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${esc(expectancyGradeKo(item.shortTermExpectancyGrade))}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">스윙 기대값<br><span style="font-size:11px;color:#8ea0b8;">3~20일 상승 지속 기대</span></div>
        <div class="metric-value ${scoreClass(item.swingExpectancyScore)}">${num(item.swingExpectancyScore)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${esc(expectancyGradeKo(item.swingExpectancyGrade))}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">중기 지속 기대값<br><span style="font-size:11px;color:#8ea0b8;">20~60일 중기 생존 가능성 기대</span></div>
        <div class="metric-value ${scoreClass(item.midTermExpectancyScore)}">${num(item.midTermExpectancyScore)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${esc(expectancyGradeKo(item.midTermExpectancyGrade))}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">현재 상승률<br><span style="font-size:11px;color:#8ea0b8;">높을수록 장중 수급 강함</span></div>
        <div class="metric-value ${moveClass(item.move)}">${num(item.move)}%</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.move) >= 3 ? "강한 장중 상승" : nval(item.move) >= 1 ? "양호한 흐름" : nval(item.move) >= -0.5 ? "보합권" : "장중 약세"}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">실패 압력<br><span style="font-size:11px;color:#8ea0b8;">낮을수록 안정</span></div>
        <div class="metric-value ${failureClass(item.failurePressure)}">${num(item.failurePressure)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.failurePressure) <= 35 ? "추세 안정 구간" : nval(item.failurePressure) <= 45 ? "정상 흔들림 구간" : nval(item.failurePressure) <= 55 ? "실패 위험 증가" : "붕괴 위험 높음"}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">돌파 압력<br><span style="font-size:11px;color:#8ea0b8;">높을수록 위로 밀 힘이 강함</span></div>
        <div class="metric-value">${num(item.breakoutPressure)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.breakoutPressure) >= 70 ? "강한 돌파 압력" : nval(item.breakoutPressure) >= 55 ? "양호한 돌파" : nval(item.breakoutPressure) >= 40 ? "보통 수준" : "돌파 힘 부족"}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">매물 압력<br><span style="font-size:11px;color:#8ea0b8;">낮을수록 좋음</span></div>
        <div class="metric-value">${num(item.distributionPressure)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.distributionPressure) <= 15 ? "매물 부담 낮음" : nval(item.distributionPressure) <= 30 ? "보통 수준" : nval(item.distributionPressure) <= 45 ? "매물 부담 증가" : "매물 위험 높음"}
        </div>
      </div>
    </div>

    <div class="explain-box">
      <div class="explain-title">상태 해석</div>
      <ul class="explain-list">
        <li>장중 상태: ${stateKo(item.liveMergedState)}</li>
        <li>최근 흐름: ${trajectoryKo(item.trajectory)}</li>
        <li>상위 구조: ${hierarchyKo(item.hierarchy)}</li>
        <li>현재 위치: ${positionKo(item)}</li>
        <li>진입 가이드: ${entryGuideKo(item)}</li>
        <li>판단 편향: ${biasKo(item.bias)}</li>
        <li>상승 지속성: ${profileKo(item.continuationProfile)}</li>
        <li>기대 구간: ${expectancyKo(item.expectancyProfile)}</li>
        <li>위험 성격: ${riskKo(item.riskProfile)}</li>
        <li>상태 유형: ${archetypeKo(item.continuationArchetype)}</li>

        <li>고점 품질: ${highPositionKo(item.highPositionQuality)}</li>
        <li>고점 위치 유형: ${highPositionCategoryKo(item.highPositionCategory)}</li>
        <li>진입 타이밍: ${entryTimingKo(item.entryTimingState)}</li>
        <li>현재 continuation 단계: ${continuationStageKo(item.continuationStage)}</li>
        <li>실시간 압력 흐름: ${pressureTrendKo(item.livePressureTrend)}</li>
        <li>회복 흐름: ${item.recoveryPersistenceCount || 0}</li>
        <li>약화 흐름: ${item.deteriorationPersistenceCount || 0}</li>
        <li>최근 상태 흐름: ${esc(recentStatePathKo(item.recentStatePath))}</li>
        <li>고점 해석: ${esc(item.positionInterpretation || "-")}</li>
        <li>대응 가이드: ${esc(item.positionActionGuide || "-")}</li>

        <li>운용 방식: ${operatingModeKo(item.operatingMode)}</li>
        <li>우위 시간축: ${horizonOneLine(item)}</li>
        <li>스윙 기대 구조: ${curveKo(item.expectancyCurveCluster)}</li>
        <li>스윙 등급: ${swingGradeKo(item.swingGrade)}</li>
        <li>권장 대응: ${actionKo(item.preferredAction)}</li>
      </ul>
      <div class="profile-line" style="margin-top:10px;">
        내부값: ${esc(item.trajectory || "-")} / ${esc(item.hierarchy || "-")} / ${esc(item.expectancyCurveCluster || "-")} / ${esc(item.preferredAction || "-")}
      </div>
    </div>

    <div class="explain-box">
      <div class="explain-title">왜 이렇게 판단하는가</div>
      <ul class="explain-list">${reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul>
    </div>

    <div class="verdict ${verdict.cls}">
      <div class="verdict-title">${verdict.title}</div>
      <div class="verdict-text">${verdict.text}</div>
    </div>
  `;
}

function renderTable(group, items) {
  const meta = META[group];
  const rows = sortedRows(items || []);

  let body = rows.map(item => `
    <tr data-symbol="${esc(item.symbol)}" onclick="selectSymbol('${esc(item.symbol)}')">
      <td class="symbol">${esc(item.symbol)}</td>
      <td>
        <div><span class="score ${scoreClass(item.score)}">${num(item.score)}</span></div>
        <div class="subline">원천 ${num(item.confirmedScore)} / <span class="${deltaClass(item)}">장중 ${deltaText(item)}</span></div>
      </td>
      <td>
        <div><span class="score ${scoreClass(item.survivabilityScore)}">${num(item.survivabilityScore)}</span></div>
        <div class="profile-line">${esc(profileKo(item.continuationProfile))}</div>
      </td>
      <td><span class="move ${moveClass(item.move)}">${num(item.move)}%</span></td>
      <td><span class="pill ${meta.cls}">${esc(stateKo(item.liveMergedState))}</span></td>
      <td>
        <div>${esc(trajectoryKo(item.trajectory))}</div>
        <div class="profile-line">${esc(hierarchyKo(item.hierarchy))}</div>
        <div class="profile-line">위치: ${esc(positionKo(item))}</div>
      </td>
      <td>
        <div><span class="pill watch">${esc(horizonOneLine(item))}</span></div>
        <div class="profile-line">${esc(curveKo(item.expectancyCurveCluster))}</div>
        <div class="profile-line">${esc(actionKo(item.preferredAction))}</div>
      </td>
      <td><span class="failure ${failureClass(item.failurePressure)}">${num(item.failurePressure)}</span></td>
    </tr>
  `).join("");

  if (!body) {
    body = `<tr><td colspan="8" class="empty">No symbols</td></tr>`;
  }

  return `
    <section class="group-section">
      <div class="section-header">
        <div>
          <h2>${meta.title}</h2>
          <p>${meta.desc}</p>
        </div>
        <span class="section-count">${items.length}</span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th>점수 / 장중 변화</th>
              <th>지속 가능성</th>
              <th>상승률</th>
              <th>장중 상태</th>
              <th>최근 흐름 / 상위 구조</th>
              <th>스윙 기대 구간</th>
              <th>실패 압력</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </section>
  `;
}

function findSymbol(symbol) {
  if (!CURRENT_DATA) return null;
  const board = CURRENT_DATA.board || {};

  for (const group of GROUPS) {
    const rows = board[group] || [];
    const found = rows.find(x => x.symbol === symbol);
    if (found) return found;
  }

  return null;
}

function selectSymbol(symbol) {
  const layout = document.getElementById("mainLayout");

  if (SELECTED_SYMBOL === symbol) {
    SELECTED_SYMBOL = null;
    renderDetail(null);
    if (layout) layout.classList.add("sidebar-closed");
    document.querySelectorAll("tr.selected").forEach(row => row.classList.remove("selected"));
    return;
  }

  SELECTED_SYMBOL = symbol;
  renderDetail(findSymbol(symbol));
  if (layout) layout.classList.remove("sidebar-closed");

  document.querySelectorAll("tr.selected").forEach(row => row.classList.remove("selected"));
  document.querySelectorAll(`tr[data-symbol="${CSS.escape(symbol)}"]`).forEach(row => row.classList.add("selected"));
}

function renderSections(data) {
  const board = data.board || {};
  document.getElementById("sections").innerHTML = GROUPS.map(group => renderTable(group, board[group] || [])).join("");

  if (SELECTED_SYMBOL) {
    renderDetail(findSymbol(SELECTED_SYMBOL));
  }
}

async function loadBoard() {
  try {
    const url = JSON_PATH + "?t=" + Date.now();
    const res = await fetch(url);
    if (!res.ok) throw new Error("fetch failed: " + res.status);

    const data = await res.json();
    CURRENT_DATA = data;
    renderMarketStatus(data);
    renderSummary(data);
    renderSections(data);
    document.getElementById("lastUpdate").textContent = new Date().toLocaleTimeString();
  } catch (e) {
    document.getElementById("lastUpdate").textContent = "ERROR";
    console.error(e);
  }
}

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
