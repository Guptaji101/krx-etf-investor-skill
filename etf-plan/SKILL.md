---
name: etf-plan
description: >-
  Turns the user's own goal (target amount, years, monthly money, risk level, notes) and their own
  target ETF mix and rules into checks: the return the goal needs, how often the mix earned it in
  the past, its deepest fall versus their risk level, rule breaks, drift, and this month's buy list
  in whole shares. Use when the user says "make a plan", "투자 계획", "목표", "how should I split my
  money", "rebalance", "리밸런싱", "what do I buy this month", "이번 달 매수".
argument-hint: "[goal | mix | rules | show | next]"
---

# etf-plan (Goal Planner)

`${CLAUDE_SKILL_DIR}` is this skill's folder. Files are kept under `krx/` in the current project
(`krx/etf_portfolio.json`, `krx/etf_goal.json`, caches in `krx/state/`). Python 3.8+, standard
library only. On Windows, `python3` is often missing or opens the Microsoft Store: use `python`
instead, and set `PYTHONUTF8=1` so Korean text prints correctly. Every script takes `--json`
for the raw numbers and `--offline DIR` to read saved responses.

```bash
python3 "${CLAUDE_SKILL_DIR}/plan.py" goal --target 30000000 --years 5 --monthly 300000 --risk medium --note "house deposit"
python3 "${CLAUDE_SKILL_DIR}/plan.py" mix 069500=50 360750=30 411060=20
python3 "${CLAUDE_SKILL_DIR}/plan.py" rules --max-stock 20 --max-sector 40 --max-etf 60 --no-leverage
python3 "${CLAUDE_SKILL_DIR}/plan.py" show
python3 "${CLAUDE_SKILL_DIR}/plan.py" next --budget 300000
```

The script's docstring (`--help`) explains every number it prints.

## Steps

1. Ask for what the plan needs and does not have: target, years, monthly amount, how big a fall they could sit through (low 15 %, medium 30 %, high 50 %), and anything else that matters ("vision": what the money is for, when they need it). Save it with `goal`.
2. The mix is the user's choice. If they have none, help them think it through with /etf-profile search (broad index vs sector, domestic vs overseas, bonds or gold for steadiness) and /etf-history, then let them choose; do not choose for them. Save it with `mix`, and their limits with `rules`.
3. Run `show` and walk through sections 1 to 6. If the goal needs more return than the mix ever earned, or the mix fell further than their risk level, say so plainly: the fix is more time, more money, a smaller target, or a steadier mix.
4. `next` gives this month's whole-share buy list toward the target, new money only. The user places orders themselves.

## 한국어 요약

사용자가 정한 목표(금액, 기간, 월 투자금, 위험 수준, 메모)와 목표 비중·규칙을 바탕으로 필요 수익률, 과거 달성 빈도, 최대 하락 대비 위험 수준, 규칙 위반, 비중 이탈, 이번 달 매수 목록을 계산합니다. ETF를 대신 골라주지 않습니다.

## Language / 언어

Answer in the user's language. If they write in Korean, or `krx/config.json` has `"lang": "ko"`,
reply in Korean (the tools print mostly English; translate faithfully, numbers unchanged).
ETF and company names stay as printed (HANARO 200, 삼성전자).

## Rules for answering

- Facts, not verdicts. Report what the tools print. Do not tell the user to buy, sell or hold a
  specific ETF, and do not pick ETFs for them. When asked "should I buy?", lay out the numbers
  that bear on it (concentration, drawdown history, fees, goal math, their own rules) and say
  the decision is theirs. You are not a licensed financial advisor; say so once when asked for advice.
- Never predict prices or say a fall is "over" or a price is "the bottom".
- Past results are a sample, not a promise: say so once when showing any backtest or range.
- Data comes from Naver Finance, WiseReport and Yahoo public pages: unofficial, can lag a day,
  can change shape. If a tool reports a parsing problem, say so plainly; never fill in numbers.
- Tax lines are general Korean rules for residents. A foreign resident, ISA, pension account or
  IRP is taxed differently: suggest checking with the broker or the National Tax Service (국세청).
- Never ask for brokerage logins, account numbers or passwords. Nothing here places orders.
