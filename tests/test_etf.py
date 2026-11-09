"""Offline tests on fixtures cut from real Naver responses (prices are generated)."""

import contextlib
import glob
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(ROOT, "common"))
import etf  # noqa: E402
import krx  # noqa: E402


def load(skill, name):
    spec = importlib.util.spec_from_file_location("%s_%s" % (skill.replace("-", "_"), name),
                                                  os.path.join(ROOT, skill, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.etf.OFFLINE = FIX
    return mod


def run(mod, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main(["--offline", FIX] + argv)
    return rc, buf.getvalue()


class Workdir(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        etf.OFFLINE = FIX

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp)


class Data(Workdir):
    def test_list_and_resolve(self):
        lst = etf.etf_list()
        self.assertTrue(any(e["code"] == "293180" for e in lst))
        self.assertEqual(etf.resolve("HANARO 200", lst)["code"], "293180")
        self.assertEqual(etf.resolve("A293180", lst)["code"], "293180")
        self.assertEqual(etf.resolve("TIGER 반도체TOP10", lst)["code"], "396500")
        with self.assertRaises(etf.ETFError):
            etf.resolve("반도체TOP10", lst)          # several match: ask for the code
        with self.assertRaises(etf.ETFError):
            etf.resolve("nothing like this", lst)

    def test_analysis(self):
        a = etf.analysis("293180")
        self.assertEqual(a["fee_pct"], 0.036)
        self.assertEqual(a["tax_code"], "1")
        self.assertEqual(a["top10"][0]["name"], "삼성전자")
        self.assertAlmostEqual(a["top10"][0]["weight"], 33.02)
        self.assertEqual(a["sectors"][0][0], "IT")
        lev = etf.analysis("488080")
        self.assertEqual(lev["tax_code"], "2")
        self.assertTrue(etf.is_leveraged("TIGER 반도체TOP10레버리지"))

    def test_basket_and_cash(self):
        b, cov = etf.basket("293180")
        self.assertIn("삼성전자", b)
        self.assertFalse(any("현금" in n for n in b))
        gold, _ = etf.basket("411060")
        self.assertFalse(any("현금" in n for n in gold))
        us, cov = etf.basket("360750")
        self.assertEqual(us, {})                   # overseas: weights not published

    def test_history(self):
        h = etf.history("293180")
        self.assertEqual(len(h["dates"]), len(h["adj"]))
        self.assertTrue(h["dividends"])
        self.assertLess(h["adj"][0], h["close"][0])  # earlier prices adjusted down for later payouts
        self.assertEqual(h["adj"][-1], h["close"][-1])

    def test_num(self):
        self.assertEqual(etf.num("3,119억"), 3119)
        self.assertEqual(etf.num("33.02%"), 33.02)
        self.assertIsNone(etf.num("-"))


class Profile(Workdir):
    def test_show(self):
        m = load("etf-profile", "profile")
        rc, out = run(m, ["show", "293180", "488080"])
        self.assertEqual(rc, 0)
        self.assertIn("0.036% a year", out)
        self.assertIn("no tax on the gain", out)
        self.assertIn("the top two holdings are", out)
        self.assertIn("leveraged / inverse ETF", out)

    def test_overlap(self):
        m = load("etf-profile", "profile")
        pairs = m.overlap(["293180", "396500", "462010"], etf.etf_list())
        hs = pairs[0]
        self.assertGreater(hs["weighted"], 40)
        self.assertEqual(hs["shared"][0][0], "삼성전자")
        self.assertLess(pairs[2]["weighted"], 1)

    def test_search(self):
        m = load("etf-profile", "profile")
        rc, out = run(m, ["search", "S&P500"])
        self.assertIn("360750", out)


class Portfolio(Workdir):
    def test_flow(self):
        m = load("etf-portfolio", "portfolio")
        self.assertEqual(run(m, ["add", "293180", "--qty", "8", "--avg", "97162"])[0], 0)
        self.assertEqual(run(m, ["add", "396500", "--qty", "10", "--avg", "34592"])[0], 0)
        run(m, ["buy", "293180", "--qty", "2", "--price", "80000"])
        pf = etf.load_portfolio()
        p = [x for x in pf["positions"] if x["code"] == "293180"][0]
        self.assertEqual(p["qty"], 10)
        self.assertAlmostEqual(p["avg"], (97162 * 8 + 80000 * 2) / 10)
        rc, out = run(m, ["show"])
        self.assertEqual(rc, 0)
        self.assertIn("Looking through the ETFs", out)
        self.assertIn("삼성전자", out)
        self.assertIn("over 20%", out)
        rc, _ = run(m, ["sell", "396500", "--qty", "99", "--price", "1"])
        self.assertEqual(rc, 1)                     # cannot sell more than held

    def test_look_through_scale(self):
        m = load("etf-portfolio", "portfolio")
        pf = {"positions": [{"code": "293180", "qty": 10, "avg": 1}], "cash": 0}
        rows, total, _ = m.evaluate(pf, etf.etf_list())
        stocks, sectors, _, _ = m.look_through(rows, total)
        a = etf.analysis("293180")
        self.assertAlmostEqual(stocks["삼성전자"], a["top10"][0]["weight"], places=1)
        self.assertAlmostEqual(sum(sectors.values()), sum(w for _, w in a["sectors"]), places=1)


class History(Workdir):
    def test_xirr(self):
        h = load("etf-history", "history")
        r = h.xirr([("2020-01-01", -100.0), ("2021-01-01", 110.0)])
        self.assertAlmostEqual(r, 10.0, delta=0.1)

    def test_dca_and_compare(self):
        h = load("etf-history", "history")
        rc, out = run(h, ["dca", "293180", "--monthly", "100000", "--years", "3"])
        self.assertEqual(rc, 0)
        self.assertIn("purchases", out)
        rc, out = run(h, ["compare", "293180", "--amount", "1000000", "--years", "3", "--split", "6"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.count("worth"), 3)
        rc, out = run(h, ["dca", "069500:60", "360750:40", "--monthly", "300000", "--years", "3"])
        self.assertEqual(rc, 0)

    def test_simulate_invests_all(self):
        h = load("etf-history", "history")
        mix = [({"code": "X"}, 100.0)]
        dates = ["2020-01-02", "2020-02-03", "2020-03-02"]
        prices = [[1000.0, 1000.0, 1000.0]]
        path, flows, shares, cash = h.simulate(mix, prices, dates, dates, {d: 10000.0 for d in dates})
        self.assertEqual(shares[0], 29)              # 10,000 / 1,000.15 = 9 a month, the rest carries
        self.assertLess(cash, 1000.15)

    def test_rolling_and_drawdowns(self):
        h = load("etf-history", "history")
        self.assertEqual(run(h, ["rolling", "069500", "--years", "3"])[0], 0)
        rc, out = run(h, ["drawdowns", "293180", "--min", "5"])
        self.assertEqual(rc, 0)
        self.assertIn("Falls of 5%", out)


class Valuation(Workdir):
    def test_per_combines_as_earnings_yield(self):
        v = load("etf-valuation", "valuation")
        lt = v.look_through("293180")
        rows = {r["code"]: r for r in lt["rows"]}
        w1, w2 = rows["005930"]["weight"], rows["000660"]["weight"]
        expect = (w1 + w2) / (w1 / 10.0 + 0.0)     # the loss-maker adds weight but no earnings
        self.assertAlmostEqual(lt["per"], expect, places=6)
        self.assertGreater(lt["per"], 10.0)

    def test_report(self):
        v = load("etf-valuation", "valuation")
        rc, out = run(v, ["293180", "360750"])
        self.assertEqual(rc, 0)
        self.assertIn("vs its 200-day average", out)
        self.assertIn("not for overseas equity", out)


class Plan(Workdir):
    def test_needed_return(self):
        p = load("etf-plan", "plan")
        self.assertEqual(p.needed_return(0, 100000, 1000000, 1), 0.0)
        r = p.needed_return(1000000, 0, 1100000, 1)
        self.assertAlmostEqual(r, 10.0, delta=0.05)
        self.assertIsNone(p.needed_return(0, 1, 1e12, 1))

    def test_flow(self):
        p = load("etf-plan", "plan")
        port = load("etf-portfolio", "portfolio")
        run(port, ["add", "293180", "--qty", "8", "--avg", "97162"])
        self.assertEqual(run(p, ["goal", "--target", "20000000", "--years", "3", "--monthly", "300000",
                                 "--risk", "low"])[0], 0)
        self.assertEqual(run(p, ["mix", "069500=60", "360750=40"])[0], 0)
        self.assertEqual(run(p, ["mix", "069500=60", "360750=30"])[0], 1)     # must add to 100
        run(p, ["rules", "--max-stock", "20", "--max-sector", "40", "--no-leverage"])
        rc, out = run(p, ["show"])
        self.assertEqual(rc, 0)
        for s in ("1. Goal", "2. Track record", "3. Deepest fall", "4. Your rules", "5. Drift", "6. This month"):
            self.assertIn(s, out)
        self.assertIn("not in your plan", out)
        rc, out = run(p, ["--json", "next", "--budget", "200000"])
        doc = json.loads(out)
        spent = 200000 - doc["left"]
        self.assertGreater(spent, 0)
        self.assertLessEqual(spent, 200000)


class Repo(unittest.TestCase):
    def test_copies_in_sync(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sync.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_skill_files(self):
        skills = sorted(os.path.basename(d) for d in glob.glob(os.path.join(ROOT, "etf-*")))
        self.assertEqual(skills, ["etf-history", "etf-plan", "etf-portfolio", "etf-profile", "etf-valuation"])
        for s in skills:
            with open(os.path.join(ROOT, s, "SKILL.md"), encoding="utf-8") as fh:
                text = fh.read()
            m = re.match(r"^---\nname: (\S+)\ndescription: >-\n(.+?)\n---\n", text, re.S)
            self.assertTrue(m, s)
            self.assertEqual(m.group(1), s)
            self.assertLess(len(" ".join(m.group(2).split())), 1024)
            for script in re.findall(r"CLAUDE_SKILL_DIR\}/(\w+\.py)", text):
                self.assertTrue(os.path.exists(os.path.join(ROOT, s, script)))
            self.assertIn("한국어 요약", text)


if __name__ == "__main__":
    unittest.main()
