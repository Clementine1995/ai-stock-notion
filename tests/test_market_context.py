from __future__ import annotations

import unittest
from datetime import date

from analysis.market_context import build_market_context, classify_amount_tier
from storage.models import MarketSnapshot


class MarketContextTests(unittest.TestCase):
    def test_classify_amount_tier_uses_stock_review_thresholds(self) -> None:
        self.assertEqual("unknown", classify_amount_tier(0))
        self.assertEqual("below_1t_watch_small_caps_or_shrinking_liquidity", classify_amount_tier(999_999_999_999))
        self.assertEqual("above_1t_supports_one_main_sector", classify_amount_tier(1_000_000_000_000))
        self.assertEqual("above_2t_supports_two_to_three_main_sectors", classify_amount_tier(2_000_000_000_000))

    def test_build_market_context_ranks_strength_volume_and_sector_hotspots(self) -> None:
        trade_date = date(2026, 6, 11)
        snapshots = [
            MarketSnapshot(
                trade_date=trade_date,
                code="sh000001",
                name="上证指数",
                pct_chg=0.5,
                amount=500_000_000_000,
                source="akshare_index",
                metadata={"instrument_type": "index"},
            ),
            MarketSnapshot(
                trade_date=trade_date,
                code="000001",
                name="强势股",
                pct_chg=6.0,
                amount=700_000_000_000,
                turnover_rate=8.0,
                source="akshare",
                metadata={"instrument_type": "stock", "sector": "AI"},
            ),
            MarketSnapshot(
                trade_date=trade_date,
                code="000002",
                name="弱势股",
                pct_chg=-3.0,
                amount=400_000_000_000,
                turnover_rate=3.0,
                source="akshare",
                metadata={"instrument_type": "stock", "sector": "地产"},
            ),
            MarketSnapshot(
                trade_date=trade_date,
                code="000003",
                name="跟随股",
                pct_chg=2.0,
                amount=100_000_000_000,
                source="akshare",
                metadata={"instrument_type": "stock", "sector": "AI"},
            ),
        ]

        context = build_market_context(snapshots, trade_date)

        self.assertEqual(4, context.snapshot_count)
        self.assertEqual(3, context.stock_count)
        self.assertEqual(1, context.index_count)
        self.assertEqual("above_1t_supports_one_main_sector", context.amount_tier)
        self.assertEqual("000001", context.strong_stocks[0].code)
        self.assertEqual("000002", context.weak_stocks[0].code)
        self.assertEqual("000001", context.volume_leaders[0].code)
        self.assertEqual("AI", context.sector_hotspots[0].sector)
        self.assertEqual(2, context.sector_hotspots[0].stock_count)
        self.assertEqual("unknown", context.market_style)
        self.assertEqual("unknown", context.sentiment_cycle)
        self.assertNotIn("missing_sector_mapping", context.evidence_gaps)


if __name__ == "__main__":
    unittest.main()
