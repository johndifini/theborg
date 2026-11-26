"""Tests for ai-sleeve/rebalance.py against a fixture universe with fixed caps.

Run: python3 -m unittest discover -s warren-bot-fett/ai-sleeve/tests
"""

import contextlib
import csv
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
spec = importlib.util.spec_from_file_location("rebalance", HERE.parent / "rebalance.py")
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)


def fixture_universe():
    return rb.parse_universe((FIXTURES / "universe.md").read_text())


def fixture_caps():
    return rb.load_caps_file(FIXTURES / "caps.tsv")


class ParseUniverse(unittest.TestCase):
    def test_tunables_categories_and_excludes(self):
        u = fixture_universe()
        self.assertEqual(u["basket_size"], 6)
        self.assertEqual(u["floor_pct"], 5.0)
        self.assertEqual(u["ticker_floors"], {"LOWB": 4.0})
        self.assertEqual([c["name"] for c in u["categories"]], ["giants", "mid", "power", "tiny"])
        self.assertEqual([c["min"] for c in u["categories"]], [0, 0, 2, 1])
        self.assertEqual([s["ticker"] for s in u["soft_excludes"]], ["PWRX", "FFF"])
        self.assertEqual(u["soft_excludes"][0]["note"], "excluded for the test")
        # Union of members in first-seen order, soft excludes dropped, DDD once.
        self.assertEqual(u["candidates"],
                         ["AAA", "BBB", "CCC", "DDD", "EEE", "PWR1", "PWR2", "LOWA", "LOWB"])

    def test_real_universe_parses(self):
        u = rb.parse_universe(rb.DEFAULT_UNIVERSE.read_text())
        rb.validate_universe(u)
        self.assertGreaterEqual(len(u["candidates"]), u["basket_size"])

    def test_glued_fence_halts(self):
        text = (FIXTURES / "universe.md").read_text().replace(
            "FFF       # excluded for the test\n```", "FFF       # excluded for the test```")
        with self.assertRaises(rb.Halt):
            rb.parse_universe(text)

    def test_over_constrained_category_halts(self):
        text = (FIXTURES / "universe.md").read_text().replace(
            "PWRX      # excluded", "PWR2      # gone\nPWRX      # excluded")
        u = rb.parse_universe(text)
        with self.assertRaises(rb.Halt) as cm:
            rb.validate_universe(u)
        self.assertIn("over-constrained", cm.exception.reason)

    def test_sum_of_mins_over_basket_halts(self):
        text = (FIXTURES / "universe.md").read_text().replace("basket_size: 6", "basket_size: 2")
        with self.assertRaises(rb.Halt):
            rb.validate_universe(rb.parse_universe(text))


class SelectAndWeigh(unittest.TestCase):
    def setUp(self):
        self.u = fixture_universe()
        rb.validate_universe(self.u)
        self.result = rb.build_result(self.u, fixture_caps())

    def test_selection_swaps_lowest_unprotected_names(self):
        r = self.result
        self.assertEqual(r["provisional_top_n"], ["AAA", "BBB", "CCC", "DDD", "EEE", "PWR1"])
        self.assertEqual(r["swaps"], [
            {"category": "power", "in": "PWR2", "out": "EEE"},
            {"category": "tiny", "in": "LOWB", "out": "DDD"},
        ])
        self.assertEqual([b["ticker"] for b in r["basket"]],
                         ["AAA", "BBB", "CCC", "PWR1", "PWR2", "LOWB"])
        self.assertEqual([b["ticker"] for b in r["basket"] if b["forced"]], ["PWR2", "LOWB"])

    def test_weights_follow_step5(self):
        got = {b["ticker"]: (b["weight_pct"], b["status"]) for b in self.result["basket"]}
        self.assertEqual(got, {
            "AAA": (45.87, "free"), "BBB": (28.67, "free"), "CCC": (11.47, "free"),
            "PWR1": (5.0, "floored"), "PWR2": (5.0, "floored"),
            "LOWB": (4.0, "floored"),  # ticker_floors override, not floor_pct
        })
        self.assertAlmostEqual(self.result["weight_sum"], 100.01, places=2)

    def test_categories_and_cap_units(self):
        rows = {b["ticker"]: b for b in self.result["basket"]}
        self.assertEqual(rows["LOWB"]["cap_b"], 15.0)  # 15000M
        self.assertEqual(rows["AAA"]["cap_b"], 4000.0)  # 4T
        u = self.u
        self.assertEqual(rb.categories_of(u, "DDD"), ["giants", "mid"])

    def test_no_valid_swap_halts(self):
        # Two slots, power needs both, tiny needs one: once power fills the
        # basket, every name is protected (validate_universe would catch the
        # sum of mins first; this exercises select_basket's own guard).
        text = (FIXTURES / "universe.md").read_text().replace("basket_size: 6", "basket_size: 2")
        u = rb.parse_universe(text)
        with self.assertRaises(rb.Halt) as cm:
            rb.select_basket(u, fixture_caps())
        self.assertIn("no valid swap", cm.exception.reason)
        self.assertEqual(cm.exception.details["unsatisfied"][0]["category"], "tiny")


