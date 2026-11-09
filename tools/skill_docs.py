#!/usr/bin/env python3
"""Writes the five SKILL.md files from one place. Edit here, then: python3 tools/skill_docs.py"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMMON = """`${CLAUDE_SKILL_DIR}` is this skill's folder. Files are kept under `krx/` in the current project
(`krx/etf_portfolio.json`, `krx/etf_goal.json`, caches in `krx/state/`). Python 3.8+, standard
library only. On Windows, `python3` is often missing or opens the Microsoft Store: use `python`
instead, and set `PYTHONUTF8=1` so Korean text prints correctly. Every script takes `--json`
for the raw numbers and `--offline DIR` to read saved responses."""

LANG = """## Language / 언어

Answer in the user's language. If they write in Korean, or `krx/config.json` has `"lang": "ko"`,
reply in Korean (the tools print mostly English; translate faithfully, numbers unchanged).
ETF and company names stay as printed (HANARO 200, 삼성전자)."""

RULES = """## Rules for answering

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
- Never ask for brokerage logins, account numbers or passwords. Nothing here places orders."""

SKILLS = [
    {
        "dir": "etf-profile", "script": "profile.py", "title": "ETF Profile",
        "desc": ("What is inside a Korean-listed ETF (KODEX, TIGER, HANARO, ACE, RISE...): fee (총보수), size, tracking "
                 "error, NAV gap (괴리율), tax type, sectors, countries, top holdings, dividends, fund flows, and how much "
                 "several ETFs overlap. Use when the user asks \"what's in this ETF\", \"ETF 구성종목\", \"수수료\", "
                 "\"compare these ETFs\", \"do my ETFs overlap\", \"find an S&P500 ETF\", \"ETF 검색\"."),
        "hint": "[show CODE... | search WORDS | overlap CODE CODE...]",
        "cmds": ['python3 "${CLAUDE_SKILL_DIR}/profile.py" show 293180 396500',
                 'python3 "${CLAUDE_SKILL_DIR}/profile.py" search 미국 S&P500',
                 'python3 "${CLAUDE_SKILL_DIR}/profile.py" search 채권 --type 6',
                 'python3 "${CLAUDE_SKILL_DIR}/profile.py" overlap 293180 396500 462010'],
        "steps": ["Resolve the ETF by code or exact name; if several match, show the list and ask which.",
                  "Report fee, size, tax type and the 'Careful' lines first; then sectors and top holdings.",
                  "For overlap, lead with the weighted overlap and the shared names. Over 40 % means the two "
                  "are largely the same bet.",
                  "For search, show the biggest funds first and point out fee differences between near-identical ones."],
        "ko": "ETF의 총보수, 규모, 추적오차, 괴리율, 과세 유형, 업종·국가 비중, 상위 구성종목, 분배금, 자금 유출입과 "
              "여러 ETF의 중복 정도를 보여줍니다.",
    },
    {
        "dir": "etf-portfolio", "script": "portfolio.py", "title": "Portfolio Health",
        "desc": ("The user's ETF holdings in one view: value, profit or loss, weights, how far each has fallen versus its "
                 "own past falls, and a look-through of what they really own across all ETFs (e.g. Samsung Electronics "
                 "is 28 % of the account). Use when the user shares holdings or a broker screenshot, or says \"my ETFs\", "
                 "\"내 계좌\", \"수익률\", \"평가손익\", \"am I diversified\", \"how bad is this drop\"."),
        "hint": "[add | buy | sell | cash | show]",
        "cmds": ['python3 "${CLAUDE_SKILL_DIR}/portfolio.py" add 293180 --qty 8 --avg 97162',
                 'python3 "${CLAUDE_SKILL_DIR}/portfolio.py" buy 396500 --qty 2 --price 24950',
                 'python3 "${CLAUDE_SKILL_DIR}/portfolio.py" sell 462010 --qty 27 --price 3705',
                 'python3 "${CLAUDE_SKILL_DIR}/portfolio.py" cash 500000',
                 'python3 "${CLAUDE_SKILL_DIR}/portfolio.py" show'],
        "steps": ["If the user shares a broker screenshot, read the name, quantity (보유수량) and average price (평균가) "
                  "of each line, confirm them with the user, then `add` each one.",
                  "Run `show`. Lead with the total and the 'Worth knowing' lines, then the look-through.",
                  "Explain drawdown lines plainly: how this fall compares with the ETF's own past falls and how long "
                  "those took to recover. Never say when this one will end.",
                  "Point to /etf-plan for a goal and target mix, and /etf-history for how buying more would have played out."],
        "ko": "보유 ETF의 평가금액, 손익, 비중, 과거 하락폭 대비 현재 하락, 그리고 모든 ETF를 합쳐 실제로 어떤 종목·업종에 "
              "돈이 들어가 있는지(look-through)를 보여줍니다.",
    },
    {
        "dir": "etf-history", "script": "history.py", "title": "History and DCA",
        "desc": ("How an ETF or a mix of ETFs behaved in the past and how ways of buying would have turned out, with "
                 "dividends reinvested: monthly buying (적립식), lump sum vs split buying (분할매수), every N-year holding "
                 "period, and every fall over 10 % with its recovery. Use when the user asks \"what if I bought monthly\", "
                 "\"적립식 수익률\", \"분할매수 vs 일시금\", \"how long to recover\", \"과거 하락\", \"backtest\"."),
        "hint": "[dca | compare | rolling | drawdowns]",
        "cmds": ['python3 "${CLAUDE_SKILL_DIR}/history.py" dca 293180 --monthly 100000 --years 5',
                 'python3 "${CLAUDE_SKILL_DIR}/history.py" dca 069500:60 360750:40 --monthly 300000 --years 5',
                 'python3 "${CLAUDE_SKILL_DIR}/history.py" compare 396500 --amount 1000000 --years 3 --split 6',
                 'python3 "${CLAUDE_SKILL_DIR}/history.py" rolling 069500 --years 5',
                 'python3 "${CLAUDE_SKILL_DIR}/history.py" drawdowns 293180'],
        "steps": ["Pick the command that answers the question; default to --years 5 when none is given.",
                  "Report invested, value, gain, XIRR and the worst point; for compare, all three lines.",
                  "Always say which period it covers and that a different period can rank the methods differently.",
                  "Young ETFs have short histories: say how many years the result rests on."],
        "ko": "배당 재투자 기준으로 적립식, 일시금 vs 분할매수, 모든 N년 보유 구간, 10% 이상 하락과 회복 기간을 과거 데이터로 "
              "보여줍니다. 예측이 아닙니다.",
    },
    {
        "dir": "etf-valuation", "script": "valuation.py", "title": "Valuation Context",
        "desc": ("Whether an ETF looks cheap or expensive by the usual yardsticks: look-through PER, forward PER and PBR of "
                 "its largest holdings, and where its price sits versus its 200-day and 5-year averages, its past falls and "
                 "its usual dividend yield. Use when the user asks \"is it cheap now\", \"지금 싼가요\", \"PER\", "
                 "\"valuation\", \"저평가\", \"is this a good entry\"."),
        "hint": "[CODE...]",
        "cmds": ['python3 "${CLAUDE_SKILL_DIR}/valuation.py" 293180',
                 'python3 "${CLAUDE_SKILL_DIR}/valuation.py" 396500 069500 --json'],
        "steps": ["Run it. Report the look-through PER/PBR with their coverage, then the price context lines.",
                  "Explain the trap for cyclical sectors: memory-chip and battery earnings swing, so PER is often lowest "
                  "at the earnings peak. Forward PER above trailing PER means analysts expect earnings to fall.",
                  "Never call a price 'the bottom' or 'a good entry'. Say what the numbers show and what they cannot."],
        "ko": "상위 보유종목 기준 PER·선행 PER·PBR과, 200일·5년 평균 대비 가격, 과거 하락 대비 현재 위치, 배당수익률을 "
              "보여줍니다. 경기민감 업종은 실적 정점에서 PER이 가장 낮아 보일 수 있습니다.",
    },
    {
        "dir": "etf-plan", "script": "plan.py", "title": "Goal Planner",
        "desc": ("Turns the user's own goal (target amount, years, monthly money, risk level, notes) and their own target "
                 "ETF mix and rules into checks: the return the goal needs, how often the mix earned it in the past, its "
                 "deepest fall versus their risk level, rule breaks, drift, and this month's buy list in whole shares. "
                 "Use when the user says \"make a plan\", \"투자 계획\", \"목표\", \"how should I split my money\", "
                 "\"rebalance\", \"리밸런싱\", \"what do I buy this month\", \"이번 달 매수\"."),
        "hint": "[goal | mix | rules | show | next]",
        "cmds": ['python3 "${CLAUDE_SKILL_DIR}/plan.py" goal --target 30000000 --years 5 --monthly 300000 --risk medium '
                 '--note "house deposit"',
                 'python3 "${CLAUDE_SKILL_DIR}/plan.py" mix 069500=50 360750=30 411060=20',
                 'python3 "${CLAUDE_SKILL_DIR}/plan.py" rules --max-stock 20 --max-sector 40 --max-etf 60 --no-leverage',
                 'python3 "${CLAUDE_SKILL_DIR}/plan.py" show',
                 'python3 "${CLAUDE_SKILL_DIR}/plan.py" next --budget 300000'],
        "steps": ["Ask for what the plan needs and does not have: target, years, monthly amount, how big a fall they could "
                  "sit through (low 15 %, medium 30 %, high 50 %), and anything else that matters (\"vision\": what the "
                  "money is for, when they need it). Save it with `goal`.",
                  "The mix is the user's choice. If they have none, help them think it through with /etf-profile search "
                  "(broad index vs sector, domestic vs overseas, bonds or gold for steadiness) and /etf-history, then let "
                  "them choose; do not choose for them. Save it with `mix`, and their limits with `rules`.",
                  "Run `show` and walk through sections 1 to 6. If the goal needs more return than the mix ever earned, "
                  "or the mix fell further than their risk level, say so plainly: the fix is more time, more money, a "
                  "smaller target, or a steadier mix.",
                  "`next` gives this month's whole-share buy list toward the target, new money only. The user places "
                  "orders themselves."],
        "ko": "사용자가 정한 목표(금액, 기간, 월 투자금, 위험 수준, 메모)와 목표 비중·규칙을 바탕으로 필요 수익률, 과거 달성 "
              "빈도, 최대 하락 대비 위험 수준, 규칙 위반, 비중 이탈, 이번 달 매수 목록을 계산합니다. ETF를 대신 골라주지 않습니다.",
    },
]


def render(s):
    out = ["---", "name: %s" % s["dir"], "description: >-"]
    line = "  "
    for w in s["desc"].split():
        if len(line) + len(w) + 1 > 100:
            out.append(line.rstrip())
            line = "  "
        line += w + " "
    out += [line.rstrip(), 'argument-hint: "%s"' % s["hint"], "---", "",
            "# %s (%s)" % (s["dir"], s["title"]), "", COMMON, "", "```bash"] + s["cmds"] + ["```", "",
            "The script's docstring (`--help`) explains every number it prints.", "", "## Steps", ""]
    out += ["%d. %s" % (i, t) for i, t in enumerate(s["steps"], 1)]
    out += ["", "## 한국어 요약", "", s["ko"], "", LANG, "", RULES, ""]
    return "\n".join(out)


def main():
    for s in SKILLS:
        with open(os.path.join(ROOT, s["dir"], "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write(render(s))
        print("wrote %s/SKILL.md" % s["dir"])


if __name__ == "__main__":
    main()
