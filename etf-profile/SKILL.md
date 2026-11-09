---
name: etf-profile
description: >-
  What is inside a Korean-listed ETF (KODEX, TIGER, HANARO, ACE, RISE...): fee (총보수), size,
  tracking error, NAV gap (괴리율), tax type, sectors, countries, top holdings, dividends, fund flows,
  and how much several ETFs overlap. Use when the user asks "what's in this ETF", "ETF 구성종목",
  "수수료", "compare these ETFs", "do my ETFs overlap", "find an S&P500 ETF", "ETF 검색".
argument-hint: "[show CODE... | search WORDS | overlap CODE CODE...]"
---

# etf-profile (ETF Profile)

`${CLAUDE_SKILL_DIR}` is this skill's folder. Files are kept under `krx/` in the current project
(`krx/etf_portfolio.json`, `krx/etf_goal.json`, caches in `krx/state/`). Python 3.8+, standard
library only. On Windows, `python3` is often missing or opens the Microsoft Store: use `python`
instead, and set `PYTHONUTF8=1` so Korean text prints correctly. Every script takes `--json`
for the raw numbers and `--offline DIR` to read saved responses.

```bash
python3 "${CLAUDE_SKILL_DIR}/profile.py" show 293180 396500
python3 "${CLAUDE_SKILL_DIR}/profile.py" search 미국 S&P500
python3 "${CLAUDE_SKILL_DIR}/profile.py" search 채권 --type 6
python3 "${CLAUDE_SKILL_DIR}/profile.py" overlap 293180 396500 462010
```

The script's docstring (`--help`) explains every number it prints.

## Steps

1. Resolve the ETF by code or exact name; if several match, show the list and ask which.
2. Report fee, size, tax type and the 'Careful' lines first; then sectors and top holdings.
3. For overlap, lead with the weighted overlap and the shared names. Over 40 % means the two are largely the same bet.
4. For search, show the biggest funds first and point out fee differences between near-identical ones.

## 한국어 요약

ETF의 총보수, 규모, 추적오차, 괴리율, 과세 유형, 업종·국가 비중, 상위 구성종목, 분배금, 자금 유출입과 여러 ETF의 중복 정도를 보여줍니다.

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
