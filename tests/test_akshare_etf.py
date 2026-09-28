import unittest
from datetime import date

from industry_monitor_core.akshare_etf import (
    fetch_history,
    market_observation,
    normalize_history,
)


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows
        self.attrs = {}

    def to_dict(self, orient=None):
        if orient != "records":
            raise TypeError("records required")
        return self.rows


class AkshareEtfTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "日期": "2026-09-17",
                "代码": "512580",
                "收盘": "1.234",
                "涨跌幅": "1.25",
                "成交量": "1000",
                "成交额": "2000",
            },
            {
                "日期": "2026/09/16",
                "代码": "512580",
                "收盘": "1.219",
                "涨跌幅": "-0.40",
                "成交量": "900",
                "成交额": "1800",
            },
        ]

    def test_normalizes_and_sorts(self):
        points = normalize_history(FakeFrame(self.rows), "512580", date(2026, 9, 17))
        self.assertEqual(points[0]["date"], "2026-09-17")
        self.assertEqual(points[0]["close"], "1.234")
        self.assertEqual(points[1]["change_pct"], "-0.40")

    def test_rejects_wrong_symbol_future_date_and_conflict(self):
        with self.assertRaises(ValueError):
            normalize_history([dict(self.rows[0], 代码="510360")], "512580", date(2026, 9, 17))
        with self.assertRaises(ValueError):
            normalize_history([dict(self.rows[0], 日期="2026-09-18")], "512580", date(2026, 9, 17))
        with self.assertRaises(ValueError):
            normalize_history(self.rows + [dict(self.rows[0], 收盘="1.235")], "512580", date(2026, 9, 17))

    def test_keeps_zero_and_distinguishes_weekend(self):
        result = market_observation({"code": "512580"}, FakeFrame(self.rows), "2026-09-19T09:00:00+08:00")
        self.assertEqual(result["status"], "weekend_closed")
        self.assertEqual(result["values"]["close"], "1.234")
        self.assertEqual(result["values"]["volume"], "1000")

    def test_normalizes_sina_shape_and_derives_daily_change(self):
        frame = FakeFrame([
            {"date": "2026-09-25", "close": "1.25", "volume": "100", "amount": "200"},
            {"date": "2026-09-24", "close": "1.20", "volume": "90", "amount": "180"},
        ])
        result = market_observation(
            {"code": "512580"},
            frame,
            "2026-09-25T09:00:00+08:00",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["values"]["change_1d_pct"], "4.17")
        self.assertEqual(result["source_url"], "https://quote.eastmoney.com/")

    def test_fetch_history_falls_back_to_sina(self):
        class FakeAkshare:
            def fund_etf_hist_em(self, **kwargs):
                raise OSError("Eastmoney unavailable")

            def fund_etf_hist_sina(self, **kwargs):
                self.symbol = kwargs["symbol"]
                return FakeFrame([
                    {"date": "2026-09-25", "close": "1.25", "volume": "100", "amount": "200"},
                ])

        module = FakeAkshare()
        frame = fetch_history(
            {"code": "512580"},
            "2026-09-25T09:00:00+08:00",
            ak_module=module,
        )
        self.assertEqual(module.symbol, "sh512580")
        self.assertEqual(
            frame.attrs["source_url"],
            "https://finance.sina.com.cn/fund/quotes/512580/bc.shtml",
        )
        self.assertEqual(normalize_history(frame, "512580", date(2026, 9, 25))[0]["close"], "1.25")
