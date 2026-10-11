import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "rag_db")
    DB_USER: str = os.getenv("DB_USER", "rag_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "rag_password")
    
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-mpnet-base-v2"
    NLI_MODEL_NAME: str = "cross-encoder/nli-deberta-v3-base"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
