#!/usr/bin/env python3
"""etf.py: Korean-listed ETF data for the krx-etf-investor skills. Standard library only.
One copy lives in every skill folder (tools/sync.py keeps them identical).

Sources (public, no login, read 2026-11-09):
  ETF list      https://finance.naver.com/api/sise/etfItemList.nhn
                every KRX-listed ETF: code, name, price, NAV, AUM (억원), 3-month return,
                and Naver's type tab (1 domestic index, 2 sector/theme, 3 leveraged/inverse,
                4 overseas equity, 5 commodity, 6 bond, 7 other). EUC-KR encoded.
  Analysis      https://m.stock.naver.com/api/stock/<code>/etfAnalysis
                issuer, base index, total fee (총보수, % a year), tracking error, tax type,
                NAV deviation, returns, fund flows, asset/country/sector mix, top 10 holdings
                with weights, dividends.
  Holdings      https://navercomp.wisereport.co.kr/v2/ETF/index.aspx?cmp_cd=<code>
                the full basket (CU: 구성종목) as an embedded JSON object `CU_data`.
  Stock values  https://m.stock.naver.com/api/stock/<code>/integration
                a stock's PER / PBR / dividend yield (totalInfos), for look-through valuation.
  Prices        Yahoo Finance chart API, <code>.KS, daily, with dividends and adjusted close.

These are unofficial endpoints of public web pages. They can change without notice;
every parser fails with a plain message rather than a wrong number.
"""

import datetime
import json
import os
import re
import time

import krx

LIST_URL = "https://finance.naver.com/api/sise/etfItemList.nhn"
ANALYSIS_URL = "https://m.stock.naver.com/api/stock/%s/etfAnalysis"
WISE_URL = "https://navercomp.wisereport.co.kr/v2/ETF/index.aspx?cmp_cd=%s"
STOCK_URL = "https://m.stock.naver.com/api/stock/%s/integration"
LIST_CACHE = os.path.join(krx.DATA_DIR, "state", "etf_list.json")
CACHE_DIR = os.path.join(krx.DATA_DIR, "state", "etf_cache")
PORTFOLIO = os.path.join(krx.DATA_DIR, "etf_portfolio.json")
GOAL = os.path.join(krx.DATA_DIR, "etf_goal.json")
HEADERS = {"Referer": "https://finance.naver.com/"}

TYPES = {1: "domestic index", 2: "sector / theme", 3: "leveraged / inverse", 4: "overseas equity",
         5: "commodity", 6: "bond", 7: "other"}
TYPES_KO = {1: "국내 시장지수", 2: "국내 업종/테마", 3: "레버리지/인버스", 4: "해외 주식", 5: "원자재",
            6: "채권", 7: "기타"}
TAX = {
    "1": ("domestic equity ETF: no tax on the gain when you sell; distributions taxed 15.4 %",
          "국내주식형: 매매차익 비과세, 분배금 15.4 % 과세"),
    "2": ("other ETF (overseas, bond, commodity...): gains and distributions taxed 15.4 % as dividend "
          "income (the lesser of your gain and the taxable-base increase); counts toward the "
          "₩20M financial-income threshold",
          "기타 ETF(해외·채권·원자재 등): 매매차익과 분배금 모두 배당소득세 15.4 % (보유기간 과세, "
          "과표기준가 기준), 금융소득종합과세 대상"),
}
SECTORS_KO = {"IT": "IT", "INDUSTRIALS": "산업재", "FINANCIALS": "금융", "CONSUMER_DISCRETIONARY": "경기소비재",
              "COMMUNICATION": "커뮤니케이션", "HEALTHCARE": "헬스케어", "MATERIALS": "소재",
              "CONSUMER_STAPLES": "필수소비재", "ENERGY": "에너지", "UTILITIES": "유틸리티",
              "REAL_ESTATE": "부동산", "UNCLASSIFIED": "기타"}
SECTORS_EN = {"IT": "IT", "INDUSTRIALS": "industrials", "FINANCIALS": "financials",
              "CONSUMER_DISCRETIONARY": "consumer discretionary", "COMMUNICATION": "communication",
              "HEALTHCARE": "healthcare", "MATERIALS": "materials", "CONSUMER_STAPLES": "consumer staples",
              "ENERGY": "energy", "UTILITIES": "utilities", "REAL_ESTATE": "real estate", "UNCLASSIFIED": "other"}
