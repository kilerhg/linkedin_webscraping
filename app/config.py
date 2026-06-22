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

    # When True, run Chrome headed (visible) so you can watch/debug the scrape.
    # When False (default, e.g. cron), run headless so it needs no X display.
    DEBUG: bool = False

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

    # Real-time alert run (the 7-9am poller): push a notification for fresh,
    # high-scoring posts so you can apply first. See run_alerts() in main.py.
    NTFY_SERVER: str = "https://ntfy.sh"
    NTFY_TOPIC: str = ""           # 64-hex random string -> set in .env
    NTFY_TOKEN: str = ""           # optional bearer token for an access-controlled topic
    JOB_ALERT_MIN_SCORE: int = 18  # only ping for strong-to-ideal matches
    JOB_ALERT_MAX_AGE_MIN: int = 60  # only ping for posts this fresh (be first to apply)


settings = BaseConfig()
