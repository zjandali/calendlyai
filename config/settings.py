from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # API Keys
    anchor_api_key: str = Field(None, env="ANCHOR_API_KEY")
    openai_api_key: str = Field(None, env="OPENAI_API_KEY")
    
    # Calendly configuration
    default_calendly_url: str = Field(
        'https://calendly.com/robertjandali/30min?month=2025-03',
        env="DEFAULT_CALENDLY_URL"
    )
    
    # Run configuration
    default_num_runs: int = Field(5, env="DEFAULT_NUM_RUNS")
    default_max_retries: int = Field(5, env="DEFAULT_MAX_RETRIES")
    
    # Anchor browser configuration
    anchor_browser_config: dict = {
        "adblock_config": {
            "active": False,
            "popup_blocking_active": False
        },
        "captcha_config": {"active": True},
        "headless": False,
        "proxy_config": {
            "type": "anchor_residential",
            "active": True
        },
        "recording": {"active": False},
        "profile": {
            "name": "my-profile",
            "persist": True,
            "store_cache": True
        },
        "viewport": {
            "width": 1440,
            "height": 900
        },
        "timeout": 10,
        "idle_timeout": 3
    }
    
    # Validation
    @validator('anchor_api_key', 'openai_api_key')
    def check_api_keys(cls, v, values, **kwargs):
        if not v:
            raise ValueError(f"Missing required API key: {kwargs.get('field').name}")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create instance for import
settings = Settings() 