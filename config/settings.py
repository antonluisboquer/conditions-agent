"""Application settings and configuration."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LangSmith Configuration
    langsmith_api_key: str
    langsmith_project: str = "conditions-agent"
    langsmith_tracing_v2: bool = True
    
    # Database Configuration
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # External Service Endpoints
    predicted_conditions_api_url: str
    rack_and_stack_api_url: str
    conditions_ai_api_url: str
    
    # Agent Configuration
    confidence_threshold: float = 0.7
    max_execution_timeout_seconds: int = 30
    cost_budget_usd_per_execution: float = 5.0
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

