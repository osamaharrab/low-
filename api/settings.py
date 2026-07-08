from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    weaviate_url: str = "http://weaviate:8080"
    weaviate_class: str = "LegalChunk"
    embedding_model: str = "intfloat/multilingual-e5-small"
    top_k: int = 5
    rag_prompt_top_n: int = 3
    chunk_text_limit: int = 900

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = 120

    api_url: str = "http://api:8000"
    next_public_api_url: str = "http://localhost:8001"
    web_origin: str = "http://localhost:3001"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
