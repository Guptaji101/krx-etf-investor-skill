#!/usr/bin/env python3
"""Valuation Context for etf-valuation: is an ETF's basket cheap or expensive by the usual
yardsticks, and where does its price sit against its own past. Standard library only. Read-only.

    python3 valuation.py 293180               # look-through PER / PBR, price context
    python3 valuation.py 293180 396500 --json

Two views, both descriptive:
  Look-through   the weighted PER (price / earnings), forward PER and PBR (price / book) of the
                 ETF's largest stock holdings, from Naver's stock pages, with how much of the fund
                 they cover. PER is combined the right way (as an earnings yield: sum of weight /
                 PER, inverted), and loss-making holdings are counted as zero earnings, not dropped.
                 Domestic-stock ETFs only: Naver has no per-stock values for overseas holdings.
  Price context  where today's price sits against its own history: % above or below its 200-day
                 and 5-year averages, how deep the current fall is versus past falls, and the
                 dividend yield now versus its 5-year average (a high yield after a fall can mean
                 cheap, or that payouts are about to drop).

There is no free, login-free history of index PER in Korea any more (KRX's data site now needs
an account), so the tool shows today's PER without its long-run range. A low PER can be a
bargain or a warning that earnings are about to fall: cyclical sectors like memory chips often
look cheapest at the top of their cycle. Not investment advice.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etf  # noqa: E402
import krx  # noqa: E402

TOP_N = 10


def look_through(code):
    a = etf.analysis(code)
    rows, covered = [], 0.0
    for t in a["top10"][:TOP_N]:
        if t["cash"] or not t["weight"] or not t["code"] or not krx.CODE_RE.match(t["code"]):
            continue
        v = etf.stock_valuation(t["code"])
        rows.append(dict(t, **v))
        covered += t["weight"]
    if not rows:
        return None

    def combine(key, invert):
        num, wsum = 0.0, 0.0
        for r in rows:
            x = r.get(key)
            if x is None:
                continue
            wsum += r["weight"]
            if invert:
                num += r["weight"] * (1.0 / x if x > 0 else 0.0)   # loss-making: zero earnings yield
            else:
                num += r["weight"] * x
        if not wsum:
            return None, 0.0
        if invert:
            return ((wsum / num) if num > 0 else None), wsum
        return num / wsum, wsum
    per, per_cov = combine("per", True)
    fper, fper_cov = combine("est_per", True)
    pbr, pbr_cov = combine("pbr", False)
    return {"rows": rows, "covered": covered, "per": per, "per_cov": per_cov, "est_per": fper,
            "est_per_cov": fper_cov, "pbr": pbr, "pbr_cov": pbr_cov}


def price_context(code):
    h = etf.history(code)
    adj, dates = h["adj"], h["dates"]
    now = adj[-1]
    ma = lambda n: sum(adj[-n:]) / n if len(adj) >= n else None  # noqa: E731
    m200, m5y = ma(200), ma(1250)
    peak = max(adj)
    dd_now = 100 * (now / peak - 1)
    # past falls' depths
    depths, pk, tr = [], adj[0], 0.0
    for c in adj:
        if c >= pk:
            if tr <= -10:
                depths.append(tr)
            pk, tr = c, 0.0
        else:
            tr = min(tr, 100 * (c / pk - 1))
    # dividend yield now vs 5-year average (raw price, trailing 12 months of payouts)
    close = dict(zip(dates, h["close"]))

    def ttm_yield(at):
        a0 = (datetime.date.fromisoformat(at) - datetime.timedelta(days=365)).isoformat()
        paid = sum(x for d, x in h["dividends"] if a0 < d <= at)
        p = close.get(at)
        return 100 * paid / p if p and paid else None
    yields = []
    for i in range(len(dates) - 1, max(0, len(dates) - 1250), -21):
        y = ttm_yield(dates[i])
        if y is not None:
            yields.append(y)
    return {"price": h["close"][-1], "date": dates[-1], "vs_200d": 100 * (now / m200 - 1) if m200 else None,
            "vs_5y": 100 * (now / m5y - 1) if m5y else None, "from_high": dd_now,
            "past_falls": sorted(depths), "yield_now": ttm_yield(dates[-1]),
            "yield_5y_avg": sum(yields) / len(yields) if yields else None, "years": len(dates) / 250.0}


def report(code, lst):
    e = etf.resolve(code, lst)
    a = etf.analysis(e["code"])
    L = ["%s %s: valuation context" % (e["code"], e["name"])]
    lt = look_through(e["code"]) if e["type"] in (1, 2) else None
    if lt:
        fmt = lambda x, cov: ("%.1fx" % x if x else "n/a") + " (covers %.0f%% of the fund)" % cov  # noqa: E731
        L.append("  Look-through, largest %d holdings:" % len(lt["rows"]))
        L.append("    PER (trailing)  %s" % fmt(lt["per"], lt["per_cov"]))
        L.append("    PER (forward)   %s" % fmt(lt["est_per"], lt["est_per_cov"]))
        L.append("    PBR             %s" % ("%.2fx (covers %.0f%%)" % (lt["pbr"], lt["pbr_cov"]) if lt["pbr"] else "n/a"))
        for r in lt["rows"][:5]:
            L.append("      %-14s %5.1f%%  PER %s  fwd %s  PBR %s" % (
                r["name"][:14], r["weight"], fx(r.get("per")), fx(r.get("est_per")), fx(r.get("pbr"))))
        if lt["per"] and lt["est_per"] and lt["est_per"] > lt["per"] * 1.2:
            L.append("    Forward PER is well above trailing PER: analysts expect earnings to fall.")
        elif lt["per"] and lt["est_per"] and lt["est_per"] < lt["per"] * 0.8:
            L.append("    Forward PER is well below trailing PER: analysts expect earnings to grow.")
    elif e["type"] in (1, 2):
        L.append("  Look-through valuation: not available (no stock values found for the holdings).")
    else:
        L.append("  Look-through valuation: not for %s ETFs (holdings are not KRX stocks)." % e["type_name"])
    pc = price_context(e["code"])
    L.append("  Price %s won on %s (%.1f years of history):" % (krx.px(pc["price"]), pc["date"], pc["years"]))
    if pc["vs_200d"] is not None:
        L.append("    %s vs its 200-day average" % etf.pct(pc["vs_200d"]))
    if pc["vs_5y"] is not None:
        L.append("    %s vs its 5-year average" % etf.pct(pc["vs_5y"]))
    falls = pc["past_falls"]
    line = "    %s from its highest price" % etf.pct(pc["from_high"])
    if falls and pc["from_high"] < -10:
        deeper = sum(1 for f in falls if f <= pc["from_high"])
        line += "; %d of %d past falls over 10%% went deeper (deepest %s)" % (deeper, len(falls), etf.pct(min(falls)))
    L.append(line)
    if pc["yield_now"] is not None:
        L.append("    Dividend yield %.2f%% now vs %.2f%% on average over 5 years" % (
            pc["yield_now"], pc["yield_5y_avg"] or 0))
    L.append("  No free history of index PER is available, so 'cheap' here means cheaper than its own recent "
             "price, not than its earnings history. Cyclical stocks can look cheapest at their peak.")
    return L, {"etf": e, "look_through": lt, "price": pc}


def fx(x):
    return "%.1f" % x if x is not None else "-"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valuation Context (etf-valuation).")
    ap.add_argument("etfs", nargs="+")
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    etf.OFFLINE = a.offline
    try:
        lst = etf.etf_list()
        docs = []
        for i, c in enumerate(a.etfs):
            lines, doc = report(c, lst)
            docs.append(doc)
            if not a.json:
                print(("\n" if i else "") + "\n".join(lines))
        if a.json:
            print(json.dumps(docs, indent=2, ensure_ascii=False, default=str))
        else:
            print("Not investment advice.")
        return 0
    except (etf.ETFError, krx.KRXError) as e:
        print("valuation.py: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
