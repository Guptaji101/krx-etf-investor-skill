---
name: etf-history
description: >-
  How an ETF or a mix of ETFs behaved in the past and how ways of buying would have turned out,
  with dividends reinvested: monthly buying (적립식), lump sum vs split buying (분할매수), every N-year
  holding period, and every fall over 10 % with its recovery. Use when the user asks "what if I
  bought monthly", "적립식 수익률", "분할매수 vs 일시금", "how long to recover", "과거 하락", "backtest".
argument-hint: "[dca | compare | rolling | drawdowns]"
---

# etf-history (History and DCA)

`${CLAUDE_SKILL_DIR}` is this skill's folder. Files are kept under `krx/` in the current project
(`krx/etf_portfolio.json`, `krx/etf_goal.json`, caches in `krx/state/`). Python 3.8+, standard
library only. On Windows, `python3` is often missing or opens the Microsoft Store: use `python`
instead, and set `PYTHONUTF8=1` so Korean text prints correctly. Every script takes `--json`
for the raw numbers and `--offline DIR` to read saved responses.

```bash
python3 "${CLAUDE_SKILL_DIR}/history.py" dca 293180 --monthly 100000 --years 5
python3 "${CLAUDE_SKILL_DIR}/history.py" dca 069500:60 360750:40 --monthly 300000 --years 5
python3 "${CLAUDE_SKILL_DIR}/history.py" compare 396500 --amount 1000000 --years 3 --split 6
python3 "${CLAUDE_SKILL_DIR}/history.py" rolling 069500 --years 5
python3 "${CLAUDE_SKILL_DIR}/history.py" drawdowns 293180
```

The script's docstring (`--help`) explains every number it prints.

## Steps

1. Pick the command that answers the question; default to --years 5 when none is given.
2. Report invested, value, gain, XIRR and the worst point; for compare, all three lines.
3. Always say which period it covers and that a different period can rank the methods differently.
4. Young ETFs have short histories: say how many years the result rests on.

## 한국어 요약

배당 재투자 기준으로 적립식, 일시금 vs 분할매수, 모든 N년 보유 구간, 10% 이상 하락과 회복 기간을 과거 데이터로 보여줍니다. 예측이 아닙니다.

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
