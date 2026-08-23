"""アプリ設定の一元管理。各モジュールは os.environ を直接読まず、ここ経由でのみ環境値を取得する。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="local", alias="ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    harness_max_retries: int = Field(default=3, alias="HARNESS_MAX_RETRIES")
    llm_daily_cost_limit_usd: float = Field(default=5.0, alias="LLM_DAILY_COST_LIMIT_USD")

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")

    google_genai_api_key: str = Field(default="", alias="GOOGLE_GENAI_API_KEY")
    google_genai_model: str = Field(default="gemini-2.5-flash", alias="GOOGLE_GENAI_MODEL")
    google_cloud_project: str = Field(default="", alias="GOOGLE_CLOUD_PROJECT")

    article_score_threshold: int = Field(
        default=27,
        alias="ARTICLE_SCORE_THRESHOLD",
        description=(
            "score_impact×score_timeliness×score_controversyの記事化しきい値の初期値"
            "（1〜125）。運用しながら調整する想定の暫定値。"
        ),
    )

    discord_webhook_url: str = Field(default="", alias="DISCORD_WEBHOOK_URL")
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")
    review_app_url: str = Field(
        default="https://usamiiyori.github.io/eduloop-ai/", alias="REVIEW_APP_URL"
    )
    contact_url: str = Field(
        default="",
        alias="CONTACT_URL",
        description="Web記事末尾の問い合わせ導線に使うURL。未設定の場合は導線を追記しない。",
    )
    note_url: str = Field(
        default="",
        alias="NOTE_URL",
        description="note有料マガジンのURL。未設定の場合はnote導線を追記しない。",
    )

    x_api_key: str = Field(default="", alias="X_API_KEY")
    x_api_secret: str = Field(default="", alias="X_API_SECRET")
    x_access_token: str = Field(default="", alias="X_ACCESS_TOKEN")
    x_access_token_secret: str = Field(default="", alias="X_ACCESS_TOKEN_SECRET")
    x_publish_mode: str = Field(default="draft", alias="X_PUBLISH_MODE")

    scraper_contact_url: str = Field(
        default="",
        alias="SCRAPER_CONTACT_URL",
        description="User-Agentに明記する連絡先。robots.txt遵守の観点から本番運用前に必ず設定する。",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
