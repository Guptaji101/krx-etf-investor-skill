# KRX ETF Investor skill · 한국 ETF 장기투자 스킬

5 Claude skills for **long-term investing in Korean-listed ETFs** (KODEX, TIGER, HANARO, ACE,
RISE, SOL and the rest of the ~1,200 on KRX): see what is inside an ETF, what you really own
across all of them, how buying would have played out, whether prices look stretched, and
whether your own plan adds up.

국내 상장 ETF 약 1,200개를 대상으로 한 장기투자용 Claude 스킬 5개: 구성종목과 보수, 내 계좌의 실제 종목·업종
비중, 적립식·분할매수 백테스트, 밸류에이션과 가격 위치, 그리고 내가 세운 목표·비중·규칙 점검.

> **Facts, not verdicts.** These tools never tell you to buy, sell or hold, never pick ETFs for
> you, and never place orders. They lay out the numbers so the decision is yours.
> 투자 조언이 아닙니다. 매수·매도·보유 판단과 주문은 직접 하세요.

Companion to [krx-day-trader-skill](https://github.com/Guptaji101/krx-day-trader-skill)
(short-term, paper only). This pack is for holding.

## Install · 설치

In Claude Code:

```
/plugin marketplace add Guptaji101/krx-etf-investor-skill
/plugin install krx-etf-investor-skill@krx-etf-investor-skill
```

Python 3.8+, nothing to pip install. No API key. On Windows, Claude uses `python` (not `python3`).

## The five · 5개 스킬

| command | answers | 역할 |
| --- | --- | --- |
| `/etf-profile` | What's inside, fee, size, tax type, NAV gap, overlap between ETFs | ETF 구성·보수·과세·중복 |
| `/etf-portfolio` | Your value and P&L, falls vs history, look-through stock/sector exposure | 내 계좌 점검 |
| `/etf-history` | Monthly buying, lump sum vs split, N-year periods, past falls and recoveries | 적립식·분할매수 백테스트 |
| `/etf-valuation` | Look-through PER/PBR, price vs 200-day / 5-year averages, yield vs history | 밸류에이션·가격 위치 |
| `/etf-plan` | Your goal, mix and rules: return needed, track record, risk fit, drift, this month's buys | 목표·비중·규칙 점검 |

Ask in plain words: "내 ETF 계좌 점검해줘" with a broker screenshot, "HANARO 200이랑 반도체TOP10
겹치는 거 얼마나 돼?", "KODEX 200을 5년간 매달 10만원 샀으면?", "5년에 3천만원 목표로 계획 세워줘".

## Example · 예시

A real account (Nov 2026): HANARO 200, TIGER 반도체TOP10 and TIGER 2차전지소재Fn, three
different-looking ETFs. `/etf-portfolio show`:

```
Looking through the ETFs, your money is in (share of the whole account):
  삼성전자                      28.3%  <- over 20%
  SK하이닉스                    22.2%  <- over 20%
  SK스퀘어                      7.9%
  Sectors: IT 58.7%, industrials 20.9%, financials 5.6% ...
Worth knowing:
  - 삼성전자 is 28.3% of everything you own, through 2 ETF(s).
  - one sector (IT) is 58.7% of the account.
```

and `/etf-profile overlap 293180 396500`: weighted overlap 55 %. Two of the three ETFs were
largely the same bet on two memory-chip companies.

## Data · 데이터

Public pages, no login: Naver Finance's ETF list and ETF analysis, WiseReport's ETF holdings
(구성종목), Naver stock pages (PER/PBR), Yahoo Finance daily prices with dividends. They are
unofficial and can change or lag a day; every parser fails with a plain message rather than a
wrong number. KRX's own data site now requires a login, so there is no free history of index
PER: valuation compares price with its own past, not with its earnings history.

## Tests · 테스트

```bash
python3 -m unittest discover -s tests -v
```

Offline, on fixtures trimmed from real Naver responses. Price histories in the fixtures are
generated (same dates, made-up prices) so the repo does not republish market data.

## Fine print · 유의사항

- **Not financial advice.** Past returns are a sample of one history, not a forecast.
- **Tax lines are general rules for Korean residents** (domestic equity ETFs: gains tax-free,
  distributions 15.4 %; other ETFs: 15.4 % on gains and distributions). ISA, pension accounts,
  IRP and non-residents differ. Check with your broker or 국세청.
- **Leveraged and inverse ETFs** reset daily and drift over time; the tools flag them.
- **Small ETFs** (under ₩50억) can be delisted; the tools flag them.

## License

MIT. See LICENSE.
