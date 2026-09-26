import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from industry_monitor_core.akshare_etf import AkshareFetchError
from industry_monitor_core.observations import collect_akshare_etfs
from industry_monitor_core.public import public_observation
from industry_monitor_core.registry import load_market_registry


class Frame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient=None):
        if orient != "records":
            raise TypeError("records required")
        return self.rows


class MarketObservationTests(unittest.TestCase):
    def setUp(self):
        self.item = {
            "id": "etf-sample", "code": "512480", "name": "样本 ETF",
            "theme": "样本主题", "benchmark": False,
        }
        self.config = {
            "market_adapters": {"akshare-etf": {
                "enabled": True, "source_url": "https://quote.eastmoney.com/",
            }},
            "etfs": [self.item],
        }
        self.rows = [{
            "日期": "2026-09-25", "代码": "512480", "收盘": "1.25",
            "涨跌幅": "0.50", "成交量": "100", "成交额": "200",
        }]

    def test_collect_archives_private_raw_and_public_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            db = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
            result = collect_akshare_etfs(
                self.config, data, db, "run-1", "2026-09-25T09:00:00+08:00",
                fetcher=lambda item, checked_at: Frame(self.rows),
                sleep=lambda _: None, min_interval=0,
            )[0]
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["values"]["close"], "1.25")
            self.assertEqual(len(list((data / "indicator-archive").glob("*/*.json"))), 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM indicator_snapshots").fetchone()[0], 1)
            public = public_observation(result)
            encoded = json.dumps(public, ensure_ascii=False)
            for private in ("_raw_paths", "_fetch_status", "_windows", "indicator-archive"):
                self.assertNotIn(private, encoded)
            db.close()

    def test_registry_rejects_foreign_domain_and_invalid_watchlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "market.json"
            value = {
                "schema_version": 1, "domain": "ai-computer",
                "market_adapters": {"akshare-etf": {
                    "enabled": True, "review_status": "sample_only",
                    "package": "akshare", "function": "fund_etf_hist_em",
                    "source_url": "https://quote.eastmoney.com/",
                }},
                "etfs": [
                    {**self.item, "benchmark": False},
                    {"id": "benchmark", "code": "510300", "name": "宽基",
                     "theme": "宽基参照", "benchmark": True},
                ],
            }
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(load_market_registry(path, "ai-computer")["domain"], "ai-computer")
            with self.assertRaises(ValueError):
                load_market_registry(path, "energy-saving")
            value["etfs"][1]["code"] = "512480"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_market_registry(path, "ai-computer")

    def test_transient_fetch_failure_is_retried_without_fabricating_data(self):
        calls = []

        def flaky_fetcher(item, checked_at):
            calls.append(item["code"])
            if len(calls) == 1:
                raise AkshareFetchError("temporary upstream failure")
            return Frame(self.rows)

        with tempfile.TemporaryDirectory() as directory:
            db = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
            result = collect_akshare_etfs(
                self.config, Path(directory), db, "run-retry",
                "2026-09-25T09:00:00+08:00",
                fetcher=flaky_fetcher, sleep=lambda _: None,
                min_interval=0, fetch_attempts=2,
            )[0]
            self.assertEqual(calls, ["512480", "512480"])
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["values"]["close"], "1.25")
            db.close()


if __name__ == "__main__":
    unittest.main()
