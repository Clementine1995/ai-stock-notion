from __future__ import annotations

from datetime import date, datetime
from typing import Any

from storage.models import MarketSnapshot


def collect_stock_daily(stock_code: str, trade_date: date) -> list[MarketSnapshot]:
    return collect_stock_daily_range(stock_code, trade_date, trade_date)


def collect_stock_daily_range(stock_code: str, start_date: date, end_date: date) -> list[MarketSnapshot]:
    ak = import_akshare()
    frame, data_provider = fetch_stock_daily_frame(ak, stock_code, start_date, end_date)
    return [
        akshare_row_to_market_snapshot(row, stock_code, data_provider=data_provider)
        for row in dataframe_to_records(frame)
    ]


def collect_index_daily(index_code: str, trade_date: date) -> list[MarketSnapshot]:
    return collect_index_daily_range(index_code, trade_date, trade_date)


def collect_index_daily_range(index_code: str, start_date: date, end_date: date) -> list[MarketSnapshot]:
    ak = import_akshare()
    frame = ak.stock_zh_index_daily(symbol=normalize_index_code(index_code))
    snapshots = [
        akshare_index_row_to_market_snapshot(row, index_code)
        for row in dataframe_to_records(frame)
    ]
    return [snapshot for snapshot in snapshots if start_date <= snapshot.trade_date <= end_date]


def import_akshare() -> Any:
    try:
        import akshare as ak
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: run `pip install -r requirements.txt` first.") from exc
    return ak


def normalize_stock_code(stock_code: str) -> str:
    return stock_code.strip().upper().replace(".SH", "").replace(".SZ", "")


def normalize_prefixed_stock_code(stock_code: str) -> str:
    code = normalize_stock_code(stock_code)
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def normalize_index_code(index_code: str) -> str:
    value = index_code.strip().lower()
    if value.endswith(".sh"):
        return f"sh{value[:-3]}"
    if value.endswith(".sz"):
        return f"sz{value[:-3]}"
    if value.startswith(("sh", "sz")):
        return value
    if value.startswith(("000", "880", "999")):
        return f"sh{value}"
    return f"sz{value}"


def fetch_stock_daily_frame(ak: Any, stock_code: str, start_date: date, end_date: date) -> tuple[Any, str]:
    compact_start = start_date.strftime("%Y%m%d")
    compact_end = end_date.strftime("%Y%m%d")
    try:
        return ak.stock_zh_a_hist(
            symbol=normalize_stock_code(stock_code),
            period="daily",
            start_date=compact_start,
            end_date=compact_end,
            adjust="",
        ), "eastmoney"
    except Exception as primary_exc:
        try:
            return ak.stock_zh_a_daily(
                symbol=normalize_prefixed_stock_code(stock_code),
                start_date=compact_start,
                end_date=compact_end,
                adjust="",
            ), "sina"
        except Exception:
            raise primary_exc


def dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", False):
        return []
    return frame.to_dict("records")


def akshare_row_to_market_snapshot(row: dict[str, Any], fallback_code: str, data_provider: str = "eastmoney") -> MarketSnapshot:
    trade_date = parse_date(first_value(row, ("日期", "date")))
    code = str(first_value(row, ("股票代码", "code")) or normalize_stock_code(fallback_code)).strip()
    return MarketSnapshot(
        trade_date=trade_date,
        code=code,
        name=str(first_value(row, ("股票名称", "name")) or ""),
        open=to_float(first_value(row, ("开盘", "open"))),
        close=to_float(first_value(row, ("收盘", "close"))),
        high=to_float(first_value(row, ("最高", "high"))),
        low=to_float(first_value(row, ("最低", "low"))),
        pct_chg=to_float(first_value(row, ("涨跌幅", "pct_chg"))),
        amount=to_float(first_value(row, ("成交额", "amount"))),
        turnover_rate=to_float(first_value(row, ("换手率", "turnover_rate"))),
        source="akshare",
        metadata={
            "instrument_type": "stock",
            "data_provider": data_provider,
            "volume": to_float(first_value(row, ("成交量", "volume"))),
            "amplitude": to_float(first_value(row, ("振幅", "amplitude"))),
            "price_change": to_float(first_value(row, ("涨跌额", "price_change"))),
        },
    )


def akshare_index_row_to_market_snapshot(row: dict[str, Any], fallback_code: str) -> MarketSnapshot:
    code = normalize_index_code(fallback_code)
    return MarketSnapshot(
        trade_date=parse_date(first_value(row, ("date", "日期"))),
        code=code,
        name=code,
        open=to_float(first_value(row, ("open", "开盘"))),
        close=to_float(first_value(row, ("close", "收盘"))),
        high=to_float(first_value(row, ("high", "最高"))),
        low=to_float(first_value(row, ("low", "最低"))),
        pct_chg=to_float(first_value(row, ("pct_chg", "涨跌幅"))),
        amount=to_float(first_value(row, ("amount", "成交额"))),
        source="akshare_index",
        metadata={
            "instrument_type": "index",
            "data_provider": "akshare.stock_zh_index_daily",
            "volume": to_float(first_value(row, ("volume", "成交量"))),
        },
    )


def first_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
