"""S3 클라이언트 래퍼

파일 업로드/다운로드/삭제 기능을 제공합니다.
테넌트별 폴더 격리를 지원합니다.
"""

import logging
from pathlib import Path
from typing import Optional, List
from botocore.exceptions import ClientError, BotoCoreError

try:
    import boto3
    from botocore.config import Config
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    """S3 클라이언트 래퍼

    사용 예시:
        s3_client = S3Client()
        uri = s3_client.upload_file(
            file_path="/tmp/result.csv",
            s3_key="tenants/uuid-123/workflows/wf-456/result.csv"
        )
    """

    def __init__(self):
        if not S3_AVAILABLE:
            logger.warning("boto3 not installed, S3 features will be disabled")
            self.client = None
            self.bucket = None
            return

        # boto3 설정 (재시도 로직)
        config = Config(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            connect_timeout=5,
            read_timeout=60
        )

        try:
            self.client = boto3.client(
                's3',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id if settings.aws_access_key_id else None,
                aws_secret_access_key=settings.aws_secret_access_key if settings.aws_secret_access_key else None,
                config=config
            )
            self.bucket = settings.s3_bucket_name
            logger.info(f"S3 client initialized (bucket: {self.bucket})")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.client = None
            self.bucket = None

    def is_available(self) -> bool:
        """S3 클라이언트 사용 가능 여부"""
        return self.client is not None and self.bucket is not None

    def upload_file(
        self,
        file_path: str,
        s3_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """파일을 S3에 업로드

        Args:
            file_path: 로컬 파일 경로
            s3_key: S3 객체 키 (예: tenants/uuid/workflows/wf-123/result.csv)
            content_type: MIME 타입 (선택사항)
            metadata: 사용자 정의 메타데이터 (선택사항)

        Returns:
            S3 URI (s3://bucket/key)

        Raises:
            RuntimeError: S3 사용 불가
            ClientError: S3 업로드 실패
        """
        if not self.is_available():
            raise RuntimeError("S3 client not available")

        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            if metadata:
                extra_args['Metadata'] = metadata

            # 서버 측 암호화 (AES256)
            extra_args['ServerSideEncryption'] = 'AES256'

            self.client.upload_file(
                Filename=file_path,
                Bucket=self.bucket,
                Key=s3_key,
                ExtraArgs=extra_args if extra_args else None
            )

            s3_uri = f"s3://{self.bucket}/{s3_key}"
            logger.info(f"Uploaded to S3: {s3_uri}")
            return s3_uri

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"S3 upload failed ({error_code}): {s3_key} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            raise

    def download_file(self, s3_key: str, file_path: str) -> str:
        """S3에서 파일 다운로드

        Args:
            s3_key: S3 객체 키
            file_path: 저장할 로컬 파일 경로

        Returns:
            로컬 파일 경로

        Raises:
            RuntimeError: S3 사용 불가
            ClientError: S3 다운로드 실패
        """
        if not self.is_available():
            raise RuntimeError("S3 client not available")

        try:
            # 디렉토리 생성
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            self.client.download_file(
                Bucket=self.bucket,
                Key=s3_key,
                Filename=file_path
            )

            logger.info(f"Downloaded from S3: {s3_key} → {file_path}")
            return file_path

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.error(f"S3 object not found: {s3_key}")
            else:
                logger.error(f"S3 download failed: {s3_key} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during S3 download: {e}")
            raise

    def delete_file(self, s3_key: str) -> bool:
        """S3 객체 삭제

        Args:
            s3_key: S3 객체 키

        Returns:
            성공 여부

        Raises:
            RuntimeError: S3 사용 불가
        """
        if not self.is_available():
            raise RuntimeError("S3 client not available")

        try:
            self.client.delete_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            logger.info(f"Deleted from S3: {s3_key}")
            return True

        except ClientError as e:
            logger.error(f"S3 delete failed: {s3_key} - {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during S3 delete: {e}")
            return False

    def list_objects(
        self,
        prefix: str,
        max_keys: int = 1000
    ) -> List[dict]:
        """S3 객체 목록 조회

        Args:
            prefix: 접두사 (예: tenants/uuid-123/workflows/)
            max_keys: 최대 반환 개수

        Returns:
            객체 목록 [{'Key': '...', 'Size': 123, 'LastModified': ...}, ...]

        Raises:
            RuntimeError: S3 사용 불가
        """
        if not self.is_available():
            raise RuntimeError("S3 client not available")

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
                MaxKeys=max_keys
            )

            if 'Contents' not in response:
                return []

            objects = [
                {
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat()
                }
                for obj in response['Contents']
            ]

            logger.debug(f"Listed {len(objects)} objects with prefix: {prefix}")
            return objects

        except ClientError as e:
            logger.error(f"S3 list failed: {prefix} - {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during S3 list: {e}")
            return []

    def get_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
        method: str = 'get_object'
    ) -> Optional[str]:
        """S3 객체에 대한 presigned URL 생성

        Args:
            s3_key: S3 객체 키
            expiration: URL 만료 시간 (초, 기본 1시간)
            method: HTTP 메서드 ('get_object' or 'put_object')

        Returns:
            Presigned URL (만료 시간 포함)
        """
        if not self.is_available():
            raise RuntimeError("S3 client not available")

        try:
            url = self.client.generate_presigned_url(
                ClientMethod=method,
                Params={
                    'Bucket': self.bucket,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            logger.debug(f"Generated presigned URL for {s3_key} (expires in {expiration}s)")
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {s3_key} - {e}")
            return None

    def build_tenant_key(self, tenant_id: str, category: str, filename: str) -> str:
        """테넌트별 S3 키 생성 헬퍼

        Args:
            tenant_id: 테넌트 UUID
            category: 카테고리 (workflows, uploads, exports)
            filename: 파일명

        Returns:
            S3 키 (tenants/{tenant_id}/{category}/{filename})
        """
        return f"tenants/{tenant_id}/{category}/{filename}"
