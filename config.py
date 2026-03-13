from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM — must be set in .env, no defaults
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_small_model: str | None = None

    # Embedder — defaults to same endpoint as LLM
    embedder_api_key: str | None = None
    embedder_base_url: str | None = None
    embedder_model: str = "text-embedding-3-small"

    # Graph DB backend: "neo4j" or "falkordb"
    graph_db: str = "neo4j"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"

    # FalkorDB
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379

    # SQLite
    sqlite_path: str = "openzep.db"

    # Auth
    api_key: str | None = None  # if set, require Authorization: Bearer <key>

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
