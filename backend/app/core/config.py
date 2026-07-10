from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

class Settings(BaseSettings):
    groq_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    voyage_api_key: str | None = None
    pinecone_api_key: str | None = None
    llm_provider: str = "groq"
    embedding_provider: str = "voyage"
    reranker_provider: str = "voyage"
    llm_model_name: str = "llama-3.1-8b-instant"
    voyage_embedding_model_name: str = "voyage-3.5"
    pinecone_index_name: str = "campus-codex"
    pinecone_shared_namespace: str = "shared_kb"
    pinecone_benchmark_namespace: str = "benchmark"
    pdf_path: str = str(PROJECT_ROOT / "data" / "raw" / "student_manual_2019.pdf")
    retrieval_candidate_k: int = 15
    reranked_top_k: int = 5
    voyage_reranker_model_name: str = "rerank-2.5"
    enable_query_rewrite: bool = True
    eval_judge_model_name: str = "claude-haiku-4-5"
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.",
    ]

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
    )

    @field_validator("pdf_path", mode="before")
    @classmethod
    def resolve_project_relative_paths(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((BACKEND_DIR / path).resolve())

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_comma_separated_origins(cls, value: str | list[str]) -> str | list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
