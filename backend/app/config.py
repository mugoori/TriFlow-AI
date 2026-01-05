"""
환경 설정 모듈
Pydantic Settings를 사용하여 .env 파일에서 환경변수를 로드합니다.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # Application
    app_name: str = "TriFlow AI"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 40

    # Redis
    redis_url: str
    redis_max_connections: int = 50

    # AWS S3 Storage (선택 - 없으면 로컬 저장소 사용)
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = "triflow-ai"

    # AI Models (MVP: Anthropic Only - Rule 8)
    anthropic_api_key: str

    # Embedding & Reranking (E-1 스펙)
    openai_api_key: str = ""       # OpenAI Embedding용 (선택)
    voyage_api_key: str = ""       # Voyage AI Embedding용 (선택)
    cohere_api_key: str = ""       # Cohere Reranking용 (E-1 스펙)

    # LLM Settings
    default_llm_model: str = "claude-sonnet-4-5-20250929"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_timeout: int = 60

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # CORS
    cors_origins: str = "http://localhost:1420,http://localhost:5173,http://localhost:3000"
    cors_allow_credentials: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate Limiting
    rate_limit_enabled: bool = True  # 개발 환경에서 False로 설정 가능

    # Monitoring
    prometheus_port: int = 9090

    # Sentry (Error Tracking)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_profiles_sample_rate: float = 0.1

    # OAuth2 - Google
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS origins를 리스트로 변환"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 전역 설정 인스턴스
settings = Settings()
