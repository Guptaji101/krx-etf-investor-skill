#!/usr/bin/env python3
"""Portfolio Health for etf-portfolio: your ETF holdings, what they are worth, and what you
really own once every ETF is looked through to its stocks and sectors. Standard library only.
Read-only toward your broker: it only reads and writes krx/etf_portfolio.json.

    python3 portfolio.py add 293180 --qty 8 --avg 97162       # record a holding (avg = 평균단가)
    python3 portfolio.py add "TIGER 반도체TOP10" --qty 10 --avg 34592
    python3 portfolio.py buy 293180 --qty 2 --price 78970      # later buy: updates qty and average
    python3 portfolio.py sell 293180 --qty 2 --price 81000     # records a sale and its realized P&L
    python3 portfolio.py cash 500000                           # cash waiting in the account
    python3 portfolio.py show                                  # value, P&L, look-through, drawdowns
    python3 portfolio.py remove 462010
    python3 portfolio.py show --json

`show` reports:
  per ETF      value, profit or loss (won and %), weight in the account, the fall from its
               52-week high, and how this fall ranks among its own past drawdowns
  look-through your money in each stock and sector across all ETFs together: "Samsung
               Electronics is 31 % of everything you own" even if no single ETF says so
  warnings     one stock over 20 %, one sector over 40 %, leveraged ETFs held long-term,
               small or high-fee funds, ETFs that are really the same bet
  tax          which holdings are domestic equity ETFs (gains tax-free) and which are not

Prices are the latest from Naver's ETF list (delayed). Not investment advice.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etf  # noqa: E402
import krx  # noqa: E402

STOCK_LIMIT = 20.0
SECTOR_LIMIT = 40.0


def drawdown_stats(code):
    """Current fall from the all-time (data) high and the 52-week high, and past max drawdowns."""
    h = etf.history(code)
    closes, dates = h["adj"], h["dates"]
    peak, peak_d, episodes, cur = closes[0], dates[0], [], None
    trough = None
    for d, c in zip(dates, closes):
        if c >= peak:
            if trough and trough[1] < -10:
                episodes.append({"peak": peak_d, "trough": trough[0], "depth": trough[1], "recovered": d})
            peak, peak_d, trough = c, d, None
        else:
            dd = 100 * (c / peak - 1)
            if trough is None or dd < trough[1]:
                trough = (d, dd)
    if trough:
        cur = {"peak": peak_d, "trough": trough[0], "depth": trough[1], "recovered": None,
               "now": 100 * (closes[-1] / peak - 1)}
    y = [c for d, c in zip(dates, closes) if d >= krx_shift(dates[-1], -365)]
    off52 = 100 * (closes[-1] / max(y) - 1) if y else None
    past = sorted(e["depth"] for e in episodes)
    rank = None
    if cur:
        rank = 1 + sum(1 for x in past if x < cur["depth"])
    return {"current": cur, "off_52w": off52, "past": episodes, "rank": rank, "since": dates[0]}


def krx_shift(d, days):
    import datetime
    return (datetime.date.fromisoformat(d) + datetime.timedelta(days=days)).isoformat()


def evaluate(pf, lst):
    by = {e["code"]: e for e in lst}
    rows, total, cost = [], float(pf.get("cash") or 0), 0.0
    for p in pf["positions"]:
        e = by.get(p["code"])
        if not e:
            rows.append(dict(p, missing=True))
            continue
        val = e["price"] * p["qty"]
        c = p["avg"] * p["qty"]
        rows.append(dict(p, name=e["name"], price=e["price"], value=val, cost=c, pnl=val - c,
                         pnl_pct=100 * (val / c - 1) if c else None, type=e["type"], aum_eok=e["aum_eok"]))
        total += val
        cost += c
    for r in rows:
        if not r.get("missing"):
            r["weight"] = 100 * r["value"] / total if total else 0
    return rows, total, cost


def look_through(rows, total):
    """{stock: % of the whole account}, {sector: %}, {country: %}, unknown share."""
    stocks, sectors, countries, unknown = {}, {}, {}, 0.0
    for r in rows:
        if r.get("missing") or not total:
            continue
        w = r["value"] / total              # this ETF's share of the account, 0..1
        b, cov = etf.basket(r["code"])         # holding weights in %, so w * x is % of the account
        a = etf.analysis(r["code"])
        for n, x in b.items():
            stocks[n] = stocks.get(n, 0) + w * x
        unknown += w * max(0.0, 100 - cov)
        for s, x in a["sectors"]:
            sectors[s] = sectors.get(s, 0) + w * x
        for c, x in a["countries"]:
            countries[c] = countries.get(c, 0) + w * x
    return stocks, sectors, countries, unknown


def report(pf, lst, lang="en"):
    rows, total, cost = evaluate(pf, lst)
    if not rows:
        return ["No ETFs recorded yet. Add them: portfolio.py add <code> --qty N --avg PRICE"], {}
    L = ["Your ETF account (prices delayed, from Naver)"]
    L.append("  %-6s %-24s %6s %9s %9s %12s %12s %8s %6s" % ("code", "name", "qty", "avg", "now", "value", "P&L",
                                                            "P&L %", "share"))
    for r in rows:
        if r.get("missing"):
            L.append("  %-6s (not found in the ETF list: delisted or a typo?)" % r["code"])
            continue
        L.append("  %-6s %-24s %6s %9s %9s %12s %12s %8s %5.1f%%" % (
            r["code"], r["name"][:24], "{:,}".format(int(r["qty"])), krx.px(r["avg"]), krx.px(r["price"]),
            krx.won(r["value"]), krx.won(r["pnl"], True), etf.pct(r["pnl_pct"]), r["weight"]))
    pnl = total - float(pf.get("cash") or 0) - cost
    L.append("  Total %s (cash %s). Invested %s, %s %s (%s)." % (
        krx.won(total), krx.won(pf.get("cash") or 0), krx.won(cost), "up" if pnl >= 0 else "down",
        krx.won(abs(pnl)), etf.pct(100 * pnl / cost if cost else None)))
    L.append("")
    L.append("How far each has fallen, and how that compares with its own history:")
    dd = {}
    for r in rows:
        if r.get("missing"):
            continue
        try:
            s = dd[r["code"]] = drawdown_stats(r["code"])
        except etf.ETFError as e:
            L.append("  %s: no price history (%s)" % (r["code"], e))
            continue
        cur = s["current"]
        line = "  %-6s %s from its 52-week high" % (r["code"], etf.pct(s["off_52w"]))
        if cur and cur["now"] < -5:
            n = len(s["past"]) + 1
            where = ("its only" if n == 1 else "the deepest") if s["rank"] == 1 else "the %s deepest" % ordinal(s["rank"])
            line += "; %s from its high of %s, %s %s over 10%% since %s" % (
                etf.pct(cur["now"]), cur["peak"], where, "fall" if n == 1 else "of %d falls" % n, s["since"][:4])
            if s["past"]:
                worst = min(s["past"], key=lambda e: e["depth"])
                line += " (worst: %s, %s to %s, recovered %s)" % (etf.pct(worst["depth"]), worst["peak"],
                                                                   worst["trough"], worst["recovered"])
        L.append(line + ".")
    stocks, sectors, countries, unknown = look_through(rows, total)
    L.append("")
    L.append("Looking through the ETFs, your money is in (share of the whole account):")
    for n, w in sorted(stocks.items(), key=lambda x: -x[1])[:10]:
        L.append("  %-24s %5.1f%%%s" % (n[:24], w, "  <- over %d%%" % STOCK_LIMIT if w > STOCK_LIMIT else ""))
    if unknown > 1:
        L.append("  (%.1f%% of the account is in holdings whose weights are not published)" % unknown)
    L.append("  Sectors: " + ", ".join("%s %.1f%%" % (etf.sector_name(s, lang), w)
                                       for s, w in sorted(sectors.items(), key=lambda x: -x[1])[:6]))
    ctry = sorted(countries.items(), key=lambda x: -x[1])
    if ctry:
        L.append("  Countries: " + ", ".join("%s %.1f%%" % (c, w) for c, w in ctry[:5]))
    warns = []
    for n, w in stocks.items():
        if w > STOCK_LIMIT:
            warns.append("%s is %.1f%% of everything you own, through %d ETF(s)" % (
                n, w, sum(1 for r in rows if not r.get("missing") and n in etf.basket(r["code"])[0])))
    for s, w in sectors.items():
        if w > SECTOR_LIMIT:
            warns.append("one sector (%s) is %.1f%% of the account" % (etf.sector_name(s, lang), w))
    for r in rows:
        if r.get("missing"):
            continue
        if etf.is_leveraged(r["name"]):
            warns.append("%s is leveraged / inverse: daily reset makes it drift; not built for holding" % r["name"])
        if (r["aum_eok"] or 0) < 50:
            warns.append("%s is a small fund (%s): delisting risk" % (r["name"], etf.eok((r["aum_eok"] or 0) * 1e8)))
    if ctry and ctry[0][0] == "KR" and ctry[0][1] > 90:
        warns.append("%.0f%% of the account is in Korean stocks: one country's market and currency" % ctry[0][1])
    if warns:
        L.append("")
        L.append("Worth knowing:")
        L += ["  - " + w + "." for w in warns]
    taxes = {}
    for r in rows:
        if not r.get("missing"):
            taxes.setdefault(etf.analysis(r["code"]).get("tax_code"), []).append(r["code"])
    L.append("")
    for code, codes in taxes.items():
        t = etf.TAX.get(code)
        L.append("Tax, %s: %s." % (", ".join(codes), (t[1] if lang == "ko" else t[0]) if t else "check with your broker"))
    L.append("Not investment advice. Past drawdowns say how deep and long falls have been, not what comes next.")
    return L, {"positions": rows, "total": total, "cost": cost, "look_through": {"stocks": stocks, "sectors": sectors,
                                                                                    "countries": countries},
               "drawdowns": dd, "warnings": warns}


def ordinal(n):
    if n is None:
        return "-"
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def find(pf, code):
    for p in pf["positions"]:
        if p["code"] == code:
            return p
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Portfolio Health (etf-portfolio).")
    ap.add_argument("--file", default=etf.PORTFOLIO)
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--lang", choices=["en", "ko"])
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("add", "buy", "sell"):
        p = sub.add_parser(name)
        p.add_argument("etf")
        p.add_argument("--qty", type=float, required=True)
        p.add_argument("--avg" if name == "add" else "--price", type=float, required=True)
    p = sub.add_parser("remove")
    p.add_argument("etf")
    p = sub.add_parser("cash")
    p.add_argument("amount", type=float)
    sub.add_parser("show")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    etf.OFFLINE = a.offline
    try:
        lang = krx.lang_of(a.lang, krx.load_config())
        pf = etf.load_portfolio(a.file)
        lst = etf.etf_list()
        if a.cmd in ("add", "buy", "sell", "remove"):
            e = etf.resolve(a.etf, lst)
            p = find(pf, e["code"])
            if a.cmd == "add":
                if a.qty <= 0 or a.avg <= 0:
                    raise etf.ETFError("--qty and --avg must be above 0")
                if p:
                    p.update(qty=a.qty, avg=a.avg)
                else:
                    pf["positions"].append({"code": e["code"], "name": e["name"], "qty": a.qty, "avg": a.avg})
                print("Recorded %s %s: %s shares at an average of %s won." % (e["code"], e["name"], krx.px(a.qty),
                                                                             krx.px(a.avg)))
            elif a.cmd == "buy":
                if p:
                    q = p["qty"] + a.qty
                    p["avg"] = (p["avg"] * p["qty"] + a.price * a.qty) / q
                    p["qty"] = q
                else:
                    p = {"code": e["code"], "name": e["name"], "qty": a.qty, "avg": a.price}
                    pf["positions"].append(p)
                print("Bought %s %s at %s: now %s shares, average %s won." % (krx.px(a.qty), e["name"], krx.px(a.price),
                                                                             krx.px(p["qty"]), krx.px(p["avg"])))
            elif a.cmd == "sell":
                if not p or a.qty > p["qty"]:
                    raise etf.ETFError("you hold %s shares of %s" % (krx.px(p["qty"] if p else 0), e["name"]))
                gain = (a.price - p["avg"]) * a.qty
                pf.setdefault("realized", []).append({"code": e["code"], "qty": a.qty, "price": a.price,
                                                      "avg": p["avg"], "gain": gain,
                                                      "date": etf.today_kst().isoformat()})
                p["qty"] -= a.qty
                if p["qty"] <= 0:
                    pf["positions"].remove(p)
                print("Sold %s %s at %s: realized %s." % (krx.px(a.qty), e["name"], krx.px(a.price), krx.won(gain, True)))
            else:
                if not p:
                    raise etf.ETFError("%s is not in your portfolio" % e["name"])
                pf["positions"].remove(p)
                print("Removed %s." % e["name"])
            etf.save_portfolio(pf, a.file)
            return 0
        if a.cmd == "cash":
            pf["cash"] = a.amount
            etf.save_portfolio(pf, a.file)
            print("Cash set to %s." % krx.won(a.amount))
            return 0
        lines, doc = report(pf, lst, lang)
        if a.json:
            print(json.dumps(doc, indent=2, ensure_ascii=False, default=str))
        else:
            print("\n".join(lines))
        return 0
    except (etf.ETFError, krx.KRXError) as e:
        print("portfolio.py: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
