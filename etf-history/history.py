#!/usr/bin/env python3
"""ETF History for etf-history: how an ETF has behaved, and how different ways of buying it
would have turned out. Standard library only. Uses dividend-adjusted daily prices, so every
result assumes dividends were reinvested. Read-only.

    python3 history.py drawdowns 293180                 # every fall over 10 %: depth, length, recovery
    python3 history.py rolling 293180 --years 5         # every 5-year holding period since listing
    python3 history.py dca 293180 --monthly 100000 --years 5
    python3 history.py dca 293180 --monthly 100000 --since 2021-01 --day 10
    python3 history.py compare 293180 --amount 3000000 --years 5 --split 12
    python3 history.py dca 293180:60 360750:40 --monthly 300000 --years 5    # a mix, rebalanced by new money

dca      Monthly buying (적립식): the same amount on the first trading day on or after --day each
         month, whole shares only, leftover cash carried to next month, 0.015 % commission.
         Reports invested, value, gain, the money-weighted annual return (XIRR), the worst fall of
         the account, and the longest time the account was under water.
compare  One amount three ways: all at once on day one (lump sum), split evenly over --split months
         (분할매수), and the same total spread over the whole period. Same dates, same prices.
rolling  Every holding period of --years starting each month: best, median, worst and the share
         that lost money. The honest range of outcomes, not a forecast.
drawdowns Every fall over --min % from a high: when, how deep, how long to the bottom, and how long
         back to the old high (or still below it).

A mix is CODE:WEIGHT pairs. Each month's money goes to whichever holdings are furthest below
their target weight (no selling), which is how most people rebalance a monthly plan.

The past is the only data there is, and it is a sample of one. Not investment advice.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etf  # noqa: E402
import krx  # noqa: E402

COMMISSION = 0.00015


def parse_mix(items, lst):
    mix = []
    for it in items:
        code, _, w = it.partition(":")
        e = etf.resolve(code, lst)
        mix.append((e, float(w) if w else None))
    if len(mix) == 1 and mix[0][1] is None:
        return [(mix[0][0], 100.0)]
    if any(w is None for _, w in mix):
        raise etf.ETFError("for a mix give every ETF a weight, like 293180:60 360750:40")
    tot = sum(w for _, w in mix)
    return [(e, 100.0 * w / tot) for e, w in mix]


def common_dates(hs):
    sets = [set(h["dates"]) for h in hs]
    return sorted(set.intersection(*sets))


def series(h, dates):
    m = dict(zip(h["dates"], h["adj"]))
    return [m[d] for d in dates]


def buy_days(dates, day, start, end):
    """The first trading day on or after `day` in each month from start to end (YYYY-MM-DD)."""
    out, seen = [], set()
    for d in dates:
        if d < start or d > end:
            continue
        ym = d[:7]
        if ym in seen or int(d[8:10]) < day:
            continue
        seen.add(ym)
        out.append(d)
    return out


def xirr(flows):
    """Money-weighted annual return. flows = [(date, amount)], deposits negative, final value positive."""
    if not flows or all(a >= 0 for _, a in flows) or all(a <= 0 for _, a in flows):
        return None
    t0 = datetime.date.fromisoformat(flows[0][0])
    ts = [((datetime.date.fromisoformat(d) - t0).days / 365.25, a) for d, a in flows]

    def npv(r):
        return sum(a / (1 + r) ** t for t, a in ts)
    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return 100 * (lo + hi) / 2


def simulate(mix, prices, dates, schedule, day_amounts):
    """Run a buying plan. schedule: dates to buy; day_amounts: {date: won}. Returns the account path."""
    n = len(mix)
    shares = [0] * n
    cash, invested, flows, path = 0.0, 0.0, [], []
    targets = [w / 100.0 for _, w in mix]
    sched = set(schedule)
    for i, d in enumerate(dates):
        if d in sched:
            amt = day_amounts.get(d, 0.0)
            cash += amt
            invested += amt
            flows.append((d, -amt))
            vals = [shares[k] * prices[k][i] for k in range(n)]
            total = sum(vals) + cash
            # fill the most underweight holding first, whole shares only
            for _ in range(4 * n):
                gaps = [(targets[k] * total - vals[k], k) for k in range(n)]
                gaps.sort(reverse=True)
                bought = False
                for g, k in gaps:
                    p = prices[k][i] * (1 + COMMISSION)
                    q = int(min(g, cash) // p) if g > 0 else 0
                    if q <= 0 and n == 1:
                        q = int(cash // p)
                    if q > 0:
                        shares[k] += q
                        cash -= q * p
                        vals[k] = shares[k] * prices[k][i]
                        bought = True
                        break
                if not bought:
                    break
        value = sum(shares[k] * prices[k][i] for k in range(n)) + cash
        path.append((d, invested, value))
    return path, flows, shares, cash


def summarize(path, flows):
    end_d, invested, value = path[-1]
    irr = xirr(flows + [(end_d, value)])
    worst, peak_gain, under, longest, start_under = 0.0, None, 0, 0, None
    peak = 0.0
    for d, inv, val in path:
        if inv <= 0:
            continue
        peak = max(peak, val - inv + inv)  # value high-water mark
        # account fall measured on gain over invested money
        r = val / inv - 1
        peak_gain = r if peak_gain is None else max(peak_gain, r)
        worst = min(worst, val / inv - 1)
        if val < inv:
            if start_under is None:
                start_under = d
            longest = max(longest, (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(start_under)).days)
        else:
            start_under = None
    return {"invested": invested, "value": value, "gain": value - invested,
            "gain_pct": 100 * (value / invested - 1) if invested else None, "irr": irr,
            "worst_vs_invested_pct": 100 * worst, "longest_underwater_days": longest,
            "underwater_now": path[-1][2] < path[-1][1]}


def window(dates, years=None, since=None, until=None):
    end = until or dates[-1]
    if since:
        start = since if len(since) == 10 else since + "-01"
    elif years:
        e = datetime.date.fromisoformat(end)
        start = e.replace(year=e.year - years).isoformat() if not (e.month == 2 and e.day == 29) else \
            e.replace(year=e.year - years, day=28).isoformat()
    else:
        start = dates[0]
    if start < dates[0]:
        start = dates[0]
    return start, end


def load(mix):
    hs = [etf.history(e["code"]) for e, _ in mix]
    dates = common_dates(hs)
    prices = [series(h, dates) for h in hs]
    return dates, prices


def mix_label(mix):
    return " + ".join("%s %s %.0f%%" % (e["code"], e["name"], w) for e, w in mix) if len(mix) > 1 else \
        "%s %s" % (mix[0][0]["code"], mix[0][0]["name"])


def cmd_dca(a, lst):
    mix = parse_mix(a.etfs, lst)
    dates, prices = load(mix)
    start, end = window(dates, a.years, a.since)
    days = buy_days(dates, a.day, start, end)
    if not days:
        raise etf.ETFError("no buying days between %s and %s" % (start, end))
    sub = [d for d in dates if d >= days[0] and d <= end]
    idx = [dates.index(sub[0]), dates.index(sub[-1]) + 1]
    pr = [p[idx[0]:idx[1]] for p in prices]
    path, flows, shares, cash = simulate(mix, pr, sub, days, {d: a.monthly for d in days})
    s = summarize(path, flows)
    L = ["Monthly buying (적립식): %s won on day %d of each month, %s" % (krx.px(a.monthly), a.day, mix_label(mix)),
         "  %s to %s: %d purchases, dividends reinvested, 0.015%% commission, whole shares." % (
             days[0], sub[-1], len(days)),
         "  Invested %s, worth %s: %s (%s)." % (krx.won(s["invested"]), krx.won(s["value"]), krx.won(s["gain"], True),
                                               etf.pct(s["gain_pct"])),
         "  Money-weighted return %s a year (XIRR)." % (etf.pct(s["irr"]) if s["irr"] is not None else "-"),
         "  Worst point: the account was %s against the money put in; the longest stretch below the money put in "
         "was %d days%s." % (etf.pct(s["worst_vs_invested_pct"]), s["longest_underwater_days"],
                            " (and it is below now)" if s["underwater_now"] else "")]
    return L, dict(s, mix=[(e["code"], w) for e, w in mix], start=days[0], end=sub[-1], purchases=len(days))


def cmd_compare(a, lst):
    mix = parse_mix(a.etfs, lst)
    dates, prices = load(mix)
    start, end = window(dates, a.years, a.since)
    days = buy_days(dates, a.day, start, end)
    if len(days) < 2:
        raise etf.ETFError("not enough months between %s and %s" % (start, end))
    sub = [d for d in dates if days[0] <= d <= end]
    i0 = dates.index(sub[0])
    pr = [p[i0:i0 + len(sub)] for p in prices]
    plans = [("all at once on %s" % days[0], {days[0]: a.amount}),
             ("split over %d months (분할매수)" % a.split, {d: a.amount / min(a.split, len(days))
                                                          for d in days[:a.split]}),
             ("spread over all %d months" % len(days), {d: a.amount / len(days) for d in days})]
    L = ["%s won into %s, %s to %s, three ways (dividends reinvested):" % (krx.px(a.amount), mix_label(mix),
                                                                           days[0], sub[-1])]
    out = []
    for name, amounts in plans:
        path, flows, _, _ = simulate(mix, pr, sub, sorted(amounts), amounts)
        s = summarize(path, flows)
        out.append(dict(s, plan=name))
        L.append("  %-34s worth %12s  %8s  worst %7s vs money in, %4d days below it%s" % (
            name, krx.won(s["value"]), etf.pct(s["gain_pct"]), etf.pct(s["worst_vs_invested_pct"]),
            s["longest_underwater_days"], ", below now" if s["underwater_now"] else ""))
    best = max(out, key=lambda s: s["value"])
    L.append("  In this period '%s' ended highest. In a rising market buying sooner wins; in a falling one, "
             "spreading out wins. Which one comes next is not knowable." % best["plan"])
    return L, out


def cmd_rolling(a, lst):
    mix = parse_mix(a.etfs, lst)
    if len(mix) > 1:
        raise etf.ETFError("rolling takes one ETF")
    h = etf.history(mix[0][0]["code"])
    me = etf.month_ends(h)
    n = 12 * a.years
    rets = []
    for i in range(len(me) - n):
        r = (me[i + n][2] / me[i][2]) ** (1.0 / a.years) - 1
        rets.append((me[i][1], 100 * r))
    if not rets:
        raise etf.ETFError("%s has %.1f years of prices; it needs more than %d" % (
            mix[0][0]["name"], len(me) / 12.0, a.years))
    vals = sorted(r for _, r in rets)
    neg = sum(1 for v in vals if v < 0)
    best = max(rets, key=lambda x: x[1])
    worst = min(rets, key=lambda x: x[1])
    L = ["Every %d-year holding period of %s %s, buying at a month end (dividends reinvested):" % (
        a.years, mix[0][0]["code"], mix[0][0]["name"]),
        "  %d periods from %s. Annual return: best %s (from %s), median %s, worst %s (from %s)." % (
            len(rets), rets[0][0][:7], etf.pct(best[1]), best[0][:7], etf.pct(vals[len(vals) // 2]),
            etf.pct(worst[1]), worst[0][:7]),
        "  %d of %d periods (%.0f%%) lost money over the full %d years." % (neg, len(vals), 100.0 * neg / len(vals),
                                                                           a.years),
        "  Overlapping periods are not independent: %d years of data is only %.1f separate %d-year periods." % (
            len(me) // 12, len(me) / 12.0 / a.years, a.years)]
    return L, {"periods": len(rets), "best": best, "worst": worst, "median": vals[len(vals) // 2],
               "share_negative": neg / len(vals)}


def cmd_drawdowns(a, lst):
    mix = parse_mix(a.etfs, lst)
    if len(mix) > 1:
        raise etf.ETFError("drawdowns takes one ETF")
    h = etf.history(mix[0][0]["code"])
    eps, peak, pd_, trough = [], h["adj"][0], h["dates"][0], None
    for d, c in zip(h["dates"], h["adj"]):
        if c >= peak:
            if trough and trough[1] <= -a.min:
                eps.append((pd_, trough[0], trough[1], d))
            peak, pd_, trough = c, d, None
        else:
            dd = 100 * (c / peak - 1)
            if trough is None or dd < trough[1]:
                trough = (d, dd)
    if trough and trough[1] <= -a.min:
        eps.append((pd_, trough[0], trough[1], None))
    days = lambda x, y: (datetime.date.fromisoformat(y) - datetime.date.fromisoformat(x)).days  # noqa: E731
    L = ["Falls of %g%% or more in %s %s since %s (dividends reinvested):" % (a.min, mix[0][0]["code"],
                                                                             mix[0][0]["name"], h["dates"][0])]
    for p, t, depth, rec in sorted(eps, key=lambda e: e[2]):
        L.append("  %s  from %s, bottom %s after %4d days, %s" % (
            etf.pct(depth), p, t, days(p, t), ("back to the high on %s (%d days after the bottom)" % (rec, days(t, rec)))
            if rec else "still below the high (%s now)" % etf.pct(100 * (h["adj"][-1] / max(h["adj"]) - 1))))
    if not eps:
        L.append("  none")
    return L, [{"peak": p, "bottom": t, "depth": d, "recovered": r} for p, t, d, r in eps]


def main(argv=None):
    ap = argparse.ArgumentParser(description="ETF History (etf-history): drawdowns, DCA and rolling returns.")
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    def when(p):
        p.add_argument("--years", type=int, help="the last N years (default: all the data)")
        p.add_argument("--since", help="start month, YYYY-MM")
        p.add_argument("--day", type=int, default=1, help="buy on the first trading day on or after this day")
    p = sub.add_parser("dca")
    p.add_argument("etfs", nargs="+", help="CODE, or CODE:WEIGHT pairs for a mix")
    p.add_argument("--monthly", type=float, required=True)
    when(p)
    p = sub.add_parser("compare")
    p.add_argument("etfs", nargs="+")
    p.add_argument("--amount", type=float, required=True)
    p.add_argument("--split", type=int, default=12)
    when(p)
    p = sub.add_parser("rolling")
    p.add_argument("etfs", nargs=1)
    p.add_argument("--years", type=int, default=5)
    p = sub.add_parser("drawdowns")
    p.add_argument("etfs", nargs=1)
    p.add_argument("--min", type=float, default=10.0)
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    etf.OFFLINE = a.offline
    try:
        lst = etf.etf_list()
        lines, doc = {"dca": cmd_dca, "compare": cmd_compare, "rolling": cmd_rolling,
                      "drawdowns": cmd_drawdowns}[a.cmd](a, lst)
        if a.json:
            print(json.dumps(doc, indent=2, ensure_ascii=False, default=str))
        else:
            print("\n".join(lines))
            print("Past results, not a forecast. Not investment advice.")
        return 0
    except (etf.ETFError, krx.KRXError) as e:
        print("history.py: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
