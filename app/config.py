from pydantic_settings import BaseSettings, SettingsConfigDict

# Your main configuration class inherits from BaseSettings
class BaseConfig(BaseSettings):
    # Automatically load values from a .env file if it exists
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_nested_delimiter="__"
    )

    app_env: str = "development"
    logging_level: str = "DEBUG"

    LINKEDIN_EMAIL: str
    LINKEDIN_PASSWORD: str


settings = BaseConfig()
