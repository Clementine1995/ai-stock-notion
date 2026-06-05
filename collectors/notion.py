from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.config import Settings
from storage.models import RawDocument
from storage.repositories import build_content_hash


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


@dataclass(frozen=True)
class NotionPageContent:
    page_id: str
    title: str
    content: str
    url: str
    last_edited_time: datetime | None


class NotionApiError(RuntimeError):
    pass


class NotionClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._get(f"/pages/{page_id}")

    def get_block_children(self, block_id: str, page_size: int = 100) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        start_cursor: str | None = None

        while True:
            path = f"/blocks/{block_id}/children?page_size={page_size}"
            if start_cursor:
                path = f"{path}&start_cursor={start_cursor}"
            payload = self._get(path)
            results.extend(payload.get("results", []))
            if not payload.get("has_more"):
                return results
            start_cursor = payload.get("next_cursor")

    def _get(self, path: str) -> dict[str, Any]:
        request = Request(
            f"{NOTION_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Notion-Version": NOTION_VERSION,
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise NotionApiError(f"Notion API request failed: {exc.code} {message}") from exc


def parse_notion_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def split_notion_page_ids(raw_value: str) -> list[str]:
    return [normalize_notion_page_id(value) for value in raw_value.split(",") if value.strip()]


def normalize_notion_page_id(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("http://") or stripped.startswith("https://"):
        path_parts = [part for part in urlparse(stripped).path.split("/") if part]
        stripped = path_parts[-1] if path_parts else stripped
    return stripped.split("-")[-1] if "-" in stripped else stripped


def rich_text_to_plain_text(items: list[dict[str, Any]]) -> str:
    return "".join(item.get("plain_text", "") for item in items)


def extract_page_title(page: dict[str, Any]) -> str:
    properties = page.get("properties", {})
    for property_value in properties.values():
        if property_value.get("type") == "title":
            title = rich_text_to_plain_text(property_value.get("title", []))
            if title:
                return title
    return "Untitled Notion page"


def extract_block_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    if not block_type:
        return ""

    value = block.get(block_type, {})
    if block_type == "child_page":
        return value.get("title", "")
    if block_type == "to_do":
        checked = "[x]" if value.get("checked") else "[ ]"
        text = rich_text_to_plain_text(value.get("rich_text", []))
        return f"{checked} {text}".strip()
    if "rich_text" in value:
        return rich_text_to_plain_text(value.get("rich_text", []))
    return ""


def fetch_page_content(client: NotionClient, page_id: str) -> NotionPageContent:
    page = client.get_page(page_id)
    lines = collect_block_lines(client, page_id)
    return NotionPageContent(
        page_id=page.get("id", page_id),
        title=extract_page_title(page),
        content="\n".join(line for line in lines if line).strip(),
        url=page.get("url", ""),
        last_edited_time=parse_notion_datetime(page.get("last_edited_time")),
    )


def collect_block_lines(client: NotionClient, block_id: str) -> list[str]:
    lines: list[str] = []
    for block in client.get_block_children(block_id):
        text = extract_block_text(block)
        if text:
            lines.append(text)
        if block.get("has_children"):
            lines.extend(collect_block_lines(client, block["id"]))
    return lines


def page_content_to_raw_document(page: NotionPageContent) -> RawDocument:
    content_hash = build_content_hash("notion", page.title, page.last_edited_time, page.page_id)
    return RawDocument(
        source="notion",
        doc_type="note",
        title=page.title,
        content=page.content,
        url=page.url,
        publish_time=page.last_edited_time,
        external_id=page.page_id,
        metadata={"page_id": page.page_id},
        content_hash=content_hash,
    )


def fetch_notion_documents(settings: Settings) -> list[RawDocument]:
    if not settings.notion_api_key:
        raise ValueError("NOTION_API_KEY is required.")
    page_ids = split_notion_page_ids(settings.notion_root_page_ids)
    if not page_ids:
        raise ValueError("NOTION_ROOT_PAGE_IDS is required.")

    client = NotionClient(settings.notion_api_key)
    return [page_content_to_raw_document(fetch_page_content(client, page_id)) for page_id in page_ids]
