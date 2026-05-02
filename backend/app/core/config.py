from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

class Settings(BaseSettings):
    groq_api_key: str | None = None
    groq_model_name: str = "llama-3.3-70b-versatile"
    embedding_model_name: str = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
    faiss_index_path: str = str(PROJECT_ROOT / "data" / "indexes" / "faiss_student_manual")
    pdf_path: str = str(PROJECT_ROOT / "data" / "raw" / "student_manual_2019.pdf")
    retrieval_candidate_k: int = 15
    reranked_top_k: int = 5
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
    )

    @field_validator("faiss_index_path", "pdf_path", mode="before")
    @classmethod
    def resolve_project_relative_paths(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((BACKEND_DIR / path).resolve())


settings = Settings()
