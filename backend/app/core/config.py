from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str 
    groq_model_name: str = "llama-3.3-70b-versatile"
    embedding_model_name: str = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
    faiss_index_path: str = "data/indexes/faiss_student_manual"
    retrieval_top_k: int = 4

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