CASH_WORDS = ("현금", "설정현금액", "CASH")
LEVERAGE_WORDS = ("레버리지", "인버스", "2X", "선물인버스", "곱버스")


class ETFError(Exception):
    pass


# ---------------------------------------------------------------- fetching

OFFLINE = None    # a folder of saved responses (tests and --offline): etfItemList.json,
                  # etfAnalysis-<code>.json, wise-etf-<code>.html, integration-<code>.json,
                  # yahoo-<code>-10y.json


def _decode(data):
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def _offline(name):
    p = os.path.join(OFFLINE, name)
    if not os.path.exists(p):
        raise ETFError("no offline file %s" % p)
    with open(p, "rb") as fh:
        return _decode(fh.read())


def fetch(url, offline_name):
    if OFFLINE:
        return _offline(offline_name)
    try:
        return _decode(krx.http_get(url, headers=HEADERS, binary=True))
    except Exception as e:
        raise ETFError("could not read %s (%s)" % (url.split("?")[0], e))


def _cached(name, max_age_s, producer):
    """JSON from krx/state/etf_cache/<name> if fresh, else producer() saved there."""
    path = os.path.join(CACHE_DIR, name)
    if not OFFLINE and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_s:
        doc = krx.read_json(path)
        if doc is not None:
            return doc
    doc = producer()
    if not OFFLINE:
        try:
            krx.write_json(path, doc)
        except OSError:
            pass
    return doc


def sector_name(code, lang="en"):
    return (SECTORS_KO if lang == "ko" else SECTORS_EN).get(code, str(code).title())


