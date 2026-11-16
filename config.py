from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Aptivo Agent"
    environment: str = "development"
    api_key: str = "change-me-before-deploying"
    database_url: str = "sqlite+aiosqlite:///./aptivo.db"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    workspace_dir: str = "./workspace"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
