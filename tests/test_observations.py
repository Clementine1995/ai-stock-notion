from __future__ import annotations

import unittest
from datetime import date

from analysis.events import EventScore, ExtractedEvent
from analysis.observations import build_observation_candidate


class ObservationCandidateTests(unittest.TestCase):
    def test_build_observation_candidate_from_priority_event(self) -> None:
        event = ExtractedEvent(
            raw_document_id="doc-1",
            source="akshare",
            doc_type="announcement",
            title="签订重大合同",
            event_type="major_contract",
            impact_direction="positive",
            affected_stocks=["000001"],
            affected_sectors=["AI"],
            evidence=["title:签订重大合同", "sectors:AI"],
            confidence=0.9,
        )
        score = EventScore(
            catalyst_score=4,
            freshness_score=3,
            expectation_gap_score=4,
            sector_spread_score=4,
            liquidity_score=4,
            risk_score=2,
            priority="A",
            rationale=["amount_tier=above_1t_supports_one_main_sector"],
        )

        candidate = build_observation_candidate(event, score, date(2026, 6, 11), report_type="pre_market")

        self.assertIsNotNone(candidate)
        self.assertEqual("2026-06-11", candidate.to_dict()["trade_date"])
        self.assertEqual("pre_market", candidate.report_type)
        self.assertEqual("AI", candidate.theme)
        self.assertEqual(["000001"], candidate.related_stocks)
        self.assertEqual("A", candidate.priority)
        self.assertEqual("pending", candidate.status)
        self.assertEqual(["doc-1"], candidate.source_event_ids)
        self.assertIn("板块和量能确认", candidate.hypothesis)
        self.assertIn("成交额放大", candidate.validation_condition)
        self.assertIn("板块无跟随", candidate.invalid_condition)
        self.assertIn("amount_tier=above_1t_supports_one_main_sector", candidate.evidence)

    def test_build_observation_candidate_skips_c_priority(self) -> None:
        event = ExtractedEvent(
            raw_document_id="doc-1",
            source="akshare",
            doc_type="announcement",
            title="股东拟减持",
            event_type="shareholder_reduction",
            impact_direction="negative",
            affected_stocks=["000001"],
            affected_sectors=[],
            evidence=["title:股东拟减持"],
            confidence=0.8,
        )
        score = EventScore(
            catalyst_score=1,
            freshness_score=3,
            expectation_gap_score=1,
            sector_spread_score=2,
            liquidity_score=3,
            risk_score=5,
            priority="C",
            rationale=["event_type=shareholder_reduction"],
        )

        self.assertIsNone(build_observation_candidate(event, score, date(2026, 6, 11)))


if __name__ == "__main__":
    unittest.main()
