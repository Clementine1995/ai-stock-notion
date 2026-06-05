from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from storage.models import RawDocument
from storage.repositories import build_content_hash


COL_CODE = "\u4ee3\u7801"
COL_NAME = "\u540d\u79f0"
COL_TITLE = "\u516c\u544a\u6807\u9898"
COL_CATEGORY = "\u516c\u544a\u7c7b\u578b"
COL_DATE = "\u516c\u544a\u65e5\u671f"
COL_URL = "\u7f51\u5740"


def collect_announcements(trade_date: date, category: str = "\u5168\u90e8") -> list[RawDocument]:
    ak = import_akshare()
    frame = ak.stock_notice_report(symbol=category, date=trade_date.strftime("%Y%m%d"))
    return [akshare_announcement_row_to_raw_document(row) for row in dataframe_to_records(frame)]


def import_akshare() -> Any:
    try:
        import akshare as ak
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency: run `pip install -r requirements.txt` first.") from exc
    return ak


def dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", False):
        return []
    return frame.to_dict("records")


def akshare_announcement_row_to_raw_document(row: dict[str, Any]) -> RawDocument:
    stock_code = str(row.get(COL_CODE) or "").strip()
    stock_name = str(row.get(COL_NAME) or "").strip()
    title = str(row.get(COL_TITLE) or "").strip()
    category = str(row.get(COL_CATEGORY) or "").strip()
    url = str(row.get(COL_URL) or "").strip()
    publish_date = parse_date(row.get(COL_DATE))
    publish_time = datetime.combine(publish_date, time.min) if publish_date else None
    content = build_announcement_content(title, stock_code, stock_name, category, url)
    content_hash = build_content_hash("akshare", title, publish_time, f"{stock_code}|{url}")

    return RawDocument(
        source="akshare",
        doc_type="announcement",
        title=title,
        content=content,
        url=url,
        publish_time=publish_time,
        stock_code=stock_code,
        stock_name=stock_name,
        external_id=f"announcement:{url or content_hash}",
        metadata={
            "announcement_category": category,
            "data_provider": "eastmoney.stock_notice_report",
        },
        content_hash=content_hash,
    )


def build_announcement_content(title: str, stock_code: str, stock_name: str, category: str, url: str) -> str:
    lines: list[str] = []
    if title:
        lines.append(f"Title: {title}")
    stock_value = " ".join(value for value in (stock_code, stock_name) if value)
    if stock_value:
        lines.append(f"Stock: {stock_value}")
    if category:
        lines.append(f"Category: {category}")
    if url:
        lines.append(f"URL: {url}")
    return "\n".join(lines)


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()
