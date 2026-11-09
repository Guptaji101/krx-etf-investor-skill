#!/usr/bin/env python3
"""ETF Profile for etf-profile: what is inside a KRX-listed ETF, what it costs, how it is
taxed, and how much several ETFs overlap. Standard library only. Read-only.

    python3 profile.py show 293180                  # one ETF: fee, size, tax, sectors, top 10
    python3 profile.py show "TIGER 반도체TOP10" 462010
    python3 profile.py search 미국 S&P500            # find ETFs by name, biggest first
    python3 profile.py search 반도체 --type 2
    python3 profile.py overlap 293180 396500        # shared holdings, weighted overlap
    python3 profile.py show 293180 --json

What `show` reports, and why a long-term holder cares:
  fee (총보수)         paid every year from the fund; 0.5 %/yr is ~5 % over 10 years
  size (순자산)         tiny ETFs (under ₩50억) can be delisted; you get cash back, at a bad time
  tracking error       how loosely it follows its index (annual, %)
  NAV deviation (괴리율) price above (+) or below (-) the value of what it holds today
  tax type             domestic equity ETFs: gains tax-free; others: 15.4 % on gains and payouts
  leverage / inverse   daily-reset products drift away from 2x / -1x over months: not for holding
  sectors, countries, top 10 holdings, dividend yield, fund flows (money in or out)

Overlap: for each pair, the weighted overlap = sum over shared holdings of the smaller of
the two weights. 0 % = nothing in common, 100 % = the same basket. Overseas ETFs often
publish shares but not weights: then only names are compared.

Data: Naver Finance and WiseReport public pages (unofficial; can change). --offline DIR
reads saved responses instead.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etf  # noqa: E402
import krx  # noqa: E402

SMALL_AUM = 50e8          # ₩50억: the size below which delisting risk is real
HIGH_FEE = 0.5            # %/yr


def warn_list(e, a):
    w = []
    if etf.is_leveraged(e["name"]):
        w.append("leveraged / inverse ETF: it resets daily, so over months it drifts away from 2x / -1x "
                 "of the index. Built for short holds, not for long-term investing")
    if (a.get("aum_won") or (e.get("aum_eok") or 0) * 1e8) < SMALL_AUM:
        w.append("small fund (under ₩50억): KRX can delist small ETFs; you would be paid out in cash")
    if (a.get("fee_pct") or 0) >= HIGH_FEE:
        w.append("high fee: %.2f%% a year (%.0f%% over 10 years, before growth)" % (a["fee_pct"], a["fee_pct"] * 10))
    if a.get("nav_deviation_pct") is not None and abs(a["nav_deviation_pct"]) >= 1.0:
        w.append("price is %.2f%% %s its NAV right now: you'd pay %s than the holdings are worth" % (
            abs(a["nav_deviation_pct"]), "above" if a["nav_deviation_pct"] > 0 else "below",
            "more" if a["nav_deviation_pct"] > 0 else "less"))
    top = [t for t in a["top10"] if not t["cash"] and t["weight"]]
    if top and top[0]["weight"] >= 25:
        w.append("concentrated: %s alone is %.1f%% of the fund" % (top[0]["name"], top[0]["weight"]))
    if top and sum(t["weight"] for t in top[:2]) >= 45:
        w.append("the top two holdings are %.1f%% of the fund" % sum(t["weight"] for t in top[:2]))
    return w


def show(code, lst, lang="en"):
    e = etf.resolve(code, lst)
    a = etf.analysis(e["code"])
    L = ["%s %s  (%s, %s)" % (e["code"], e["name"], a.get("issuer") or "-",
                               etf.TYPES_KO.get(e["type"]) if lang == "ko" else e["type_name"])]
    L.append("  Index        %s" % (a.get("index") or "-"))
    nav = e.get("nav") or a.get("nav")
    dev = (100.0 * (e["price"] / nav - 1)) if (e.get("price") and nav) else a.get("nav_deviation_pct")
    a["nav_deviation_pct"] = dev
    L.append("  Price        %s won  (NAV %s, 괴리율 %s)" % (krx.px(e["price"]), krx.px(nav),
                                                         ("%+.2f%%" % dev) if dev is not None else "-"))
    L.append("  Size         %s  (listed %s)" % (a.get("aum") or etf.eok((e.get("aum_eok") or 0) * 1e8),
                                                 krx_date(a.get("listed"))))
    L.append("  Fee          %s a year (총보수)" % (("%.4g%%" % a["fee_pct"]) if a.get("fee_pct") is not None else "-"))
    L.append("  Tracking err %s" % (("%.2f%%" % a["tracking_error_pct"]) if a.get("tracking_error_pct") is not None else "-"))
    tax = etf.TAX.get(a.get("tax_code"))
    L.append("  Tax          %s" % ((tax[1] if lang == "ko" else tax[0]) if tax else "check with your broker"))
    d = a.get("dividend") or {}
    if d.get("dividendYieldTtm") is not None:
        L.append("  Dividends    %.2f%% over the last 12 months (₩%s a share), paid in months %s" % (
            etf.num(d["dividendYieldTtm"]) or 0, "{:,}".format(int(etf.num(d.get("dividendPerShareTtm")) or 0)),
            d.get("dividendMonthThisYear") or "-"))
    r = a["returns"]
    L.append("  Returns      1m %s  3m %s  6m %s  1y %s  3y %s  5y %s   (as of %s)" % tuple(
        [etf.pct(r.get(k)) for k in ("M1", "M3", "M6", "Y1", "Y3", "Y5")] + [a.get("returns_date") or "-"]))
    f = a["flows"]
    if f:
        L.append("  Money in/out 1m %s  3m %s  1y %s" % (f.get("1m", "-"), f.get("3m", "-"), f.get("1y", "-")))
    if a["sectors"]:
        L.append("  Sectors      " + ", ".join("%s %.1f%%" % (etf.sector_name(s, lang), w)
                                         for s, w in a["sectors"][:6]))
    if a["countries"] and not (len(a["countries"]) == 1 and a["countries"][0][0] == "KR"):
        L.append("  Countries    " + ", ".join("%s %.1f%%" % (c, w) for c, w in a["countries"][:5]))
    top = [t for t in a["top10"] if not t["cash"]]
    if top:
        L.append("  Top holdings " + ", ".join("%s %s" % (t["name"], ("%.1f%%" % t["weight"]) if t["weight"] else "")
                                            for t in top[:10]))
        tw = sum(t["weight"] or 0 for t in top[:10])
        if tw:
            L.append("               the top 10 are %.1f%% of the fund" % tw)
    for w in warn_list(e, a):
        L.append("  Careful: " + w + ".")
    return L, {"etf": e, "analysis": a}


def krx_date(s):
    s = str(s or "")
    return "%s-%s-%s" % (s[:4], s[4:6], s[6:8]) if len(s) == 8 else (s or "-")


def overlap(codes, lst):
    """Pairwise weighted overlap and the shared holdings."""
    items = []
    for c in codes:
        e = etf.resolve(c, lst)
        b, cov = etf.basket(e["code"])
        if not b:
            names = {r["name"]: None for r in etf.holdings(e["code"])["rows"]}
            b = names
        items.append((e, b, cov))
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (ea, ba, _), (eb, bb, _) = items[i], items[j]
            shared = sorted(set(ba) & set(bb), key=lambda n: -min(ba[n] or 0, bb[n] or 0))
            weighted = None
            if any(v is not None for v in ba.values()) and any(v is not None for v in bb.values()):
                weighted = sum(min(ba[n] or 0, bb[n] or 0) for n in shared)
            pairs.append({"a": ea, "b": eb, "shared": [(n, ba[n], bb[n]) for n in shared], "weighted": weighted,
                          "count": len(shared), "n_a": len(ba), "n_b": len(bb)})
    return pairs


def overlap_lines(pairs):
    L = []
    for p in pairs:
        L.append("%s %s  vs  %s %s" % (p["a"]["code"], p["a"]["name"], p["b"]["code"], p["b"]["name"]))
        if p["weighted"] is not None:
            L.append("  Weighted overlap %.1f%%: %d holdings in common (of %d and %d)." % (
                p["weighted"], p["count"], p["n_a"], p["n_b"]))
        else:
            L.append("  %d holdings in common (of %d and %d); weights not published, so no weighted overlap." % (
                p["count"], p["n_a"], p["n_b"]))
        for n, wa, wb in p["shared"][:8]:
            L.append("    %-22s %6s  %6s" % (n[:22], ("%.1f%%" % wa) if wa else "-", ("%.1f%%" % wb) if wb else "-"))
        if p["weighted"] is not None and p["weighted"] >= 40:
            L.append("  Holding both is largely the same bet twice: a fall in the shared names hits both.")
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description="ETF Profile (etf-profile): what is inside an ETF.")
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--lang", choices=["en", "ko"])
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("show")
    p.add_argument("etfs", nargs="+")
    p = sub.add_parser("search")
    p.add_argument("words", nargs="+")
    p.add_argument("--type", type=int, choices=sorted(etf.TYPES), help="1 index, 2 sector, 3 leveraged, "
                   "4 overseas, 5 commodity, 6 bond, 7 other")
    p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("overlap")
    p.add_argument("etfs", nargs="+")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    etf.OFFLINE = a.offline
    try:
        lang = krx.lang_of(a.lang, krx.load_config())
        lst = etf.etf_list()
        if a.cmd == "show":
            docs = []
            for i, c in enumerate(a.etfs):
                lines, doc = show(c, lst, lang)
                docs.append(doc)
                if not a.json:
                    print(("\n" if i else "") + "\n".join(lines))
            if a.json:
                print(json.dumps(docs, indent=2, ensure_ascii=False))
        elif a.cmd == "search":
            hits = etf.search(" ".join(a.words), lst, a.type, a.limit)
            if a.json:
                print(json.dumps(hits, indent=2, ensure_ascii=False))
            for e in hits:
                print("%s  %-34s %10s won  %9s  3m %s  %s" % (e["code"], e["name"][:34], krx.px(e["price"]),
                                                             etf.eok((e["aum_eok"] or 0) * 1e8),
                                                             etf.pct(e["ret3m"]), e["type_name"]))
            if not hits:
                print("No ETF name contains all of: %s" % " ".join(a.words))
        else:
            if len(a.etfs) < 2:
                raise etf.ETFError("overlap needs two or more ETFs")
            pairs = overlap(a.etfs, lst)
            if a.json:
                print(json.dumps([{k: v for k, v in p.items()} for p in pairs], indent=2, ensure_ascii=False))
            else:
                print("\n".join(overlap_lines(pairs)))
        print("\nData: Naver Finance / WiseReport public pages, may lag a day. Not investment advice.")
        return 0
    except (etf.ETFError, krx.KRXError) as e:
        print("profile.py: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
