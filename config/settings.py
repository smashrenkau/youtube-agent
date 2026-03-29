from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic
    anthropic_api_key: SecretStr
    anthropic_model: str = "claude-sonnet-4-6"

    # Notion（未使用・互換性のため残存）
    notion_api_key: SecretStr = SecretStr("")
    notion_database_id: str = ""
    notion_log_database_id: str = ""
    notion_content_page_id: str = ""   # コンテンツフォルダ管理ページ
    notion_renkau_page_id: str = ""    # Renkauフォルダページ（生成物保存先）
    notion_renkau_long_page_id: str = ""   # long動画フォルダページ
    notion_renkau_short_page_id: str = ""  # short動画フォルダページ

    # TTS
    tts_provider: Literal["elevenlabs", "openai"] = "elevenlabs"
    elevenlabs_api_key: SecretStr = SecretStr("")
    elevenlabs_voice_id: str = ""
    openai_api_key: SecretStr = SecretStr("")

    # YouTube
    youtube_data_api_key: str = ""          # 検索用（APIキー）
    youtube_client_secrets_path: str = "credentials/client_secrets.json"
    youtube_token_path: str = "credentials/token.json"
    youtube_default_privacy: Literal["private", "unlisted", "public"] = "private"

    # RAG
    rag_cache_dir: str = "rag/cache"
    rag_index_refresh_hours: int = 24

    # 動画
    video_template: str = "default_template"
    video_output_dir: str = "storage/videos"
    audio_output_dir: str = "storage/audio"
    scripts_output_dir: str = "storage/scripts"

    # ログ
    log_level: str = "INFO"
    log_dir: str = "storage/logs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
