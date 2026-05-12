from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # MinIO — E1
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "rag-documents"

    # PostgreSQL — E4
    postgres_dsn: str = "postgresql://raguser:ragpassword@localhost:5432/ragdb"

    # Qdrant — E2
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "pdf_chunks"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    chat_model: str = "llama3.2"
    embed_dim: int = 768

    # Pipeline
    chunk_target_tokens: int = 400
    chunk_overlap_tokens: int = 80
    top_k: int = 5

    # Redis — F5B Semantic Cache
    redis_host: str = "localhost"
    redis_port: int = 6379
    cache_similarity_threshold: float = 0.95
    cache_ttl_seconds: int = 3600

    # OpenSearch — E3 BM25
    opensearch_url: str = "http://localhost:9200"

    # Neo4j — C5 Knowledge Graph
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"


settings = Settings()
