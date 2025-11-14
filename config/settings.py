"""Application settings and configuration."""
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LangSmith Configuration
    rewoo_langsmith_api_key: Optional[str] = Field(
        default=None, alias="REWOO_LANGSMITH_API_KEY"
    )
    rewoo_langsmith_project: str = Field(
        default="conditions-agent", alias="REWOO_LANGSMITH_PROJECT"
    )
    langsmith_tracing_v2: bool = True

    # LLM Configuration
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    openai_api_key: Optional[str] = None
    planner_model: str = "gpt-4o-mini"
    solver_model: str = "gpt-4o-mini"
    planner_temperature: float = 0.1
    solver_temperature: float = 0.3

    # PreConditions API (LangGraph Cloud)
    preconditions_deployment_url: Optional[str] = None
    preconditions_api_key: Optional[str] = None
    preconditions_assistant_id: Optional[str] = None
    
    # Conditions AI (Airflow v5)
    conditions_ai_api_url: Optional[str] = None
    airflow_username: Optional[str] = None
    airflow_password: Optional[str] = None
    
    # S3 Configuration (for fetching Conditions AI results)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None  # For temporary credentials
    aws_region: str = "us-east-1"
    aws_role_arn: Optional[str] = None  # Role ARN to assume for S3 access
    s3_output_bucket: Optional[str] = None
    
    # Database Configuration
    database_url: Optional[str] = None
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
        extra = "ignore"  # Ignore extra fields in .env file


# Global settings instance
settings = Settings()

