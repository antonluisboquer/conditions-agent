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
        if settings.aws_role_arn:
            # Use STS to assume the specified role (recommended for production)
            logger.info(f"Assuming IAM role: {settings.aws_role_arn}")
            sts_client = boto3.client('sts', region_name=settings.aws_region)
            assumed_role = sts_client.assume_role(
                RoleArn=settings.aws_role_arn,
                RoleSessionName='conditions-agent-session',
                DurationSeconds=3600  # 1 hour
            )
            credentials = assumed_role['Credentials']
            self._client = boto3.client(
                's3',
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=settings.aws_region
            )
            # Set expiration time from STS response
            self._credentials_expire_at = credentials['Expiration'].replace(tzinfo=None)
            logger.info(f"Assumed role successfully, credentials expire at {self._credentials_expire_at}")
        elif settings.aws_access_key_id and settings.aws_secret_access_key:
            # Use provided credentials (with or without session token)
            if settings.aws_session_token:
                logger.info("Creating S3 client with temporary credentials (session token)")
                self._client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    aws_session_token=settings.aws_session_token,
                    region_name=settings.aws_region
                )
                # Temporary credentials typically expire in 1 hour (conservative estimate)
                self._credentials_expire_at = datetime.utcnow() + timedelta(hours=1)
            else:
                logger.info("Creating S3 client with explicit static credentials")
                self._client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region
                )
                # Static credentials don't expire
                self._credentials_expire_at = datetime.utcnow() + timedelta(days=365)
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

