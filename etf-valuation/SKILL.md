---
name: etf-valuation
description: >-
  Whether an ETF looks cheap or expensive by the usual yardsticks: look-through PER, forward PER
  and PBR of its largest holdings, and where its price sits versus its 200-day and 5-year averages,
  its past falls and its usual dividend yield. Use when the user asks "is it cheap now", "지금 싼가요",
  "PER", "valuation", "저평가", "is this a good entry".
argument-hint: "[CODE...]"
---

# etf-valuation (Valuation Context)

`${CLAUDE_SKILL_DIR}` is this skill's folder. Files are kept under `krx/` in the current project
(`krx/etf_portfolio.json`, `krx/etf_goal.json`, caches in `krx/state/`). Python 3.8+, standard
library only. On Windows, `python3` is often missing or opens the Microsoft Store: use `python`
instead, and set `PYTHONUTF8=1` so Korean text prints correctly. Every script takes `--json`
for the raw numbers and `--offline DIR` to read saved responses.

```bash
python3 "${CLAUDE_SKILL_DIR}/valuation.py" 293180
python3 "${CLAUDE_SKILL_DIR}/valuation.py" 396500 069500 --json
```

The script's docstring (`--help`) explains every number it prints.

## Steps

1. Run it. Report the look-through PER/PBR with their coverage, then the price context lines.
2. Explain the trap for cyclical sectors: memory-chip and battery earnings swing, so PER is often lowest at the earnings peak. Forward PER above trailing PER means analysts expect earnings to fall.
3. Never call a price 'the bottom' or 'a good entry'. Say what the numbers show and what they cannot.

## 한국어 요약

상위 보유종목 기준 PER·선행 PER·PBR과, 200일·5년 평균 대비 가격, 과거 하락 대비 현재 위치, 배당수익률을 보여줍니다. 경기민감 업종은 실적 정점에서 PER이 가장 낮아 보일 수 있습니다.

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
