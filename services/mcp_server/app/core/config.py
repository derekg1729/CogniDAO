from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    COGNI_DOLT_DIR: str = "data/memory_dolt"  # Default value if not in .env
    CHROMA_PATH: str = "data/memory_chroma"  # Default path for ChromaDB
    CHROMA_COLLECTION_NAME: str = "cogni_mcp_collection"  # Default Chroma collection
    MCP_SERVER_PORT: int = 8001  # Default port for the MCP server
    # Add other configurations here as needed
    # Example: API_V1_STR: str = "/api/v1"


settings = Settings()
