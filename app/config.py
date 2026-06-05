from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def redact_url(value: str) -> str:
    parts = urlsplit(value)
    if not parts.password:
        return value

    username = parts.username or ""
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{username}:***@{hostname}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = ""
    openai_model: str = ""
    embedding_provider: str = "openai-compatible"
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_dimension: int = 0
    embedding_timeout: int = 60
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout: int = 60
    tushare_token: str = ""
    notion_api_key: str = ""
    notion_root_page_ids: str = ""
    database_url: str = "postgresql://stock_ai:stock_ai@localhost:5432/stock_ai"
    database_connect_timeout: int = 5
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "market_knowledge"
    qdrant_api_key: str = ""
    report_output_dir: str = "reports/output"
    skills_dir: str = "skills"
    market_stock_codes: str = ""
    market_index_codes: str = ""
    timezone: str = "Asia/Shanghai"
    log_level: str = "INFO"
    log_file: str = "logs/app.log"


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings(path: Path | None = None) -> Settings:
    env = load_dotenv(path)
    return Settings(
        openai_api_key=env.get("OPENAI_API_KEY", Settings.openai_api_key),
        openai_model=env.get("OPENAI_MODEL", Settings.openai_model),
        embedding_provider=env.get("EMBEDDING_PROVIDER") or Settings.embedding_provider,
        embedding_model=env.get("EMBEDDING_MODEL", Settings.embedding_model),
        embedding_api_key=env.get("EMBEDDING_API_KEY") or env.get("OPENAI_API_KEY") or Settings.embedding_api_key,
        embedding_base_url=env.get("EMBEDDING_BASE_URL") or Settings.embedding_base_url,
        embedding_dimension=int(env.get("EMBEDDING_DIMENSION") or Settings.embedding_dimension),
        embedding_timeout=int(env.get("EMBEDDING_TIMEOUT") or Settings.embedding_timeout),
        llm_provider=env.get("LLM_PROVIDER", Settings.llm_provider),
        llm_api_key=env.get("LLM_API_KEY") or env.get("OPENAI_API_KEY") or Settings.llm_api_key,
        llm_base_url=env.get("LLM_BASE_URL") or Settings.llm_base_url,
        llm_model=env.get("LLM_MODEL") or env.get("OPENAI_MODEL") or Settings.llm_model,
        llm_timeout=int(env.get("LLM_TIMEOUT") or Settings.llm_timeout),
        tushare_token=env.get("TUSHARE_TOKEN", Settings.tushare_token),
        notion_api_key=env.get("NOTION_API_KEY", Settings.notion_api_key),
        notion_root_page_ids=env.get("NOTION_ROOT_PAGE_IDS", Settings.notion_root_page_ids),
        database_url=env.get("DATABASE_URL", Settings.database_url),
        database_connect_timeout=int(env.get("DATABASE_CONNECT_TIMEOUT", Settings.database_connect_timeout)),
        qdrant_url=env.get("QDRANT_URL", Settings.qdrant_url),
        qdrant_collection=env.get("QDRANT_COLLECTION", Settings.qdrant_collection),
        qdrant_api_key=env.get("QDRANT_API_KEY", Settings.qdrant_api_key),
        report_output_dir=env.get("REPORT_OUTPUT_DIR", Settings.report_output_dir),
        skills_dir=env.get("SKILLS_DIR", Settings.skills_dir),
        market_stock_codes=env.get("MARKET_STOCK_CODES", Settings.market_stock_codes),
        market_index_codes=env.get("MARKET_INDEX_CODES", Settings.market_index_codes),
        timezone=env.get("TIMEZONE", Settings.timezone),
        log_level=env.get("LOG_LEVEL", Settings.log_level),
        log_file=env.get("LOG_FILE", Settings.log_file),
    )
