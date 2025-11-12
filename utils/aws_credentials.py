"""AWS credentials management with automatic refresh for temporary credentials."""
import boto3
from datetime import datetime, timedelta
from typing import Optional
from config.settings import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RefreshableS3Client:
    """S3 client that automatically refreshes credentials."""
    
    def __init__(self):
        self._client = None
        self._credentials_expire_at: Optional[datetime] = None
        self._refresh_threshold = timedelta(minutes=5)  # Refresh 5 min before expiry
    
    def _should_refresh(self) -> bool:
        """Check if credentials need refreshing."""
        if self._credentials_expire_at is None:
            return True
        return datetime.utcnow() + self._refresh_threshold >= self._credentials_expire_at
    
    def _create_client(self):
        """Create or refresh S3 client."""
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            logger.info("Creating S3 client with explicit credentials")
            self._client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
            # Assume session tokens expire in 1 hour (adjust as needed)
            self._credentials_expire_at = datetime.utcnow() + timedelta(hours=1)
        else:
            logger.info("Creating S3 client with default credential chain")
            # Use default credential chain (IAM role, AWS CLI profile, etc.)
            self._client = boto3.client('s3', region_name=settings.aws_region)
            # IAM roles auto-refresh, so set far future expiry
            self._credentials_expire_at = datetime.utcnow() + timedelta(days=365)
    
    def get_client(self):
        """Get S3 client, refreshing if necessary."""
        if self._client is None or self._should_refresh():
            logger.info("Refreshing S3 credentials")
            self._create_client()
        return self._client


# Global refreshable client
refreshable_s3_client = RefreshableS3Client()

