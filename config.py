from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Aptivo Agent"
    environment: str = "development"
    api_key: str = "change-me-before-deploying"
    database_url: str = "sqlite+aiosqlite:///./aptivo.db"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    public_base_url: str = ""
    agent_vertical: str = "personal"
    business_name: str = ""
    business_hours: str = ""
    workspace_dir: str = "./workspace"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
