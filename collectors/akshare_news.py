from __future__ import annotations

from datetime import date, datetime, time
from hashlib import sha256
from typing import Any

from storage.models import RawDocument
from storage.repositories import build_content_hash


COL_DATE = "date"
COL_TITLE = "title"
COL_CONTENT = "content"
COL_KEYWORD = "\u5173\u952e\u8bcd"
COL_NEWS_TITLE = "\u65b0\u95fb\u6807\u9898"
COL_NEWS_CONTENT = "\u65b0\u95fb\u5185\u5bb9"
COL_PUBLISH_TIME = "\u53d1\u5e03\u65f6\u95f4"
COL_MEDIA = "\u6587\u7ae0\u6765\u6e90"
COL_LINK = "\u65b0\u95fb\u94fe\u63a5"


def collect_cctv_news(news_date: date) -> list[RawDocument]:
    ak = import_akshare()
    frame = ak.news_cctv(date=news_date.strftime("%Y%m%d"))
    return [akshare_cctv_news_row_to_raw_document(row) for row in dataframe_to_records(frame)]


def collect_stock_news(stock_codes: list[str], min_publish_date: date | None = None) -> list[RawDocument]:
    ak = import_akshare()
    documents: list[RawDocument] = []
    for stock_code in dict.fromkeys(stock_codes):
        frame = ak.stock_news_em(symbol=stock_code)
        for row in dataframe_to_records(frame):
            document = akshare_stock_news_row_to_raw_document(row, fallback_stock_code=stock_code)
            if min_publish_date is None or not document.publish_time or document.publish_time.date() >= min_publish_date:
                documents.append(document)
    return documents


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


def akshare_cctv_news_row_to_raw_document(row: dict[str, Any]) -> RawDocument:
    news_date = parse_date(row.get(COL_DATE))
    publish_time = datetime.combine(news_date, time.min) if news_date else None
    title = normalize_text(row.get(COL_TITLE))
    content = normalize_text(row.get(COL_CONTENT))
    content_hash = build_content_hash("akshare_cctv", title, publish_time, content[:120])
    external_key = stable_key("akshare_cctv", news_date.isoformat() if news_date else "", title)

    return RawDocument(
        source="akshare_cctv",
        doc_type="news",
        title=title,
        content=content or title,
        publish_time=publish_time,
        external_id=f"news:cctv:{external_key}",
        metadata={
            "news_source": "cctv",
            "data_provider": "akshare.news_cctv",
            "freshness_tier": "daily_digest",
        },
        content_hash=content_hash,
    )


def akshare_stock_news_row_to_raw_document(row: dict[str, Any], fallback_stock_code: str) -> RawDocument:
    stock_code = normalize_text(row.get(COL_KEYWORD) or fallback_stock_code)
    title = normalize_text(row.get(COL_NEWS_TITLE))
    content = normalize_text(row.get(COL_NEWS_CONTENT))
    publish_time = parse_datetime(row.get(COL_PUBLISH_TIME))
    media = normalize_text(row.get(COL_MEDIA))
    url = normalize_text(row.get(COL_LINK))
    content_hash = build_content_hash("akshare_eastmoney", title, publish_time, f"{stock_code}|{url}")
    external_key = url or stable_key("akshare_eastmoney", stock_code, title, publish_time.isoformat() if publish_time else "")

    return RawDocument(
        source="akshare_eastmoney",
        doc_type="news",
        title=title,
        content=content or title,
        url=url,
        publish_time=publish_time,
        stock_code=stock_code,
        external_id=f"news:eastmoney-stock:{external_key}",
        metadata={
            "news_source": "eastmoney_stock",
            "media": media,
            "data_provider": "akshare.stock_news_em",
            "freshness_tier": "recent_stock_news",
        },
        content_hash=content_hash,
    )


def stable_key(*parts: str) -> str:
    return sha256("|".join(part.strip() for part in parts).encode("utf-8")).hexdigest()


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw_value = str(value)
    if len(raw_value) == 8 and raw_value.isdigit():
        return datetime.strptime(raw_value, "%Y%m%d").date()
    return datetime.fromisoformat(raw_value).date()


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.fromisoformat(str(value))
