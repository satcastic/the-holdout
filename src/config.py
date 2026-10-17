"""Runtime configuration, loaded from environment variables and `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
CASE_DIR = ROOT / "case"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    anthropic_api_key: str = ""
    pinecone_api_key: str = ""
    pinecone_index: str = "the-holdout"
    pinecone_namespace: str = "case_01"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    pinecone_embed_model: str = "llama-text-embed-v2"

    llm_model_main: str = "claude-sonnet-5-5"
    llm_model_fast: str = "claude-haiku-5-5"
    llm_mode: Literal["real", "fake"] = "fake"
    max_tokens_main: int = 2000
    max_tokens_fast: int = 800

    vector_backend: Literal["pinecone", "memory"] = "memory"
    checkpointer: Literal["memory", "sqlite"] = "memory"
    sqlite_path: str = str(ROOT / "checkpoints.sqlite")

    case_file: str = str(CASE_DIR / "case_01.yaml")
    checker_enabled: bool = True
    max_retries: int = 2
    start_turns: int = 30
    max_wrong_accusations: int = 2
    retrieval_overfetch: int = 20
    retrieval_top_k: int = 5

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_per_minute: int = 20

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
