"""AWS 서비스 클라이언트 래퍼

이 모듈은 boto3를 래핑하여 TriFlow AI에서 사용하는 AWS 서비스에 대한
일관된 인터페이스를 제공합니다.

지원 서비스:
- S3: 파일 스토리지 (워크플로우 결과, 업로드 파일)
- Secrets Manager: 비밀 정보 관리 (DB 비밀번호, API 키)
- CloudWatch: 로그 및 메트릭 (모니터링, 알람)
"""

from .s3_client import S3Client
from .secrets_manager import SecretsManagerClient
from .cloudwatch_metrics import CloudWatchMetricsClient

__all__ = [
    "S3Client",
    "SecretsManagerClient",
    "CloudWatchMetricsClient",
]
