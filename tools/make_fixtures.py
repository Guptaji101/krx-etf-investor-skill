#!/usr/bin/env python3
"""Build tests/fixtures from raw samples saved by a live run (samples/ folder).

Naver responses are trimmed to what the tests need; Yahoo price histories are replaced by
generated ones on the same dates (a seeded random walk with quarterly dividends), so the repo
does not republish market data.

    python3 tools/make_fixtures.py SAMPLES_DIR
"""

import json
import math
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tests", "fixtures")
CODES = ["293180", "396500", "462010", "069500", "360750", "411060", "488080"]


def main(src):
    os.makedirs(OUT, exist_ok=True)
    raw = open(os.path.join(src, "etfItemList.json"), "rb").read().decode("euc-kr")
    doc = json.loads(raw)
    keep = [it for it in doc["result"]["etfItemList"]
            if it["itemcode"] in CODES or "S&P500" in it["itemname"] or "반도체TOP10" in it["itemname"]]
    doc["result"]["etfItemList"] = keep
    open(os.path.join(OUT, "etfItemList.json"), "wb").write(json.dumps(doc, ensure_ascii=False).encode("euc-kr"))
    for c in CODES:
        a = json.load(open(os.path.join(src, "etfAnalysis-%s.json" % c), encoding="utf-8"))
        json.dump(a, open(os.path.join(OUT, "etfAnalysis-%s.json" % c), "w", encoding="utf-8"), ensure_ascii=False)
        html = open(os.path.join(src, "wise-etf-%s.html" % c), encoding="utf-8").read()
        m = re.search(r"var CU_data = (\{.*?\});", html, re.S)
        cu = json.loads(m.group(1)) if m else {"grid_data": []}
        cu["grid_data"] = cu["grid_data"][:40]
        cu.pop("chart_data", None)
        open(os.path.join(OUT, "wise-etf-%s.html" % c), "w", encoding="utf-8").write(
            "<script>\nvar CU_data = %s;\n</script>\n" % json.dumps(cu, ensure_ascii=False))
        y = json.load(open(os.path.join(src, "yahoo-%s-10y.json" % c), encoding="utf-8"))
        res = y["chart"]["result"][0]
        rng = random.Random(int(c[:6], 36) % 1000)
        ts = res["timestamp"]
        p, closes = 10000.0, []
        for i in range(len(ts)):
            p *= math.exp(rng.gauss(0.0003, 0.012))
            closes.append(round(p))
        divs = {}
        adj = list(closes)
        for i in range(60, len(ts), 63):
            amt = round(closes[i] * 0.004)
            divs[str(ts[i])] = {"amount": amt, "date": ts[i]}
        factor = 1.0
        for i in range(len(ts) - 1, -1, -1):
            adj[i] = closes[i] * factor
            if str(ts[i]) in divs and i > 0:
                factor *= 1 - divs[str(ts[i])]["amount"] / closes[i - 1]
        q = {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1000] * len(ts)}
        out = {"chart": {"result": [{"meta": {"symbol": c + ".KS", "currency": "KRW"}, "timestamp": ts,
                                     "events": {"dividends": divs},
                                     "indicators": {"quote": [q], "adjclose": [{"adjclose": adj}]}}], "error": None}}
        json.dump(out, open(os.path.join(OUT, "yahoo-%s-10y.json" % c), "w"))
    stock = {"totalInfos": [{"code": "per", "key": "PER", "value": "10.0배"},
                            {"code": "cnsPer", "key": "추정PER", "value": "12.5배"},
                            {"code": "pbr", "key": "PBR", "value": "1.50배"},
                            {"code": "dividendYieldRatio", "key": "배당수익률", "value": "2.0%"}]}
    loss = {"totalInfos": [{"code": "per", "key": "PER", "value": "-5.0배"}, {"code": "pbr", "key": "PBR", "value": "0.80배"}]}
    json.dump(stock, open(os.path.join(OUT, "integration-005930.json"), "w"), ensure_ascii=False)
    json.dump(loss, open(os.path.join(OUT, "integration-000660.json"), "w"), ensure_ascii=False)
    print("fixtures written to %s" % OUT)


if __name__ == "__main__":
    main(sys.argv[1])
