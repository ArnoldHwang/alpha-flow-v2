# ALPHA-FLOW-V2

## DAILY RUNTIME GUIDE

---

# 1. 장마감 후 (하루 1번)

## 실행

```bash
python src/runtime/run_confirmed_pipeline.py
```

## 역할

```txt
raw scanner
→ timeframe states
→ hierarchy
→ trajectory
→ survivability
→ expectancy update
```

## 목적

확정봉 기반 전체 상태 업데이트

---

# 2. 장중 실시간 모니터링

## 실행

```bash
python src/runtime/run_live_runtime.py
```

## 기본 주기

```txt
3분 (180초)
```

## 역할

```txt
live quotes
→ live merge
→ decision board
→ live dashboard
```

## 브라우저

```txt
http://localhost:8080/live_decision_board.html
```

## 목적

실시간 continuation pressure 감시

---

# 3. 리서치 / expectancy 분석

## 실행

```bash
python src/runtime/run_research_pipeline.py
```

## 역할

```txt
trajectory expectancy
transition expectancy
survivability analysis
distribution analysis
```

## 목적

어떤 상태가
어떤 timeframe expectancy를 가지는지 연구

---

# 핵심 철학

## CONFIRMED

```txt
현재 구조
```

## LIVE

```txt
지금 살아나는가 / 무너지는가
```

## RESEARCH

```txt
실제로 얼마나 오래 살아남는가
```
