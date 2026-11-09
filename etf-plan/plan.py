#!/usr/bin/env python3
"""Goal Planner for etf-plan: turns YOUR goal and YOUR chosen mix into numbers you can check:
what return the goal needs, how often your mix delivered that in the past, how far it has
fallen, whether it breaks your own rules, and where this month's money goes to stay on plan.
Standard library only. It never picks ETFs for you and never places an order.

    python3 plan.py goal --target 30000000 --years 5 --monthly 300000 --risk medium \\
        --note "house deposit; I can't add more money"
    python3 plan.py mix 069500=50 360750=30 411060=20      # your target mix, % each
    python3 plan.py rules --max-stock 20 --max-sector 40 --max-etf 60 --no-leverage
    python3 plan.py show                                   # the whole check
    python3 plan.py next                                   # just this month's buy list
    python3 plan.py show --json

Reads krx/etf_goal.json (written by goal / mix / rules) and krx/etf_portfolio.json (etf-portfolio).

What `show` reports:
  1. Goal math   the yearly return needed to reach the target from today's value plus the monthly
                 money in the time you gave (0 % needed = saving alone gets there).
  2. Track record every past N-year period of your mix (rebalanced monthly, dividends reinvested):
                 how often it earned the needed return, the median and worst outcomes.
  3. Risk fit    the mix's deepest past fall versus the fall your risk level says you can sit
                 through (low 15 %, medium 30 %, high 50 %). A plan you abandon in a crash fails.
  4. Your rules  look-through limits on one stock, one sector, one ETF, and leverage, for the
                 target mix and for what you hold now.
  5. Drift       current weight vs target per ETF, holdings outside the plan.
  6. This month  the monthly budget split across the most underweight ETFs in whole shares, at the
                 latest price (new money only; nothing is sold). You place any order yourself.

The track record covers only the years the youngest ETF in the mix has existed. Past returns
are a sample, not a promise. Not investment advice: the goal, the mix and the rules are yours.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etf  # noqa: E402
import krx  # noqa: E402

RISK_FALL = {"low": 15.0, "medium": 30.0, "high": 50.0}


def load_goal(path=etf.GOAL):
    return krx.read_json(path, None) or {}


def save_goal(g, path=etf.GOAL):
    g["updated_at"] = krx.iso_utc(krx.utc_now())
    krx.write_json(path, g)


def needed_return(v0, monthly, target, years):
    """Annual return (%) that grows v0 plus `monthly` each month to `target` in `years`."""
    n = int(round(12 * years))
    if n <= 0:
        return None

    def fv(r):
        m = (1 + r) ** (1 / 12.0) - 1
        if abs(m) < 1e-12:
            return v0 + monthly * n
        return v0 * (1 + m) ** n + monthly * ((1 + m) ** n - 1) / m
    if fv(0.0) >= target:
        return 0.0 if fv(-0.5) < target else -50.0
    lo, hi = 0.0, 3.0
    if fv(hi) < target:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if fv(mid) < target:
            lo = mid
        else:
            hi = mid
    return 100 * (lo + hi) / 2


def mix_monthly(mix):
    """Monthly returns of the mix, rebalanced monthly: [(YYYY-MM, r)], and the start month."""
    series = []
    for code, w in mix.items():
        me = etf.month_ends(etf.history(code))
        series.append((w / 100.0, {m: v for m, _, v in me}))
    months = sorted(set.intersection(*[set(s) for _, s in series]))
    out = []
    for i in range(1, len(months)):
        r = sum(w * (s[months[i]] / s[months[i - 1]] - 1) for w, s in series)
        out.append((months[i], r))
    return out


def track_record(monthly, years, needed):
    n = int(12 * years)
    if len(monthly) < n + 1:
        return None
    rets = []
    for i in range(len(monthly) - n + 1):
        g = 1.0
        for _, r in monthly[i:i + n]:
            g *= 1 + r
        rets.append(100 * (g ** (1.0 / years) - 1))
    v = sorted(rets)
    hit = sum(1 for x in v if needed is not None and x >= needed)
    return {"periods": len(v), "median": v[len(v) // 2], "worst": v[0], "best": v[-1], "hit": hit,
            "first": monthly[0][0], "last": monthly[-1][0]}


def max_fall(monthly):
    g, peak, worst = 1.0, 1.0, 0.0
    for _, r in monthly:
        g *= 1 + r
        peak = max(peak, g)
        worst = min(worst, 100 * (g / peak - 1))
    return worst


def exposure(weights):
    """weights {code: % of money} -> look-through {stock: %}, {sector: %}."""
    stocks, sectors = {}, {}
    for code, w in weights.items():
        b, _ = etf.basket(code)
        for n, x in b.items():
            stocks[n] = stocks.get(n, 0) + w * x / 100.0
        for s, x in etf.analysis(code)["sectors"]:
            sectors[s] = sectors.get(s, 0) + w * x / 100.0
    return stocks, sectors


def rule_breaks(weights, rules, lst):
    by = {e["code"]: e for e in lst}
    out = []
    stocks, sectors = exposure(weights)
    if rules.get("max_stock"):
        for n, x in sorted(stocks.items(), key=lambda t: -t[1]):
            if x > rules["max_stock"]:
                out.append("%s is %.1f%%, over your %g%% limit for one stock" % (n, x, rules["max_stock"]))
    if rules.get("max_sector"):
        for s, x in sectors.items():
            if x > rules["max_sector"]:
                out.append("%s is %.1f%%, over your %g%% limit for one sector" % (etf.sector_name(s), x,
                                                                                 rules["max_sector"]))
    if rules.get("max_etf"):
        for c, x in weights.items():
            if x > rules["max_etf"]:
                out.append("%s is %.1f%%, over your %g%% limit for one ETF" % (by.get(c, {}).get("name", c), x,
                                                                              rules["max_etf"]))
    if rules.get("no_leverage"):
        for c in weights:
            if etf.is_leveraged(by.get(c, {}).get("name", "")):
                out.append("%s is leveraged / inverse, which your rules exclude" % by[c]["name"])
    return out


def current(pf, lst):
    by = {e["code"]: e for e in lst}
    vals = {p["code"]: p["qty"] * by[p["code"]]["price"] for p in pf["positions"] if p["code"] in by}
    total = sum(vals.values()) + float(pf.get("cash") or 0)
    return vals, total


def next_buys(g, pf, lst, budget=None):
    """This month's money to the most underweight target ETFs, whole shares, no selling."""
    by = {e["code"]: e for e in lst}
    vals, total = current(pf, lst)
    cash = float(budget if budget is not None else g.get("monthly") or 0)
    after = total + cash
    want = {c: after * w / 100.0 - vals.get(c, 0.0) for c, w in g["mix"].items()}
    buys = {c: 0 for c in g["mix"]}
    for _ in range(500):
        cands = [(want[c] - buys[c] * by[c]["price"], c) for c in g["mix"] if by[c]["price"] <= cash]
        cands = [(gap, c) for gap, c in cands if gap > 0]
        if not cands:
            break
        gap, c = max(cands)
        buys[c] += 1
        cash -= by[c]["price"]
    return {c: q for c, q in buys.items() if q}, cash, vals, total


