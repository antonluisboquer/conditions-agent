"""Application settings and configuration."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LangSmith Configuration
    langsmith_api_key: str
    langsmith_project: str = "conditions-agent"
    langsmith_tracing_v2: bool = True
    
    # PreConditions API (LangGraph Cloud)
    preconditions_deployment_url: str
    preconditions_api_key: str
    preconditions_assistant_id: str
    
    # Conditions AI (Airflow v5)
    conditions_ai_api_url: str
    airflow_username: str
    airflow_password: str
    
    # S3 Configuration (for fetching Conditions AI results)
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_output_bucket: str
    
    # Database Configuration
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
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

