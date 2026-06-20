from __future__ import annotations

import unittest
from argparse import Namespace
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from app.config import Settings
from app.main import resolve_duplicate_observations_command
from storage.models import Observation


@contextmanager
def fake_connect(settings):
    yield object()


class FakeObservationRepository:
    listed: list[Observation] = []
    updated: list[tuple[str, str, str, str]] = []

    def __init__(self, connection) -> None:
        self.connection = connection

    def list(self, query):
        self.__class__.last_query = query
        return self.__class__.listed

    def update_status(self, observation_id: str, status: str, outcome: str = "", review_note: str = "") -> int:
        self.__class__.updated.append((observation_id, status, outcome, review_note))
        return 1


def duplicate_observations() -> list[Observation]:
    first = Observation(
        id="obs-keep",
        trade_date=date(2024, 5, 28),
        report_type="pre_market",
        theme="301099",
        related_stocks=["301099"],
        hypothesis="301099 可能受 merger_acquisition 催化，需要观察是否获得板块和量能确认。",
        validation_condition="相关板块或标的成交额放大，核心标的高开不回落，且板块有跟随。",
        invalid_condition="相关标的低开低走，板块无跟随，或成交额缩量导致催化无法延续。",
        priority="B",
    )
    second = Observation(
        id="obs-duplicate",
        trade_date=first.trade_date,
        report_type=first.report_type,
        theme=first.theme,
        related_stocks=first.related_stocks,
        hypothesis=first.hypothesis,
        validation_condition=first.validation_condition,
        invalid_condition=first.invalid_condition,
        priority=first.priority,
    )
    return [first, second]


class DuplicateObservationCliTests(unittest.TestCase):
    def tearDown(self) -> None:
        FakeObservationRepository.listed = []
        FakeObservationRepository.updated = []

    def test_resolve_duplicate_observations_dry_run_does_not_update(self) -> None:
        FakeObservationRepository.listed = duplicate_observations()
        args = Namespace(
            date="2024-05-28",
            status="pending",
            limit=300,
            keep_id="obs-keep",
            review_note="历史重复",
            apply=False,
        )

        with patch("app.main.load_settings", return_value=Settings()), patch("app.main.setup_logging"), patch(
            "storage.db.connect",
            fake_connect,
        ), patch("storage.repositories.ObservationRepository", FakeObservationRepository), patch("builtins.print") as print_mock:
            exit_code = resolve_duplicate_observations_command(args)

        self.assertEqual(0, exit_code)
        self.assertEqual(date(2024, 5, 28), FakeObservationRepository.last_query.trade_date)
        self.assertEqual("pending", FakeObservationRepository.last_query.status)
        self.assertEqual([], FakeObservationRepository.updated)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("keep=obs-keep", printed)
        self.assertIn("invalid_candidate=obs-duplicate", printed)
        self.assertIn("dry_run=true", printed)

    def test_resolve_duplicate_observations_apply_marks_duplicates_invalid(self) -> None:
        FakeObservationRepository.listed = duplicate_observations()
        args = Namespace(
            date="2024-05-28",
            status="pending",
            limit=300,
            keep_id="obs-keep",
            review_note="历史重复",
            apply=True,
        )

        with patch("app.main.load_settings", return_value=Settings()), patch("app.main.setup_logging"), patch(
            "storage.db.connect",
            fake_connect,
        ), patch("storage.repositories.ObservationRepository", FakeObservationRepository), patch("builtins.print") as print_mock:
            exit_code = resolve_duplicate_observations_command(args)

        self.assertEqual(0, exit_code)
        self.assertEqual([("obs-duplicate", "invalid", "", "历史重复")], FakeObservationRepository.updated)
        print_mock.assert_any_call("updated_observations=1")


if __name__ == "__main__":
    unittest.main()
