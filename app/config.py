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

    # Daily summary selection knobs (keyword weights live in
    # app/scrapper/config/scoring.py).
    JOB_SUMMARY_TOP_N: int = 5
    JOB_SUMMARY_MIN_SCORE: int = 1
    # Drop posts that hit a deal-breaker keyword from the summary entirely.
    JOB_EXCLUDE_DEALBREAKERS: bool = True
    # Only include posts that explicitly mention remote/hybrid work.
    JOB_REQUIRE_REMOTE: bool = False


settings = BaseConfig()