def cmd_show(a, lst, only_next=False):
    g = load_goal(a.goal)
    if not g.get("mix"):
        raise etf.ETFError("no target mix yet: plan.py mix CODE=WEIGHT ... (e.g. 069500=60 360750=40)")
    pf = etf.load_portfolio(a.portfolio)
    by = {e["code"]: e for e in lst}
    L, doc = [], {}
    buys, left, vals, total = next_buys(g, pf, lst, a.budget)
    if not only_next:
        L.append("Your plan%s" % ((": " + g["note"]) if g.get("note") else ""))
        L.append("  Target mix: " + ", ".join("%s %s %g%%" % (c, by.get(c, {}).get("name", "?"), w)
                                             for c, w in g["mix"].items()))
        need = None
        if g.get("target") and g.get("years"):
            need = needed_return(total, float(g.get("monthly") or 0), float(g["target"]), float(g["years"]))
            saved = total + float(g.get("monthly") or 0) * 12 * float(g["years"])
            L.append("")
            L.append("1. Goal: %s in %g years, starting from %s and adding %s a month (%s saved in total)." % (
                krx.won(g["target"]), g["years"], krx.won(total), krx.won(g.get("monthly") or 0), krx.won(saved)))
            if need is None:
                L.append("   No realistic return gets there: the goal needs more money in, more time, or a lower target.")
            elif need <= 0:
                L.append("   Saving alone reaches it: the investments only need not to lose money.")
            else:
                L.append("   It needs about %s a year after costs." % etf.pct(need, 1, False))
        monthly = mix_monthly(g["mix"])
        yrs = float(g.get("years") or 5)
        tr = track_record(monthly, yrs, need)
        L.append("")
        if tr:
            L.append("2. Track record of this mix, every %g-year period %s to %s (%d periods):" % (
                yrs, tr["first"], tr["last"], tr["periods"]))
            L.append("   median %s a year, worst %s, best %s." % (etf.pct(tr["median"]), etf.pct(tr["worst"]),
                                                                  etf.pct(tr["best"])))
            if need is not None and need > 0:
                L.append("   It earned the needed %s or more in %d of %d periods (%.0f%%)." % (
                    etf.pct(need, 1, False), tr["hit"], tr["periods"], 100.0 * tr["hit"] / tr["periods"]))
        elif len(monthly) >= 12:
            g_all = 1.0
            for _, r in monthly:
                g_all *= 1 + r
            yrs_all = len(monthly) / 12.0
            ann = 100 * (g_all ** (1.0 / yrs_all) - 1)
            L.append("2. Track record: the mix has only %.1f years of shared history (%s to %s), shorter than the "
                     "%g-year goal, so there is no full period to test. Over those %.1f years it returned %s a year." % (
                         yrs_all, monthly[0][0], monthly[-1][0], yrs, yrs_all, etf.pct(ann)))
            tr = {"periods": 0, "annual_all": ann, "years_all": yrs_all}
        else:
            L.append("2. Track record: under a year of shared history for this mix.")
        fall = max_fall(monthly)
        risk = g.get("risk") or "medium"
        L.append("")
        L.append("3. Deepest fall of this mix (month-end, since %s): %s. Your risk level '%s' means about %s." % (
            monthly[0][0] if monthly else "-", etf.pct(fall), risk, etf.pct(-RISK_FALL.get(risk, 30))))
        if fall < -RISK_FALL.get(risk, 30):
            L.append("   The mix has fallen further than you said you could sit through. Selling in a crash "
                     "locks in the loss; a mix you can hold matters more than a higher return.")
        rules = g.get("rules") or {}
        L.append("")
        tgt_breaks = rule_breaks(g["mix"], rules, lst) if rules else []
        cur_w = {c: 100 * v / total for c, v in vals.items()} if total else {}
        cur_breaks = rule_breaks(cur_w, rules, lst) if rules and cur_w else []
        if not rules:
            L.append("4. Your rules: none set (plan.py rules --max-stock 20 --max-sector 40 --max-etf 60 --no-leverage).")
        else:
            L.append("4. Your rules (one stock <= %s%%, one sector <= %s%%, one ETF <= %s%%%s):" % (
                rules.get("max_stock", "-"), rules.get("max_sector", "-"), rules.get("max_etf", "-"),
                ", no leverage" if rules.get("no_leverage") else ""))
            L.append("   target mix: " + ("; ".join(tgt_breaks) if tgt_breaks else "within your rules"))
            if cur_w:
                L.append("   what you hold now: " + ("; ".join(cur_breaks) if cur_breaks else "within your rules"))
        L.append("")
        L.append("5. Drift (now vs target):")
        for c, w in g["mix"].items():
            now = 100 * vals.get(c, 0) / total if total else 0
            L.append("   %s %-24s now %5.1f%%  target %5.1f%%  %s" % (c, by.get(c, {}).get("name", "?")[:24], now, w,
                                                                    etf.pct(now - w) + " pts"))
        extra = [c for c in vals if c not in g["mix"]]
        for c in extra:
            L.append("   %s %-24s now %5.1f%%  not in your plan: keep it, or stop adding to it" % (
                c, by[c]["name"][:24], 100 * vals[c] / total))
        doc.update(needed=need, track=tr, max_fall=fall, rule_breaks={"target": tgt_breaks, "current": cur_breaks})
        L.append("")
    budget = float(a.budget if a.budget is not None else g.get("monthly") or 0)
    L.append("%sThis month's %s, toward the target mix (whole shares at the latest price, nothing sold):" % (
        "" if only_next else "6. ", krx.won(budget)))
    if not buys:
        L.append("   nothing: the budget is below one share of every underweight ETF, or you are on target.")
    for c, q in buys.items():
        L.append("   %s %-24s %4d share%s x %s = %s" % (c, by[c]["name"][:24], q, "" if q == 1 else "s",
                                                         krx.px(by[c]["price"]),
                                                       krx.won(q * by[c]["price"])))
    L.append("   left over %s (carried to next month)." % krx.won(left))
    L.append("You decide and place every order yourself. The goal, mix and rules are yours; past returns are a "
             "sample, not a promise. Not investment advice.")
    doc.update(buys=buys, left=left)
    return L, doc


