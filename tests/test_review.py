from __future__ import annotations

import unittest
from datetime import date

from analysis.market_context import build_market_context
from analysis.review import suggest_observation_status
from storage.models import MarketSnapshot, Observation


class ReviewSuggestionTests(unittest.TestCase):
    def test_suggests_hit_candidate_for_strong_related_stock(self) -> None:
        trade_date = date(2026, 6, 13)
        observation = Observation(
            trade_date=trade_date,
            report_type="pre_market",
            theme="AI",
            related_stocks=["000001"],
            hypothesis="观察 AI 是否加强。",
            validation_condition="核心票走强。",
            invalid_condition="核心票走弱。",
            priority="A",
        )
        market_context = build_market_context(
            [
                MarketSnapshot(
                    trade_date=trade_date,
                    code="000001",
                    name="核心票",
                    pct_chg=4.2,
                    amount=1_000_000_000,
                    metadata={"instrument_type": "stock", "sector": "AI"},
                )
            ],
            trade_date,
        )

        suggestion = suggest_observation_status(observation, market_context)

        self.assertEqual("hit_candidate", suggestion.status)
        self.assertIn("related_stock_strength", suggestion.rationale[0])

    def test_suggests_miss_candidate_for_weak_related_stock(self) -> None:
        trade_date = date(2026, 6, 13)
        observation = Observation(
            trade_date=trade_date,
            report_type="pre_market",
            theme="AI",
            related_stocks=["000001"],
            hypothesis="观察 AI 是否加强。",
            validation_condition="核心票走强。",
            invalid_condition="核心票走弱。",
            priority="A",
        )
        market_context = build_market_context(
            [
                MarketSnapshot(
                    trade_date=trade_date,
                    code="000001",
                    name="核心票",
                    pct_chg=-3.1,
                    amount=1_000_000_000,
                    metadata={"instrument_type": "stock", "sector": "AI"},
                )
            ],
            trade_date,
        )

        suggestion = suggest_observation_status(observation, market_context)

        self.assertEqual("miss_candidate", suggestion.status)
        self.assertIn("related_stock_weakness", suggestion.rationale[0])

    def test_keeps_pending_when_snapshot_is_missing(self) -> None:
        trade_date = date(2026, 6, 13)
        observation = Observation(
            trade_date=trade_date,
            report_type="pre_market",
            theme="AI",
            related_stocks=["000001"],
            hypothesis="观察 AI 是否加强。",
            validation_condition="核心票走强。",
            invalid_condition="核心票走弱。",
            priority="A",
        )

        suggestion = suggest_observation_status(observation, build_market_context([], trade_date))

        self.assertEqual("pending", suggestion.status)
        self.assertEqual(["related_stock_snapshot_missing"], suggestion.rationale)


if __name__ == "__main__":
    unittest.main()