def num(x):
    """'3,119억' / '33.02%' / 1.2 / '-' -> float or None."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    t = str(x).replace(",", "").replace("%", "").replace("억", "").replace("원", "").strip()
    if t in ("", "-", "N/A"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


# ---------------------------------------------------------------- the list

def etf_list(max_age_s=6 * 3600):
    """[{code, name, price, nav, aum_eok, ret3m, type, type_name, volume, value_mil}] for every ETF."""
    def produce():
        try:
            doc = json.loads(fetch(LIST_URL, "etfItemList.json"))
            rows = doc["result"]["etfItemList"]
        except (ValueError, KeyError, TypeError):
            raise ETFError("Naver's ETF list is not the shape this tool knows")
        out = []
        for it in rows:
            t = int(it.get("etfTabCode") or 7)
            out.append({"code": str(it.get("itemcode")), "name": str(it.get("itemname") or "").strip(),
                        "price": num(it.get("nowVal")), "nav": num(it.get("nav")),
                        "change_pct": num(it.get("changeRate")), "aum_eok": num(it.get("marketSum")),
                        "ret3m": num(it.get("threeMonthEarnRate")), "type": t, "type_name": TYPES.get(t, "other"),
                        "volume": num(it.get("quant")), "value_mil": num(it.get("amonut"))})
        return {"saved_at": krx.iso_utc(krx.utc_now()), "etfs": out}
    return _cached("etf_list.json", max_age_s, produce)["etfs"]


def resolve(text, lst=None):
    """'293180', 'A293180', 'HANARO 200', '하나로 200'(no), '반도체TOP10' -> the ETF row."""
    lst = lst if lst is not None else etf_list()
    raw = str(text or "").strip()
    up = raw.upper().replace(".KS", "")
    if len(up) == 7 and up[0] == "A":
        up = up[1:]
    by_code = {e["code"]: e for e in lst}
    if up in by_code:
        return by_code[up]
    key = raw.replace(" ", "").lower()
    exact = [e for e in lst if e["name"].replace(" ", "").lower() == key]
    if len(exact) == 1:
        return exact[0]
    part = [e for e in lst if key and key in e["name"].replace(" ", "").lower()]
    if len(part) == 1:
        return part[0]
    if part:
        part.sort(key=lambda e: -(e["aum_eok"] or 0))
        raise ETFError("%r matches %d ETFs: %s%s. Give the 6-character code." % (
            raw, len(part), "; ".join("%s %s" % (e["code"], e["name"]) for e in part[:8]),
            " ..." if len(part) > 8 else ""))
    raise ETFError("no KRX-listed ETF called %r (codes look like 069500)" % raw)


def search(query, lst=None, etf_type=None, limit=20):
    lst = lst if lst is not None else etf_list()
    words = [w.lower() for w in str(query or "").split()]
    hits = [e for e in lst if all(w in e["name"].lower().replace(" ", "") or w in e["name"].lower() for w in words)
            and (etf_type is None or e["type"] == etf_type)]
    hits.sort(key=lambda e: -(e["aum_eok"] or 0))
    return hits[:limit]


def is_leveraged(name):
    return any(w.upper() in name.upper() for w in LEVERAGE_WORDS)


# ---------------------------------------------------------------- one ETF

def analysis(code, max_age_s=6 * 3600):
    """Parsed etfAnalysis: the facts a long-term holder checks."""
    def produce():
        try:
            d = json.loads(fetch(ANALYSIS_URL % code, "etfAnalysis-%s.json" % code))
        except ValueError:
            raise ETFError("Naver's ETF analysis for %s is not JSON" % code)
        if not isinstance(d, dict) or not d.get("itemCode"):
            raise ETFError("Naver has no ETF analysis for %s" % code)
        top = []
        for it in d.get("etfTop10MajorConstituentAssets") or []:
            nm = str(it.get("itemName") or "").strip()
            top.append({"name": nm, "code": it.get("itemCode") or "", "weight": num(it.get("etfWeight")),
                        "cash": any(w in nm for w in CASH_WORDS)})
        perf = {p.get("periodTypeCode"): num(p.get("value")) for p in d.get("returnPerformanceList") or []}
        navp = {p.get("periodTypeCode"): num(p.get("value")) for p in d.get("navPerformanceList") or []}
        flows = d.get("cumulativeNetInflowList") or {}
        mix = lambda k: [(x.get("detailTypeCode"), num(x.get("weight"))) for x in d.get(k) or []  # noqa: E731
                         if (num(x.get("weight")) or 0) > 0]
        dev = num(d.get("deviationRate"))
        if dev is not None and d.get("deviationSign") == "-":
            dev = -dev
        return {"code": code, "name": d.get("itemName"), "issuer": d.get("issuerName"),
                "index": d.get("etfBaseIndex"), "listed": d.get("listedDate"),
                "summary": re.sub(r"<br\s*/?>", " ", str(d.get("etfSummary") or "")).strip(),
                "fee_pct": num(d.get("totalFee")), "tracking_error_pct": num(d.get("chaseErrorRate")),
                "tax_code": str(d.get("taxationTypeCode") or ""), "aum": d.get("marketValue"),
                "aum_won": num(d.get("marketValueRaw")), "nav": num(d.get("nav")), "nav_deviation_pct": dev,
                "returns": perf, "returns_date": d.get("returnPerformanceReferenceDate"), "nav_returns": navp,
                "flows": {k.replace("cumulativeNetInflow", ""): v for k, v in flows.items() if k != "referenceDate"},
                "assets": mix("assetPortfolioList"), "countries": mix("countryPortfolioList"),
                "sectors": mix("sectorPortfolioList"), "top10": top, "dividend": d.get("dividend") or {}}
    return _cached("analysis-%s.json" % code, max_age_s, produce)


def holdings(code, max_age_s=24 * 3600):
    """The full basket: [{name, weight, shares}] (cash lines dropped), and its date."""
    def produce():
        html = fetch(WISE_URL % code, "wise-etf-%s.html" % code)
        m = re.search(r"var CU_data = (\{.*?\});", html, re.S)
        if not m:
            return {"date": None, "rows": []}
        try:
            data = json.loads(m.group(1))
        except ValueError:
            return {"date": None, "rows": []}
        rows, date = [], None
        for r in data.get("grid_data") or []:
            nm = str(r.get("STK_NM_KOR") or "").strip()
            date = date or r.get("TRD_DT")
            if not nm or any(w in nm for w in CASH_WORDS):
                continue
            rows.append({"name": nm, "weight": num(r.get("ETF_WEIGHT")), "shares": num(r.get("AGMT_STK_CNT"))})
        return {"date": date, "rows": rows}
    return _cached("holdings-%s.json" % code, max_age_s, produce)


def basket(code):
    """{holding name: weight %} using the full basket, filled from the top 10 where weights are missing
    (overseas ETFs often publish shares but not weights). Also returns the coverage in %."""
    a = analysis(code)
    full = holdings(code)["rows"]
    top = {t["name"]: t["weight"] for t in a["top10"] if not t["cash"]}
    out = {}
    for r in full:
        w = r["weight"] if r["weight"] is not None else top.get(r["name"])
        if w:
            out[r["name"]] = out.get(r["name"], 0) + w
    if not out:
        out = {k: v for k, v in top.items() if v}
    return out, round(sum(out.values()), 1)


def code_of_holding(code, name):
    for t in analysis(code)["top10"]:
        if t["name"] == name:
            return t["code"]
    return ""


# ---------------------------------------------------------------- prices

def history(code, years=10):
    """{"dates": [...], "close": [...], "adj": [...], "dividends": [(date, amount)]} of daily bars."""
    def produce():
        info = {"code": code, "yahoo": code + ".KS", "market": "KOSPI", "name": ""}
        if OFFLINE:
            text = _offline("yahoo-%s-10y.json" % code)
        else:
            rng = "max" if years > 10 else "%dy" % years
            try:
                text = krx.yahoo_text(lambda host: "https://%s.finance.yahoo.com/v8/finance/chart/%s.KS?range=%s"
                                      "&interval=1d&events=div" % (host, code, rng))
            except krx.KRXError as e:
                raise ETFError("no price history for %s on Yahoo (%s)" % (code, e))
        try:
            res = krx.chart_result(text, code)
        except krx.KRXError as e:
            raise ETFError(str(e))
        q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
        adj = ((res.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
        dates, close, adjc = [], [], []
        for i, ts in enumerate(res.get("timestamp") or []):
            c = (q.get("close") or [None])[i] if i < len(q.get("close") or []) else None
            if c is None:
                continue
            d = krx.to_kst(krx.utc_of(ts)).date().isoformat()
            a = adj[i] if i < len(adj) and adj[i] is not None else c
            if dates and dates[-1] == d:
                close[-1], adjc[-1] = float(c), float(a)
                continue
            dates.append(d)
            close.append(float(c))
            adjc.append(float(a))
        divs = sorted((krx.to_kst(krx.utc_of(int(v.get("date") or k))).date().isoformat(), float(v.get("amount") or 0))
                      for k, v in ((res.get("events") or {}).get("dividends") or {}).items())
        return {"code": code, "dates": dates, "close": close, "adj": adjc, "dividends": divs}
    h = _cached("history-%s.json" % code, 6 * 3600, produce)
    if len(h["dates"]) < 20:
        raise ETFError("only %d days of price history for %s" % (len(h["dates"]), code))
    return h


def month_ends(h, field="adj"):
    """[(YYYY-MM, last date, value)] one per calendar month."""
    out = {}
    for d, v in zip(h["dates"], h[field]):
        out[d[:7]] = (d, v)
    return [(m, d, v) for m, (d, v) in sorted(out.items())]


# ---------------------------------------------------------------- stock valuation

def stock_valuation(stock_code):
    """{per, pbr, est_per, div_yield} for one listed stock from Naver (None where missing)."""
    def produce():
        try:
            d = json.loads(fetch(STOCK_URL % stock_code, "integration-%s.json" % stock_code))
        except (ValueError, ETFError):
            return {}
        out = {}
        for it in d.get("totalInfos") or []:
            k = (str(it.get("code") or "") + "|" + str(it.get("key") or "")).lower()
            v = num(str(it.get("value") or "").replace("배", "").replace("x", ""))
            if "cnsper" in k or "추정per" in k:
                out["est_per"] = v
            elif k.startswith("per|") or "|per" in k:
                out["per"] = v
            elif k.startswith("pbr|") or "|pbr" in k:
                out["pbr"] = v
            elif "dividendyield" in k or "배당수익률" in k:
                out["div_yield"] = v
        return out
    return _cached("stock-%s.json" % stock_code, 24 * 3600, produce)


# ---------------------------------------------------------------- portfolio file

def load_portfolio(path=PORTFOLIO):
    doc = krx.read_json(path, None)
    if not doc:
        return {"positions": [], "cash": 0}
    doc.setdefault("positions", [])
    doc.setdefault("cash", 0)
    return doc


def save_portfolio(doc, path=PORTFOLIO):
    doc["updated_at"] = krx.iso_utc(krx.utc_now())
    krx.write_json(path, doc)


def eok(x):
    """Won -> '1,234억' / '12.3조'."""
    if x is None:
        return "-"
    if abs(x) >= 1e12:
        return "%.1f조" % (x / 1e12)
    return "{:,.0f}억".format(x / 1e8)


def pct(x, digits=1, sign=True):
    if x is None:
        return "-"
    fmt = ("%+." if sign else "%.") + str(digits) + "f%%"
    return fmt % x


def today_kst():
    return krx.to_kst(krx.utc_now()).date()


def years_between(a, b):
    da, db = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return (db - da).days / 365.25