def main(argv=None):
    ap = argparse.ArgumentParser(description="Goal Planner (etf-plan).")
    ap.add_argument("--goal", default=etf.GOAL, help="goal file (default krx/etf_goal.json)")
    ap.add_argument("--portfolio", default=etf.PORTFOLIO)
    ap.add_argument("--offline", metavar="DIR")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("goal")
    p.add_argument("--target", type=float)
    p.add_argument("--years", type=float)
    p.add_argument("--monthly", type=float)
    p.add_argument("--risk", choices=sorted(RISK_FALL))
    p.add_argument("--note")
    p = sub.add_parser("mix")
    p.add_argument("items", nargs="+", help="CODE=WEIGHT")
    p = sub.add_parser("rules")
    p.add_argument("--max-stock", type=float)
    p.add_argument("--max-sector", type=float)
    p.add_argument("--max-etf", type=float)
    p.add_argument("--no-leverage", action="store_true")
    for name in ("show", "next"):
        p = sub.add_parser(name)
        p.add_argument("--budget", type=float, help="this month's money (default: the goal's monthly)")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    etf.OFFLINE = a.offline
    try:
        lst = etf.etf_list()
        g = load_goal(a.goal)
        if a.cmd == "goal":
            for k in ("target", "years", "monthly", "risk", "note"):
                if getattr(a, k) is not None:
                    g[k] = getattr(a, k)
            save_goal(g, a.goal)
            print("Goal saved: %s in %s years, %s a month, risk %s." % (
                krx.won(g.get("target") or 0), g.get("years", "-"), krx.won(g.get("monthly") or 0), g.get("risk", "-")))
            return 0
        if a.cmd == "mix":
            mix = {}
            for it in a.items:
                code, _, w = it.replace(":", "=").partition("=")
                e = etf.resolve(code, lst)
                mix[e["code"]] = float(w)
            tot = sum(mix.values())
            if abs(tot - 100) > 0.5:
                raise etf.ETFError("the weights add up to %g%%, not 100%%" % tot)
            g["mix"] = mix
            save_goal(g, a.goal)
            print("Target mix saved: " + ", ".join("%s %g%%" % (c, w) for c, w in mix.items()))
            return 0
        if a.cmd == "rules":
            r = g.get("rules") or {}
            for k in ("max_stock", "max_sector", "max_etf"):
                if getattr(a, k) is not None:
                    r[k] = getattr(a, k)
            if a.no_leverage:
                r["no_leverage"] = True
            g["rules"] = r
            save_goal(g, a.goal)
            print("Rules saved: %s" % json.dumps(r))
            return 0
        lines, doc = cmd_show(a, lst, only_next=a.cmd == "next")
        if a.json:
            print(json.dumps(doc, indent=2, ensure_ascii=False, default=str))
        else:
            print("\n".join(lines))
        return 0
    except (etf.ETFError, krx.KRXError) as e:
        print("plan.py: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
