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

    _ = load_json(INPUT_PATH)
    generated_at = datetime.now(timezone.utc).isoformat()

    # 중요:
    # 기존 대시보드 레이아웃/상세패널/시그널 패널은 유지한다.
    # 이번 업그레이드는 score / confirmedScore / live delta / survivability profile 표시만 추가한다.
    html = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Alpha-Flow V2 Live Symbol Monitor</title>
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

    .page {
      max-width: 1500px;
      margin: 0 auto;
    }

    .hero {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 20px;
      margin-bottom: 20px;
    }

    h1 {
      margin: 0;
      font-size: 32px;
      letter-spacing: -0.04em;
    }

    .subtitle {
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
    }

    .status-box {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

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

    .summary-title {
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }

    .summary-count {
      font-size: 34px;
      font-weight: 950;
      margin-top: 6px;
    }

    .summary-desc {
      color: var(--muted);
      font-size: 12px;
      margin-top: 5px;
      line-height: 1.4;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 390px;
      gap: 18px;
      align-items: start;
    }

    .group-section {
      background: rgba(13,20,32,0.84);
      border: 1px solid var(--border);
      border-radius: 22px;
      padding: 18px;
      margin-bottom: 22px;
      box-shadow: 0 14px 36px rgba(0,0,0,0.30);
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }

    .section-header h2 {
      margin: 0;
      font-size: 22px;
      letter-spacing: -0.03em;
    }

    .section-header p {
      margin: 5px 0 0;
      color: var(--muted);
      font-size: 13px;
    }

    .section-count {
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 8px 13px;
      font-weight: 900;
    }

    .table-wrap {
      overflow-x: auto;
      border-radius: 16px;
      border: 1px solid var(--border);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 1120px;
      background: rgba(7,11,18,0.55);
    }

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

    .symbol {
      font-weight: 950;
      color: white;
      font-size: 16px;
      letter-spacing: 0.02em;
    }

    .pill {
      display: inline-flex;
      padding: 6px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 900;
      border: 1px solid var(--border);
    }

    .confirming, .watch { color: var(--green); }
    .caution { color: var(--orange); }
    .risk { color: var(--red); }
    .neutral { color: var(--gray); }

    .pill.confirming, .pill.watch {
      background: rgba(30,232,138,0.12);
      border-color: rgba(30,232,138,0.34);
    }

    .pill.caution {
      background: rgba(255,173,66,0.14);
      border-color: rgba(255,173,66,0.36);
    }

    .pill.risk {
      background: rgba(255,77,94,0.14);
      border-color: rgba(255,77,94,0.36);
    }

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

    .trend-good { color: var(--green); font-weight: 900; }
    .trend-bad { color: var(--red); font-weight: 900; }
    .trend-flat { color: var(--gray); font-weight: 800; }

    .subline {
      margin-top: 4px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.45;
    }

    .profile-line {
      margin-top: 4px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.45;
      max-width: 260px;
      white-space: normal;
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

    .detail-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

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
    .metric {
      background: rgba(7,11,18,0.56);
      border: 1px solid rgba(32,48,73,0.72);
      border-radius: 14px;
      padding: 12px;
    }

    .metric-label { color: var(--muted); font-size: 11px; font-weight: 800; margin-bottom: 7px; }
    .metric-value { font-size: 18px; font-weight: 950; }

    .explain-box {
      margin-top: 12px;
      background: rgba(7,11,18,0.56);
      border: 1px solid rgba(32,48,73,0.72);
      border-radius: 16px;
      padding: 14px;
    }

    .explain-title { font-size: 14px; font-weight: 950; margin-bottom: 8px; }
    .explain-list { margin: 0; padding-left: 18px; color: var(--text); font-size: 13px; line-height: 1.65; }

    .verdict {
      margin-top: 12px;
      padding: 14px;
      border-radius: 16px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.035);
    }

    .verdict.good { border-color: rgba(30,232,138,0.36); background: rgba(30,232,138,0.10); }
    .verdict.watch { border-color: rgba(255,207,90,0.36); background: rgba(255,207,90,0.08); }
    .verdict.bad { border-color: rgba(255,77,94,0.36); background: rgba(255,77,94,0.08); }
    .verdict-title { font-weight: 950; margin-bottom: 5px; }
    .verdict-text { color: var(--muted); font-size: 13px; line-height: 1.55; }

    .signal-banner {
      margin-bottom: 12px;
      padding: 13px 14px;
      border-radius: 16px;
      border: 1px solid var(--border);
      font-weight: 950;
      line-height: 1.45;
    }

    .signal-buy { color: var(--green); background: rgba(30,232,138,0.12); border-color: rgba(30,232,138,0.38); }
    .signal-watch { color: var(--yellow); background: rgba(255,207,90,0.10); border-color: rgba(255,207,90,0.34); }
    .signal-risk { color: var(--red); background: rgba(255,77,94,0.10); border-color: rgba(255,77,94,0.34); }

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
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div>
        <h1>🔥 Alpha-Flow V2 Live Symbol Monitor</h1>
        <div class="subtitle">상위 후보 실시간 감시판 — 원천 구조 점수와 Live 보정 변화를 함께 표시</div>
      </div>
      <div class="status-box">
        <div class="badge"><span class="live-dot"></span>Auto Update ON</div>
        <div class="badge">refresh: <span id="refreshSec">5</span>s</div>
        <div class="badge">last update: <span id="lastUpdate">-</span></div>
      </div>
    </div>

    <div id="summary" class="summary-grid"></div>

    <div class="layout">
      <div id="sections"></div>
      <aside id="detailPanel" class="detail-panel">
        <div class="detail-title">
          <div class="detail-symbol">종목 선택</div>
          <div class="detail-grade">대기</div>
        </div>
        <div class="detail-help">
          왼쪽 표에서 종목을 누르면 원천 구조 점수, Live 보정 점수, 추세 지속 상태, 실패 위험을 한글로 풀어서 보여준다.
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
  ACTION_CONFIRMING: { title: "🔥 CONFIRMING", desc: "즉시 강한 재가속 확인 후보", cls: "confirming" },
  ACTION_WATCH: { title: "🟢 WATCH", desc: "실시간 관찰 핵심 후보", cls: "watch" },
  ACTION_CAUTION: { title: "🟠 CAUTION", desc: "회복은 있으나 구조 부담", cls: "caution" },
  ACTION_RISK_OFF: { title: "🔴 RISK OFF", desc: "장중 실패/분산/붕괴 위험", cls: "risk" }
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

function trendClass(v) {
  const s = String(v || "");
  if (s.includes("IMPROVING") || s.includes("BUILDING") || s.includes("STRONG")) return "trend-good";
  if (s.includes("DETERIORATING") || s.includes("WEAK") || s.includes("PERSISTING")) return "trend-bad";
  return "trend-flat";
}

function stateKo(v) {
  const s = String(v || "");
  if (s.includes("TACTICAL_PARABOLIC")) return "고위험 고수익 후반부 continuation 감시 상태";
  if (s.includes("RECOVERY_EXTENSION")) return "회복 이후 재가속 관찰 상태";
  if (s.includes("RECOVERY_WATCHLIST")) return "회복 초입 관찰 상태";
  if (s.includes("UNDER_PRESSURE")) return "장중 압박 발생";
  if (s.includes("FAILING")) return "장중 실패 위험";
  if (s.includes("BREAKDOWN")) return "붕괴 확인 위험";
  if (s.includes("DISTRIBUTION")) return "분산/매물 부담";
  if (s.includes("CONTINUATION_HOLDING")) return "추세 지속이 유지되는 상태";
  return "중립 상태";
}

function trajectoryKo(v) {
  const s = String(v || "");
  if (s.includes("RECOVERY")) return "최근 흐름이 회복 방향으로 이어지는 중";
  if (s.includes("ACCELERATING")) return "가속 흐름";
  if (s.includes("DISTRIBUTION")) return "매물 출회 흐름";
  if (s.includes("BREAKDOWN")) return "하락 지속 흐름";
  if (s.includes("STABLE")) return "안정적인 추세 지속 흐름";
  return "명확한 흐름 부족";
}

function profileKo(v) {
  const s = String(v || "");
  if (s === "RECOVERY_REACCELERATION_ALIVE") return "회복 후 재가속 continuation이 아직 살아있는 상태";
  if (s === "TACTICAL_PARABOLIC_ALIVE") return "고위험 후반부지만 아직 momentum이 살아있는 상태";
  if (s === "CONTINUATION_STILL_ALIVE") return "추세 지속 구조가 아직 살아있는 상태";
  if (s === "ACCELERATION_ALIVE") return "가속 continuation이 유지되는 상태";
  if (s === "CONTINUATION_BREAKING") return "continuation이 깨지는 중";
  if (s === "LOW_SURVIVABILITY_STRUCTURE") return "생존 가능성이 낮은 구조";
  if (s === "UNCERTAIN_CONTINUATION") return "살아있지만 확정성이 부족한 continuation";
  return "profile 해석 부족";
}

function riskKo(v) {
  const s = String(v || "");
  if (s === "CONTROLLED_RISK") return "위험이 통제되는 구간";
  if (s === "ELEVATED_RISK") return "위험이 높아지는 구간";
  if (s === "HIGH_VOLATILITY_EXTENSION_RISK") return "변동성 큰 후반부 extension 위험";
  if (s === "DISTRIBUTION_RISK") return "매물 출회 위험";
  if (s === "STRUCTURAL_BREAKDOWN_RISK") return "구조적 붕괴 위험";
  if (s === "EXTREME_FAILURE_RISK") return "극단적 실패 위험";
  if (s === "LATE_STAGE_REVERSAL_RISK") return "후반부 반전 위험";
  return "위험 profile 해석 부족";
}

function expectancyKo(v) {
  const s = String(v || "");
  if (s === "SHORT_SWING_BURST") return "단기 급등 기대값 중심";
  if (s === "SWING_CONTINUATION") return "스윙 continuation 기대값 중심";
  if (s === "MIDTERM_SURVIVABILITY") return "중기 생존 기대값 중심";
  if (s === "LONG_DRIFT_CONTINUATION") return "느리지만 긴 continuation 기대값";
  if (s === "NEGATIVE_EXPECTANCY") return "기대값 부정적";
  if (s === "MIXED_EXPECTANCY") return "시간축별 기대값이 섞인 상태";
  return "expectancy profile 해석 부족";
}

function trendKo(v) {
  const s = String(v || "");
  if (s.includes("RECOVERY_PRESSURE_BUILDING")) return "회복 압력이 쌓이는 중";
  if (s.includes("PERSISTENT_STRONG_PRESSURE")) return "강한 압력이 유지되는 중";
  if (s.includes("IMPROVING")) return "장중 힘이 개선되는 중";
  if (s.includes("DETERIORATING")) return "장중 힘이 약해지는 중";
  if (s.includes("WEAK")) return "약한 압력";
  if (s.includes("STABLE")) return "큰 변화 없이 안정";
  return "아직 판단 근거 부족";
}

function groupKo(v) {
  if (v === "ACTION_CONFIRMING") return "강한 확인 후보";
  if (v === "ACTION_WATCH") return "관찰 후보";
  if (v === "ACTION_CAUTION") return "주의 후보";
  if (v === "ACTION_RISK_OFF") return "위험 회피 후보";
  return "중립";
}

function verdictFor(item) {
  const score = nval(item.score);
  const confirmed = nval(item.confirmedScore);
  const delta = liveDelta(item);
  const failure = nval(item.failurePressure);
  const group = String(item.decisionGroup || "");
  const profile = String(item.continuationProfile || "");

  if (
    score >= 88 &&
    confirmed >= 80 &&
    delta >= 0 &&
    failure <= 45 &&
    group !== "ACTION_RISK_OFF"
  ) {
    return {
      cls: "good",
      title: "매수 검토 가능",
      text: "원천 구조가 좋고 Live 보정도 우호적이다. 다만 실제 매수는 시장 지수와 손절 기준까지 같이 확인해야 한다."
    };
  }

  if (profile.includes("ALIVE") && score >= 70 && failure <= 55) {
    return {
      cls: "watch",
      title: "우선 관찰 후보",
      text: "continuation profile은 살아있지만 Live 보정 또는 실패 압력 확인이 더 필요하다."
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

  if (
    score >= 90 &&
    confirmed >= 85 &&
    delta >= 0 &&
    failure <= 45 &&
    group !== "ACTION_RISK_OFF"
  ) {
    return {
      cls: "signal-buy",
      text: "🟢 강한 매수 검토 시그널: 원천 구조와 Live 보정이 같이 맞는다."
    };
  }

  if (
    score >= 80 &&
    confirmed >= 80 &&
    failure <= 50 &&
    profile.includes("ALIVE")
  ) {
    return {
      cls: "signal-watch",
      text: "🟡 우선 감시 시그널: continuation은 살아있지만 장중 확인이 더 필요하다."
    };
  }

  if (group === "ACTION_RISK_OFF" || failure >= 55) {
    return {
      cls: "signal-risk",
      text: "🔴 보류 시그널: 실패 압력이나 장중 약화가 보여서 추격은 위험하다."
    };
  }

  return {
    cls: "signal-watch",
    text: "🟡 관찰 시그널: 아직 확실한 매수 확인은 부족하다."
  };
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

  if (confirmed >= 85) reasons.push("원천 구조 점수가 높다. 확정봉 기준 continuation 구조가 강하다.");
  else if (confirmed >= 70) reasons.push("원천 구조는 양호하지만 최상급은 아니다.");
  else reasons.push("원천 구조 점수가 강하지 않다.");

  if (delta > 3) reasons.push(`Live 보정이 +${delta.toFixed(2)}점으로 원천 구조를 더 강화하고 있다.`);
  else if (delta > 0) reasons.push(`Live 보정이 +${delta.toFixed(2)}점으로 약하게 우호적이다.`);
  else if (delta < -5) reasons.push(`Live 보정이 ${delta.toFixed(2)}점으로 크게 깎이고 있다. 장중 약화가 강하다.`);
  else if (delta < 0) reasons.push(`Live 보정이 ${delta.toFixed(2)}점으로 소폭 부정적이다.`);
  else reasons.push("Live 보정 영향은 거의 중립이다.");

  if (score >= 88) reasons.push("실시간 보정 점수가 높다. 오늘 집중 감시할 만하다.");
  else if (score >= 70) reasons.push("실시간 보정 점수는 양호하다.");
  else reasons.push("실시간 보정 점수는 아직 강한 매수 판단까지 부족하다.");

  if (move >= 2) reasons.push("현재 상승률이 강하다. 장중 수급 확인이 붙고 있다.");
  else if (move >= 0.5) reasons.push("현재 상승률은 약하지만 플러스 흐름이다.");
  else if (move > -0.5) reasons.push("현재 움직임은 거의 보합이다. 추가 확인이 필요하다.");
  else reasons.push("현재 움직임이 음수다. 장중 힘이 약할 수 있다.");

  if (failure >= 55) reasons.push("실패 압력이 높다. 추격 매수 위험이 크다.");
  else if (failure >= 45) reasons.push("실패 압력이 중간 이상이다. 매수 전 추가 확인이 필요하다.");
  else reasons.push("실패 압력이 낮은 편이다.");

  if (breakout >= 55) reasons.push("돌파 압력이 양호하다.");
  if (distribution >= 30) reasons.push("분산/매물 부담이 존재한다.");
  if (profile) reasons.push(`Continuation Profile: ${profileKo(profile)}`);

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
        왼쪽 표에서 종목을 누르면 원천 구조 점수, Live 보정 점수, 추세 지속 상태, 실패 위험을 한글로 풀어서 보여준다.
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
      이 패널은 매수 신호가 아니라 판단 근거 확인용이다. 점수가 높아도 원천 점수와 Live 보정 방향을 반드시 같이 봐야 한다.
    </div>

    <div class="signal-banner ${signal.cls}">
      ${signal.text}
    </div>

    <div class="metric-grid">
      <div class="metric">
        <div class="metric-label">실시간 보정 점수<br><span style="font-size:11px;color:#8ea0b8;">원천 구조 + Live 압력 반영</span></div>
        <div class="metric-value ${scoreClass(item.score)}">${num(item.score)}</div>
        <div style="margin-top:6px;font-size:12px;line-height:1.45;color:#8ea0b8;">
          원천 구조 점수: <span class="${scoreClass(item.confirmedScore)}" style="font-weight:900;">${num(item.confirmedScore)}</span><br>
          Live 보정: <span class="${deltaClass(item)}" style="font-weight:900;">${deltaText(item)}</span>
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">Survivability Score<br><span style="font-size:11px;color:#8ea0b8;">상태 생존 가능성 점수</span></div>
        <div class="metric-value ${scoreClass(item.survivabilityScore)}">${num(item.survivabilityScore)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">${esc(profileKo(item.continuationProfile))}</div>
      </div>

      <div class="metric">
        <div class="metric-label">현재 상승률<br><span style="font-size:11px;color:#8ea0b8;">↑ 높을수록 강한 수급</span></div>
        <div class="metric-value ${moveClass(item.move)}">${num(item.move)}%</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.move) >= 3 ? "강한 장중 상승" : nval(item.move) >= 1 ? "양호한 흐름" : nval(item.move) >= -0.5 ? "보합권" : "장중 약세"}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">실패 압력<br><span style="font-size:11px;color:#8ea0b8;">↓ 낮을수록 안정</span></div>
        <div class="metric-value ${failureClass(item.failurePressure)}">${num(item.failurePressure)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.failurePressure) <= 35 ? "추세 안정 구간" : nval(item.failurePressure) <= 45 ? "정상 흔들림 구간" : nval(item.failurePressure) <= 55 ? "실패 위험 증가" : "붕괴 위험 높음"}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">돌파 압력<br><span style="font-size:11px;color:#8ea0b8;">↑ 높을수록 강함</span></div>
        <div class="metric-value">${num(item.breakoutPressure)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.breakoutPressure) >= 70 ? "강한 돌파 압력" : nval(item.breakoutPressure) >= 55 ? "양호한 돌파" : nval(item.breakoutPressure) >= 40 ? "보통 수준" : "돌파 힘 부족"}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label">분산/매물 압력<br><span style="font-size:11px;color:#8ea0b8;">↓ 낮을수록 좋음</span></div>
        <div class="metric-value">${num(item.distributionPressure)}</div>
        <div style="margin-top:6px;font-size:12px;color:#8ea0b8;line-height:1.4;">
          ${nval(item.distributionPressure) <= 15 ? "매물 부담 낮음" : nval(item.distributionPressure) <= 30 ? "보통 수준" : nval(item.distributionPressure) <= 45 ? "매물 부담 증가" : "분산 위험 높음"}
        </div>
      </div>
    </div>

    <div class="explain-box">
      <div class="explain-title">상태 해석</div>
      <ul class="explain-list">
        <li>Live State: ${stateKo(item.liveMergedState)} <br><span class="neutral">${esc(item.liveMergedState)}</span></li>
        <li>Trajectory: ${trajectoryKo(item.trajectory)} <br><span class="neutral">${esc(item.trajectory)}</span></li>
        <li>Hierarchy: ${esc(item.hierarchy || "-")}</li>
        <li>Bias: ${esc(item.bias || "-")}</li>
        <li>Continuation Profile: ${profileKo(item.continuationProfile)} <br><span class="neutral">${esc(item.continuationProfile || "-")}</span></li>
        <li>Expectancy Profile: ${expectancyKo(item.expectancyProfile)} <br><span class="neutral">${esc(item.expectancyProfile || "-")}</span></li>
        <li>Risk Profile: ${riskKo(item.riskProfile)} <br><span class="neutral">${esc(item.riskProfile || "-")}</span></li>
        <li>Survivability: ${esc(item.survivabilityInterpretation || "-")}</li>
      </ul>
    </div>

    <div class="explain-box">
      <div class="explain-title">왜 이렇게 판단하는가</div>
      <ul class="explain-list">
        ${reasons.map(r => `<li>${esc(r)}</li>`).join("")}
      </ul>
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
        <div class="subline">
          원천 ${num(item.confirmedScore)} / <span class="${deltaClass(item)}">Live ${deltaText(item)}</span>
        </div>
      </td>
      <td>
        <div><span class="score ${scoreClass(item.survivabilityScore)}">${num(item.survivabilityScore)}</span></div>
        <div class="subline">${esc(item.continuationProfile || "-")}</div>
      </td>
      <td><span class="move ${moveClass(item.move)}">${num(item.move)}%</span></td>
      <td><span class="pill ${meta.cls}">${esc(item.liveMergedState)}</span></td>
      <td>
        <div>${esc(item.trajectory)}</div>
        <div class="profile-line">${esc(item.expectancyProfile || "-")} / ${esc(item.riskProfile || "-")}</div>
      </td>
      <td><span class="failure ${failureClass(item.failurePressure)}">${num(item.failurePressure)}</span></td>
    </tr>
  `).join("");

  if (!body) {
    body = `<tr><td colspan="7" class="empty">No symbols</td></tr>`;
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
              <th>Symbol</th>
              <th>Score / Live Δ</th>
              <th>Survivability</th>
              <th>Move</th>
              <th>Live State</th>
              <th>Trajectory / Profile</th>
              <th>Failure</th>
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
  SELECTED_SYMBOL = symbol;
  renderDetail(findSymbol(symbol));

  document.querySelectorAll("tr.selected").forEach(row => row.classList.remove("selected"));
  document.querySelectorAll(`tr[data-symbol="${CSS.escape(symbol)}"]`).forEach(row => row.classList.add("selected"));
}

function renderSections(data) {
  const board = data.board || {};

  document.getElementById("sections").innerHTML = GROUPS.map(group => {
    return renderTable(group, board[group] || []);
  }).join("");

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

    renderSummary(data);
    renderSections(data);

    if (!SELECTED_SYMBOL) {
      const board = data.board || {};
      const first =
        (board.ACTION_CONFIRMING || [])[0] ||
        (board.ACTION_WATCH || [])[0] ||
        (board.ACTION_CAUTION || [])[0] ||
        (board.ACTION_RISK_OFF || [])[0];

      if (first && first.symbol) {
        SELECTED_SYMBOL = first.symbol;
        renderDetail(first);
      }
    }

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
