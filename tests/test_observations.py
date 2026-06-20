from __future__ import annotations

import unittest
from datetime import date

from analysis.events import EventScore, ExtractedEvent
from analysis.observations import ObservationCandidate, build_observation_candidate
from app.main import group_duplicate_observations, merge_observation_candidates, resolve_duplicate_observation_ids
from storage.models import Observation


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

    def test_build_observation_candidate_skips_event_without_tradeable_anchor(self) -> None:
        event = ExtractedEvent(
            raw_document_id="doc-1",
            source="akshare",
            doc_type="news",
            title="泛政策新闻",
            event_type="policy_catalyst",
            impact_direction="positive",
            affected_stocks=[],
            affected_sectors=[],
            evidence=["title:泛政策新闻"],
            confidence=0.8,
        )
        score = EventScore(
            catalyst_score=4,
            freshness_score=3,
            expectation_gap_score=3,
            sector_spread_score=2,
            liquidity_score=3,
            risk_score=2,
            priority="B",
            rationale=["event_type=policy_catalyst"],
        )

        self.assertIsNone(build_observation_candidate(event, score, date(2026, 6, 11)))

    def test_build_observation_candidate_skips_generic_policy_event_without_stock(self) -> None:
        event = ExtractedEvent(
            raw_document_id="doc-1",
            source="akshare_cctv",
            doc_type="news",
            title="神舟十八号航天员乘组圆满完成第一次出舱活动",
            event_type="policy_catalyst",
            impact_direction="positive",
            affected_stocks=[],
            affected_sectors=["商业航天"],
            evidence=["title:神舟十八号航天员乘组圆满完成第一次出舱活动", "sectors:商业航天"],
            confidence=0.8,
        )
        score = EventScore(
            catalyst_score=4,
            freshness_score=3,
            expectation_gap_score=3,
            sector_spread_score=2,
            liquidity_score=2,
            risk_score=2,
            priority="B",
            rationale=["event_type=policy_catalyst"],
        )

        self.assertIsNone(build_observation_candidate(event, score, date(2026, 6, 11)))

    def test_build_observation_candidate_keeps_actionable_policy_event_without_stock(self) -> None:
        event = ExtractedEvent(
            raw_document_id="doc-1",
            source="akshare_cctv",
            doc_type="news",
            title="多部门发布支持商业航天产业发展政策",
            event_type="policy_catalyst",
            impact_direction="positive",
            affected_stocks=[],
            affected_sectors=["商业航天"],
            evidence=["title:多部门发布支持商业航天产业发展政策", "sectors:商业航天"],
            confidence=0.8,
        )
        score = EventScore(
            catalyst_score=4,
            freshness_score=3,
            expectation_gap_score=3,
            sector_spread_score=2,
            liquidity_score=2,
            risk_score=2,
            priority="B",
            rationale=["event_type=policy_catalyst"],
        )

        candidate = build_observation_candidate(event, score, date(2026, 6, 11))

        self.assertIsNotNone(candidate)
        self.assertEqual("商业航天", candidate.theme)

    def test_merge_observation_candidates_dedupes_same_trade_hypothesis(self) -> None:
        first = ObservationCandidate(
            trade_date=date(2026, 6, 11),
            report_type="pre_market",
            theme="301099",
            related_stocks=["301099"],
            hypothesis="301099 可能受 merger_acquisition 催化，需要观察是否获得板块和量能确认。",
            validation_condition="相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。",
            invalid_condition="相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。",
            priority="B",
            status="pending",
            source_event_ids=["doc-1"],
            evidence=["title:公告一"],
        )
        second = ObservationCandidate(
            trade_date=date(2026, 6, 11),
            report_type="pre_market",
            theme="301099",
            related_stocks=["301099"],
            hypothesis=first.hypothesis,
            validation_condition=first.validation_condition,
            invalid_condition=first.invalid_condition,
            priority="B",
            status="pending",
            source_event_ids=["doc-2"],
            evidence=["title:公告二", "title:公告一"],
        )

        merged = merge_observation_candidates([first, second])

        self.assertEqual(1, len(merged))
        self.assertEqual(["doc-1", "doc-2"], merged[0].source_event_ids)
        self.assertEqual(["title:公告一", "title:公告二"], merged[0].evidence)

    def test_group_duplicate_observations_finds_same_trade_hypothesis(self) -> None:
        first = Observation(
            id="obs-1",
            trade_date=date(2026, 6, 11),
            report_type="pre_market",
            theme="301099",
            related_stocks=["301099"],
            hypothesis="301099 可能受 merger_acquisition 催化，需要观察是否获得板块和量能确认。",
            validation_condition="相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。",
            invalid_condition="相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。",
            priority="B",
        )
        second = Observation(
            id="obs-2",
            trade_date=first.trade_date,
            report_type=first.report_type,
            theme=first.theme,
            related_stocks=first.related_stocks,
            hypothesis=first.hypothesis,
            validation_condition=first.validation_condition,
            invalid_condition=first.invalid_condition,
            priority=first.priority,
        )
        different = Observation(
            id="obs-3",
            trade_date=first.trade_date,
            report_type=first.report_type,
            theme="AI",
            related_stocks=["000001"],
            hypothesis="AI 加强。",
            validation_condition="放量。",
            invalid_condition="无跟随。",
            priority="A",
        )

        groups = group_duplicate_observations([first, second, different])

        self.assertEqual(1, len(groups))
        self.assertEqual(["obs-1", "obs-2"], [item.id for item in groups[0]])

    def test_resolve_duplicate_observation_ids_keeps_selected_observation(self) -> None:
        first = Observation(
            id="obs-1",
            trade_date=date(2026, 6, 11),
            report_type="pre_market",
            theme="301099",
            related_stocks=["301099"],
            hypothesis="301099 可能受 merger_acquisition 催化，需要观察是否获得板块和量能确认。",
            validation_condition="相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。",
            invalid_condition="相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。",
            priority="B",
        )
        second = Observation(
            id="obs-2",
            trade_date=first.trade_date,
            report_type=first.report_type,
            theme=first.theme,
            related_stocks=first.related_stocks,
            hypothesis=first.hypothesis,
            validation_condition=first.validation_condition,
            invalid_condition=first.invalid_condition,
            priority=first.priority,
        )

        keep, duplicate_ids = resolve_duplicate_observation_ids([first, second], "obs-2")

        self.assertEqual("obs-2", keep.id)
        self.assertEqual(["obs-1"], duplicate_ids)

    def test_resolve_duplicate_observation_ids_rejects_non_duplicate_keep_id(self) -> None:
        observation = Observation(
            id="obs-1",
            trade_date=date(2026, 6, 11),
            report_type="pre_market",
            theme="AI",
            related_stocks=["000001"],
            hypothesis="AI 加强。",
            validation_condition="放量。",
            invalid_condition="无跟随。",
            priority="A",
        )

        with self.assertRaises(ValueError):
            resolve_duplicate_observation_ids([observation], "obs-1")


if __name__ == "__main__":
    unittest.main()
