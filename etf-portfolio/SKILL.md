---
name: etf-portfolio
description: >-
  The user's ETF holdings in one view: value, profit or loss, weights, how far each has fallen
  versus its own past falls, and a look-through of what they really own across all ETFs (e.g.
  Samsung Electronics is 28 % of the account). Use when the user shares holdings or a broker
  screenshot, or says "my ETFs", "내 계좌", "수익률", "평가손익", "am I diversified", "how bad is this drop".
argument-hint: "[add | buy | sell | cash | show]"
---

# etf-portfolio (Portfolio Health)

`${CLAUDE_SKILL_DIR}` is this skill's folder. Files are kept under `krx/` in the current project
(`krx/etf_portfolio.json`, `krx/etf_goal.json`, caches in `krx/state/`). Python 3.8+, standard
library only. On Windows, `python3` is often missing or opens the Microsoft Store: use `python`
instead, and set `PYTHONUTF8=1` so Korean text prints correctly. Every script takes `--json`
for the raw numbers and `--offline DIR` to read saved responses.

```bash
python3 "${CLAUDE_SKILL_DIR}/portfolio.py" add 293180 --qty 8 --avg 97162
python3 "${CLAUDE_SKILL_DIR}/portfolio.py" buy 396500 --qty 2 --price 24950
python3 "${CLAUDE_SKILL_DIR}/portfolio.py" sell 462010 --qty 27 --price 3705
python3 "${CLAUDE_SKILL_DIR}/portfolio.py" cash 500000
python3 "${CLAUDE_SKILL_DIR}/portfolio.py" show
```

The script's docstring (`--help`) explains every number it prints.

## Steps

1. If the user shares a broker screenshot, read the name, quantity (보유수량) and average price (평균가) of each line, confirm them with the user, then `add` each one.
2. Run `show`. Lead with the total and the 'Worth knowing' lines, then the look-through.
3. Explain drawdown lines plainly: how this fall compares with the ETF's own past falls and how long those took to recover. Never say when this one will end.
4. Point to /etf-plan for a goal and target mix, and /etf-history for how buying more would have played out.

## 한국어 요약

보유 ETF의 평가금액, 손익, 비중, 과거 하락폭 대비 현재 하락, 그리고 모든 ETF를 합쳐 실제로 어떤 종목·업종에 돈이 들어가 있는지(look-through)를 보여줍니다.

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