class CapFetching(unittest.TestCase):
    def test_extractor(self):
        self.assertEqual(rb.extract_cap('x,marketCap:"5.15T",y'), "5.15T")
        self.assertEqual(rb.extract_cap('marketCap:"52.89B" marketCap:"52.89B"'), "52.89B")
        self.assertIsNone(rb.extract_cap('marketCap:"1T" marketCap:"2T"'))  # ambiguous
        self.assertIsNone(rb.extract_cap("<html>no data</html>"))
        self.assertAlmostEqual(rb.parse_cap("512.3M"), 0.5123)

    def _fake(self, pages):
        calls = []

        def fetch(url):
            calls.append(url)
            seq = pages.get(url)
            if not seq:
                return 404, ""
            return 200, f'marketCap:"{seq.pop(0)}"'
        return fetch, calls

    def test_two_passes_agree(self):
        url = "https://stockanalysis.com/stocks/aaa/"
        fetch, calls = self._fake({url: ["4.00T", "4.10T"]})
        caps, flags = rb.fetch_caps(["AAA"], fetch=fetch, pause=0)
        self.assertEqual(flags, [])
        self.assertEqual(caps["AAA"]["cap_b"], 4000.0)
        self.assertEqual(caps["AAA"]["source"], "stockanalysis.com/stocks")
        self.assertIn("fetched_at", caps["AAA"])
        self.assertEqual(len(calls), 2)

    def test_disagreement_over_10pct_flags(self):
        url = "https://stockanalysis.com/stocks/aaa/"
        fetch, _ = self._fake({url: ["100B", "117B"]})
        caps, flags = rb.fetch_caps(["AAA"], fetch=fetch, pause=0)
        self.assertEqual([f["kind"] for f in flags], ["fetches_disagree"])
        self.assertEqual([d["raw"] for d in flags[0]["detail"]], ["100B", "117B"])

    def test_etf_fallback_and_failure(self):
        etf = "https://stockanalysis.com/etf/xyz/"
        fetch, _ = self._fake({etf: ["10B", "10B"]})
        caps, flags = rb.fetch_caps(["XYZ", "NOPE"], fetch=fetch, pause=0)
        self.assertEqual(caps["XYZ"]["source"], "stockanalysis.com/etf")
        self.assertEqual([(f["ticker"], f["kind"]) for f in flags], [("NOPE", "fetch_failed")])

    def test_manual_cap_clears_flag(self):
        caps, flags = {}, [{"ticker": "NOPE", "kind": "fetch_failed", "detail": ""}]
        rb.apply_manual_caps(caps, flags, ["nope=1.2B"])
        self.assertEqual(flags, [])
        self.assertEqual(caps["NOPE"]["source"], "companiesmarketcap.com")


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = rb.main(list(args))
        return code, buf.getvalue()

    def test_writes_history_and_replays_exactly(self):
        with tempfile.TemporaryDirectory() as d:
            code, _ = self.run_cli("--universe", str(FIXTURES / "universe.md"),
                                   "--caps", str(FIXTURES / "caps.tsv"), "--write-history",
                                   "--date", "2026-12-01", "--run-type", "scheduled",
                                   "--history-dir", d)
            self.assertEqual(code, 0)
            csv_path = Path(d) / "2026-12-01-scheduled.csv"
            with csv_path.open() as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(list(rows[0]), rb.CSV_COLUMNS)
            self.assertEqual([(r["rank"], r["ticker"], r["weight_pct"], r["status"], r["forced"])
                              for r in rows][-1], ("6", "LOWB", "4.00", "floored", "true"))
            self.assertEqual(rows[0]["cap_b"], "4000.00")
            # The companion caps file replays to the same CSV.
            first = csv_path.read_text()
            with tempfile.TemporaryDirectory() as d2:
                code, _ = self.run_cli("--universe", str(FIXTURES / "universe.md"),
                                       "--caps", str(Path(d) / "2026-12-01-scheduled.caps.tsv"),
                                       "--write-history", "--date", "2026-12-01",
                                       "--run-type", "scheduled", "--history-dir", d2)
                self.assertEqual(code, 0)
                self.assertEqual((Path(d2) / "2026-12-01-scheduled.csv").read_text(), first)

    def test_halt_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            caps = Path(d) / "caps.tsv"
            caps.write_text("AAA\t4T\n")  # every other candidate missing
            code, out = self.run_cli("--universe", str(FIXTURES / "universe.md"),
                                     "--caps", str(caps), "--write-history",
                                     "--history-dir", str(Path(d) / "h"))
            self.assertEqual(code, 2)
            self.assertIn('"status": "halt"', out)
            self.assertFalse((Path(d) / "h").exists())


if __name__ == "__main__":
    unittest.main()
