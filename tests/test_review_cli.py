from __future__ import annotations

import unittest
from argparse import Namespace
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from app.config import Settings
from app.main import review_command
from storage.models import MarketSnapshot, Observation


@contextmanager
def fake_connect(settings):
    yield object()


class FakeObservationRepository:
    listed: list[Observation] = []
    updated: tuple[str, str, str, str] | None = None

    def __init__(self, connection) -> None:
        self.connection = connection

    def list(self, query):
        self.__class__.last_query = query
        return self.__class__.listed

    def update_status(self, observation_id: str, status: str, outcome: str = "", review_note: str = "") -> int:
        self.__class__.updated = (observation_id, status, outcome, review_note)
        return 1


class FakeMarketSnapshotRepository:
    listed: list[MarketSnapshot] = []

    def __init__(self, connection) -> None:
        self.connection = connection

    def list(self, query):
        self.__class__.last_query = query
        return self.__class__.listed


class ReviewCliTests(unittest.TestCase):
    def tearDown(self) -> None:
        FakeObservationRepository.listed = []
        FakeObservationRepository.updated = None
        FakeMarketSnapshotRepository.listed = []

    def test_review_lists_pending_observations_for_date(self) -> None:
        FakeObservationRepository.listed = [
            Observation(
                id="obs-1",
                trade_date=date(2026, 6, 13),
                report_type="pre_market",
                theme="AI",
                related_stocks=["000001"],
                hypothesis="观察 AI 是否继续加强。",
                validation_condition="板块放量。",
                invalid_condition="板块无跟随。",
                priority="A",
            )
        ]
        FakeMarketSnapshotRepository.listed = [
            MarketSnapshot(
                trade_date=date(2026, 6, 13),
                code="000001",
                name="核心票",
                pct_chg=4.2,
                amount=1_000_000_000,
                metadata={"instrument_type": "stock", "sector": "AI"},
            )
        ]
        args = Namespace(date="2026-06-13", id="", status=None, outcome="", review_note="", limit=20)

        with patch("app.main.load_settings", return_value=Settings()), patch("app.main.setup_logging"), patch(
            "storage.db.connect",
            fake_connect,
        ), patch("storage.repositories.ObservationRepository", FakeObservationRepository), patch(
            "storage.repositories.MarketSnapshotRepository",
            FakeMarketSnapshotRepository,
        ), patch("builtins.print") as print_mock:
            exit_code = review_command(args)

        self.assertEqual(0, exit_code)
        self.assertEqual(date(2026, 6, 13), FakeObservationRepository.last_query.trade_date)
        self.assertEqual("pending", FakeObservationRepository.last_query.status)
        self.assertEqual(date(2026, 6, 13), FakeMarketSnapshotRepository.last_query.trade_date)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("obs-1", printed)
        self.assertIn("hypothesis=观察 AI 是否继续加强。", printed)
        self.assertIn("suggestion=hit_candidate", printed)

    def test_review_updates_observation_when_id_is_provided(self) -> None:
        args = Namespace(date="2026-06-13", id="obs-1", status="hit", outcome="成立", review_note="板块放量", limit=20)

        with patch("app.main.load_settings", return_value=Settings()), patch("app.main.setup_logging"), patch(
            "storage.db.connect",
            fake_connect,
        ), patch("storage.repositories.ObservationRepository", FakeObservationRepository), patch("builtins.print") as print_mock:
            exit_code = review_command(args)

        self.assertEqual(0, exit_code)
        self.assertEqual(("obs-1", "hit", "成立", "板块放量"), FakeObservationRepository.updated)
        print_mock.assert_called_with("updated_observations=1")

    def test_review_requires_status_when_id_is_provided(self) -> None:
        args = Namespace(date="2026-06-13", id="obs-1", status=None, outcome="", review_note="", limit=20)

        with patch("app.main.load_settings", return_value=Settings()), patch("app.main.setup_logging"), patch(
            "storage.db.connect",
            fake_connect,
        ), patch("storage.repositories.ObservationRepository", FakeObservationRepository):
            with self.assertRaises(ValueError):
                review_command(args)


if __name__ == "__main__":
    unittest.main()
