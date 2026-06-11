from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from storage.models import MarketSnapshot


ONE_TRILLION = 1_000_000_000_000
TWO_TRILLION = 2_000_000_000_000


@dataclass(frozen=True)
class MarketInstrumentSummary:
    code: str
    name: str
    pct_chg: float | None
    amount: float | None
    turnover_rate: float | None
    source: str


@dataclass(frozen=True)
class SectorHotspot:
    sector: str
    stock_count: int
    average_pct_chg: float | None
    total_amount: float


@dataclass(frozen=True)
class MarketContext:
    trade_date: date
    snapshot_count: int
    stock_count: int
    index_count: int
    observed_total_amount: float
    amount_tier: str
    indexes: list[MarketInstrumentSummary]
    strong_stocks: list[MarketInstrumentSummary]
    weak_stocks: list[MarketInstrumentSummary]
    volume_leaders: list[MarketInstrumentSummary]
    sector_hotspots: list[SectorHotspot]
    market_style: str
    sentiment_cycle: str
    evidence_gaps: list[str]


def build_market_context(snapshots: list[MarketSnapshot], trade_date: date) -> MarketContext:
    stock_snapshots = [snapshot for snapshot in snapshots if instrument_type(snapshot) == "stock"]
    index_snapshots = [snapshot for snapshot in snapshots if instrument_type(snapshot) == "index"]
    observed_total_amount = sum(snapshot.amount or 0 for snapshot in stock_snapshots)
    evidence_gaps = []
    if not stock_snapshots:
        evidence_gaps.append("missing_stock_snapshots")
    if not index_snapshots:
        evidence_gaps.append("missing_index_snapshots")
    if not build_sector_hotspots(stock_snapshots):
        evidence_gaps.append("missing_sector_mapping")

    return MarketContext(
        trade_date=trade_date,
        snapshot_count=len(snapshots),
        stock_count=len(stock_snapshots),
        index_count=len(index_snapshots),
        observed_total_amount=observed_total_amount,
        amount_tier=classify_amount_tier(observed_total_amount),
        indexes=sort_by_pct(index_snapshots, reverse=True),
        strong_stocks=sort_by_pct(stock_snapshots, reverse=True)[:10],
        weak_stocks=sort_by_pct(stock_snapshots, reverse=False)[:10],
        volume_leaders=sort_by_amount(stock_snapshots)[:10],
        sector_hotspots=build_sector_hotspots(stock_snapshots)[:10],
        market_style="unknown",
        sentiment_cycle="unknown",
        evidence_gaps=evidence_gaps,
    )


def classify_amount_tier(amount: float) -> str:
    if amount >= TWO_TRILLION:
        return "above_2t_supports_two_to_three_main_sectors"
    if amount >= ONE_TRILLION:
        return "above_1t_supports_one_main_sector"
    if amount > 0:
        return "below_1t_watch_small_caps_or_shrinking_liquidity"
    return "unknown"


def build_sector_hotspots(snapshots: list[MarketSnapshot]) -> list[SectorHotspot]:
    grouped: dict[str, list[MarketSnapshot]] = {}
    for snapshot in snapshots:
        sector = str(snapshot.metadata.get("sector") or "").strip()
        if sector:
            grouped.setdefault(sector, []).append(snapshot)

    hotspots = []
    for sector, sector_snapshots in grouped.items():
        pct_values = [snapshot.pct_chg for snapshot in sector_snapshots if snapshot.pct_chg is not None]
        average_pct_chg = sum(pct_values) / len(pct_values) if pct_values else None
        total_amount = sum(snapshot.amount or 0 for snapshot in sector_snapshots)
        hotspots.append(
            SectorHotspot(
                sector=sector,
                stock_count=len(sector_snapshots),
                average_pct_chg=average_pct_chg,
                total_amount=total_amount,
            )
        )
    return sorted(hotspots, key=lambda item: (item.average_pct_chg is not None, item.average_pct_chg or 0, item.total_amount), reverse=True)


def instrument_type(snapshot: MarketSnapshot) -> str:
    return str(snapshot.metadata.get("instrument_type") or "")


def sort_by_pct(snapshots: list[MarketSnapshot], reverse: bool) -> list[MarketInstrumentSummary]:
    return [summarize(snapshot) for snapshot in sorted(snapshots, key=lambda item: item.pct_chg if item.pct_chg is not None else -999, reverse=reverse)]


def sort_by_amount(snapshots: list[MarketSnapshot]) -> list[MarketInstrumentSummary]:
    return [summarize(snapshot) for snapshot in sorted(snapshots, key=lambda item: item.amount or 0, reverse=True)]


def summarize(snapshot: MarketSnapshot) -> MarketInstrumentSummary:
    return MarketInstrumentSummary(
        code=snapshot.code,
        name=snapshot.name,
        pct_chg=snapshot.pct_chg,
        amount=snapshot.amount,
        turnover_rate=snapshot.turnover_rate,
        source=snapshot.source,
    )
