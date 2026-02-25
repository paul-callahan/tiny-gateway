import logging
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/_gateway"
    PROJECT_NAME: str = "API Gateway"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = ConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    def configure_logging(self):
        """Configure logging based on LOG_LEVEL environment variable."""
        log_level = getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

settings = Settings()
