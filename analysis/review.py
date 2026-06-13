from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from analysis.market_context import MarketContext, MarketInstrumentSummary
from storage.models import Observation


@dataclass(frozen=True)
class ReviewSuggestion:
    status: str
    rationale: list[str]


STALE_PENDING_DAYS = 5


def suggest_observation_status(
    observation: Observation,
    market_context: MarketContext,
    review_date: date | None = None,
    stale_days: int = STALE_PENDING_DAYS,
) -> ReviewSuggestion:
    active_review_date = review_date or market_context.trade_date
    age_days = (active_review_date - observation.trade_date).days
    if observation.status == "pending" and age_days >= stale_days:
        return ReviewSuggestion(status="stale_pending", rationale=[f"age_days={age_days}", f"stale_days={stale_days}"])

    stock_summaries = find_related_stock_summaries(observation, market_context)
    sector_hotspot = next((item for item in market_context.sector_hotspots if item.sector == observation.theme), None)

    if any(is_strong_stock(item) for item in stock_summaries):
        return ReviewSuggestion(
            status="hit_candidate",
            rationale=[f"related_stock_strength={format_stock(item)}" for item in stock_summaries if is_strong_stock(item)],
        )
    if sector_hotspot is not None and (sector_hotspot.average_pct_chg or 0) >= 1.5 and sector_hotspot.total_amount > 0:
        return ReviewSuggestion(
            status="hit_candidate",
            rationale=[
                f"sector_strength={sector_hotspot.sector}",
                f"avg_pct={sector_hotspot.average_pct_chg:.2f}" if sector_hotspot.average_pct_chg is not None else "avg_pct=n/a",
            ],
        )
    if stock_summaries and all(is_weak_stock(item) for item in stock_summaries):
        return ReviewSuggestion(
            status="miss_candidate",
            rationale=[f"related_stock_weakness={format_stock(item)}" for item in stock_summaries],
        )
    if observation.related_stocks and not stock_summaries:
        return ReviewSuggestion(status="pending", rationale=["related_stock_snapshot_missing"])
    if market_context.evidence_gaps:
        return ReviewSuggestion(status="pending", rationale=["evidence_gaps=" + ",".join(market_context.evidence_gaps)])
    return ReviewSuggestion(status="pending", rationale=["no_clear_hit_or_miss_signal"])


def find_related_stock_summaries(observation: Observation, market_context: MarketContext) -> list[MarketInstrumentSummary]:
    summaries = {
        item.code: item
        for item in [
            *market_context.strong_stocks,
            *market_context.weak_stocks,
            *market_context.volume_leaders,
        ]
    }
    return [summaries[code] for code in observation.related_stocks if code in summaries]


def is_strong_stock(summary: MarketInstrumentSummary) -> bool:
    return (summary.pct_chg or 0) >= 3 and (summary.amount or 0) > 0


def is_weak_stock(summary: MarketInstrumentSummary) -> bool:
    return (summary.pct_chg or 0) <= -2


def format_stock(summary: MarketInstrumentSummary) -> str:
    pct = f"{summary.pct_chg:.2f}" if summary.pct_chg is not None else "n/a"
    amount = f"{summary.amount:.0f}" if summary.amount is not None else "n/a"
    return f"{summary.code}:{summary.name}:pct={pct}:amount={amount}"
