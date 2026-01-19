"""CloudWatch 커스텀 메트릭 클라이언트

애플리케이션 메트릭을 CloudWatch에 전송합니다.
- API 응답 시간
- 워크플로우 실행 시간
- 비즈니스 메트릭 (Judgment 결과 등)
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from botocore.exceptions import ClientError

try:
    import boto3
    CLOUDWATCH_AVAILABLE = True
except ImportError:
    CLOUDWATCH_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


class CloudWatchMetricsClient:
    """CloudWatch 메트릭 클라이언트

    사용 예시:
        cw_client = CloudWatchMetricsClient()
        cw_client.put_metric(
            metric_name="WorkflowExecutionTime",
            value=1.234,
            unit="Seconds",
            dimensions={"WorkflowType": "DefectDetection"}
        )
    """

    def __init__(self, namespace: Optional[str] = None):
        """
        Args:
            namespace: CloudWatch 네임스페이스 (기본: TriFlow/Production)
        """
        if not CLOUDWATCH_AVAILABLE:
            logger.warning("boto3 not installed, CloudWatch metrics disabled")
            self.client = None
            self.namespace = None
            return

        try:
            self.client = boto3.client(
                'cloudwatch',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id if settings.aws_access_key_id else None,
                aws_secret_access_key=settings.aws_secret_access_key if settings.aws_secret_access_key else None
            )
            self.namespace = namespace or f"TriFlow/{settings.environment.title()}"
            logger.info(f"CloudWatch client initialized (namespace: {self.namespace})")
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch client: {e}")
            self.client = None
            self.namespace = None

    def is_available(self) -> bool:
        """CloudWatch 사용 가능 여부"""
        return self.client is not None

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """단일 메트릭 전송

        Args:
            metric_name: 메트릭 이름 (예: APILatency)
            value: 메트릭 값
            unit: 단위 (Seconds, Milliseconds, Count, Percent 등)
            dimensions: 차원 (예: {"Endpoint": "/api/workflows"})
            timestamp: 타임스탬프 (기본: 현재 시간)

        Returns:
            성공 여부
        """
        if not self.is_available():
            return False

        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': timestamp or datetime.utcnow()
            }

            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]

            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )

            logger.debug(f"Published metric: {metric_name}={value} {unit}")
            return True

        except ClientError as e:
            logger.error(f"Failed to publish metric {metric_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing metric: {e}")
            return False

    def put_metrics(self, metrics: List[Dict[str, Any]]) -> bool:
        """여러 메트릭 일괄 전송 (최대 20개)

        Args:
            metrics: 메트릭 리스트
                [
                    {"metric_name": "...", "value": 1.23, "unit": "Seconds"},
                    ...
                ]

        Returns:
            성공 여부
        """
        if not self.is_available():
            return False

        if not metrics or len(metrics) > 20:
            logger.warning(f"Invalid metrics count: {len(metrics)} (max: 20)")
            return False

        try:
            metric_data = []
            for m in metrics:
                data = {
                    'MetricName': m['metric_name'],
                    'Value': m['value'],
                    'Unit': m.get('unit', 'None'),
                    'Timestamp': m.get('timestamp', datetime.utcnow())
                }

                if 'dimensions' in m:
                    data['Dimensions'] = [
                        {'Name': k, 'Value': v} for k, v in m['dimensions'].items()
                    ]

                metric_data.append(data)

            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )

            logger.debug(f"Published {len(metrics)} metrics")
            return True

        except ClientError as e:
            logger.error(f"Failed to publish metrics: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing metrics: {e}")
            return False


# 컨텍스트 매니저: 실행 시간 자동 측정
class MetricTimer:
    """실행 시간을 자동으로 측정하여 CloudWatch에 전송

    사용 예시:
        with MetricTimer("WorkflowExecution", dimensions={"Type": "Defect"}):
            # 워크플로우 실행 코드
            execute_workflow()
        # 자동으로 실행 시간이 CloudWatch에 전송됨
    """

    def __init__(
        self,
        metric_name: str,
        client: Optional[CloudWatchMetricsClient] = None,
        dimensions: Optional[Dict[str, str]] = None
    ):
        self.metric_name = metric_name
        self.client = client or get_cloudwatch_client()
        self.dimensions = dimensions
        self.start_time: Optional[datetime] = None

    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds()

            self.client.put_metric(
                metric_name=self.metric_name,
                value=duration,
                unit='Seconds',
                dimensions=self.dimensions
            )

        # 예외 전파하지 않음
        return False


# 싱글톤 인스턴스
_cloudwatch_client: Optional[CloudWatchMetricsClient] = None


def get_cloudwatch_client() -> CloudWatchMetricsClient:
    """CloudWatch 클라이언트 싱글톤 인스턴스 반환"""
    global _cloudwatch_client

    if _cloudwatch_client is None:
        _cloudwatch_client = CloudWatchMetricsClient()

    return _cloudwatch_client
