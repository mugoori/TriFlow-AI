"""
API Key 관리 서비스

- API Key 생성/검증/회전/폐기
- SHA-256 해시 기반 보안 저장
- 스코프 기반 권한 관리
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.core import ApiKey, User


# API Key 접두사 (TriFlow Key)
API_KEY_PREFIX = "tfk_"
API_KEY_LENGTH = 32  # 접두사 제외 32자


def generate_api_key() -> tuple[str, str, str]:
    """
    새 API Key 생성

    Returns:
        tuple: (full_key, key_prefix, key_hash)
        - full_key: 전체 키 (발급 시에만 표시, 저장 안함)
        - key_prefix: 키 앞 8자 (식별용)
        - key_hash: SHA-256 해시 (DB 저장용)
    """
    # 랜덤 키 생성
    random_part = secrets.token_urlsafe(API_KEY_LENGTH)
    full_key = f"{API_KEY_PREFIX}{random_part}"

    # 접두사 (식별용)
    key_prefix = full_key[:12]  # "tfk_" + 8자

    # 해시 생성
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    return full_key, key_prefix, key_hash


def hash_api_key(api_key: str) -> str:
    """API Key를 SHA-256으로 해시"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_api_key(
    db: Session,
    user: User,
    name: str,
    description: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    expires_in_days: Optional[int] = None,
) -> tuple[ApiKey, str]:
    """
    새 API Key 생성

    Args:
        db: DB 세션
        user: 키를 생성하는 사용자
        name: 키 이름
        description: 설명
        scopes: 권한 스코프 목록
        expires_in_days: 만료일 (일 단위, None이면 무기한)

    Returns:
        tuple: (ApiKey 객체, 전체 키 문자열)
        - 전체 키는 이 함수 호출 시에만 반환됨 (이후 조회 불가)
    """
    # 키 생성
    full_key, key_prefix, key_hash = generate_api_key()

    # 만료일 계산
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    # 기본 스코프
    if scopes is None:
        scopes = ["read"]

    # DB 저장
    api_key = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        name=name,
        description=description,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=scopes,
        expires_at=expires_at,
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return api_key, full_key


def validate_api_key(
    db: Session,
    api_key: str,
    required_scope: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> Optional[ApiKey]:
    """
    API Key 검증

    Args:
        db: DB 세션
        api_key: 검증할 API Key
        required_scope: 필요한 스코프 (선택적)
        client_ip: 클라이언트 IP (사용 기록용)

    Returns:
        ApiKey 객체 (유효한 경우) 또는 None
    """
    # 접두사 확인
    if not api_key.startswith(API_KEY_PREFIX):
        return None

    # 해시 계산
    key_hash = hash_api_key(api_key)

    # DB 조회
    db_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active is True,
        ApiKey.revoked_at.is_(None),
    ).first()

    if not db_key:
        return None

    # 만료 확인
    if db_key.expires_at and db_key.expires_at < datetime.utcnow():
        return None

    # 스코프 확인
    if required_scope:
        if required_scope not in db_key.scopes and "admin" not in db_key.scopes:
            return None

    # 사용 기록 업데이트
    db_key.last_used_at = datetime.utcnow()
    db_key.usage_count += 1
    if client_ip:
        db_key.last_used_ip = client_ip
    db.commit()

    return db_key


def rotate_api_key(
    db: Session,
    key_id: UUID,
    user: User,
) -> tuple[Optional[ApiKey], Optional[str]]:
    """
    API Key 회전 (새 키 발급 + 기존 키 폐기)

    Args:
        db: DB 세션
        key_id: 회전할 키 ID
        user: 요청 사용자

    Returns:
        tuple: (새 ApiKey 객체, 새 전체 키) 또는 (None, None)
    """
    # 기존 키 조회
    old_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.tenant_id == user.tenant_id,
        ApiKey.is_active is True,
    ).first()

    if not old_key:
        return None, None

    # 새 키 생성 (기존 설정 유지)
    new_key, full_key = create_api_key(
        db=db,
        user=user,
        name=f"{old_key.name} (rotated)",
        description=old_key.description,
        scopes=old_key.scopes,
        expires_in_days=None if not old_key.expires_at else
            max(1, (old_key.expires_at - datetime.utcnow()).days),
    )

    # 기존 키 폐기
    old_key.is_active = False
    old_key.revoked_at = datetime.utcnow()
    old_key.revoked_reason = f"Rotated to new key: {new_key.key_id}"
    db.commit()

    return new_key, full_key


def revoke_api_key(
    db: Session,
    key_id: UUID,
    user: User,
    reason: Optional[str] = None,
) -> bool:
    """
    API Key 폐기

    Args:
        db: DB 세션
        key_id: 폐기할 키 ID
        user: 요청 사용자
        reason: 폐기 사유

    Returns:
        성공 여부
    """
    api_key = db.query(ApiKey).filter(
        ApiKey.key_id == key_id,
        ApiKey.tenant_id == user.tenant_id,
    ).first()

    if not api_key:
        return False

    api_key.is_active = False
    api_key.revoked_at = datetime.utcnow()
    api_key.revoked_reason = reason or "Revoked by user"
    db.commit()

    return True


def list_api_keys(
    db: Session,
    user: User,
    include_revoked: bool = False,
) -> list[ApiKey]:
    """
    사용자의 API Key 목록 조회

    Args:
        db: DB 세션
        user: 요청 사용자
        include_revoked: 폐기된 키 포함 여부

    Returns:
        ApiKey 목록
    """
    query = db.query(ApiKey).filter(ApiKey.tenant_id == user.tenant_id)

    if not include_revoked:
        query = query.filter(ApiKey.revoked_at.is_(None))

    return query.order_by(ApiKey.created_at.desc()).all()


def get_api_key_stats(db: Session, user: User) -> dict:
    """
    API Key 통계 조회

    Returns:
        dict: {total, active, expired, revoked, usage_24h}
    """
    from sqlalchemy import func

    tenant_id = user.tenant_id
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    total = db.query(func.count(ApiKey.key_id)).filter(
        ApiKey.tenant_id == tenant_id
    ).scalar()

    active = db.query(func.count(ApiKey.key_id)).filter(
        ApiKey.tenant_id == tenant_id,
        ApiKey.is_active is True,
        ApiKey.revoked_at.is_(None),
        (ApiKey.expires_at.is_(None) | (ApiKey.expires_at > now)),
    ).scalar()

    expired = db.query(func.count(ApiKey.key_id)).filter(
        ApiKey.tenant_id == tenant_id,
        ApiKey.expires_at < now,
        ApiKey.revoked_at.is_(None),
    ).scalar()

    revoked = db.query(func.count(ApiKey.key_id)).filter(
        ApiKey.tenant_id == tenant_id,
        ApiKey.revoked_at.isnot(None),
    ).scalar()

    # 최근 24시간 사용량
    usage_24h = db.query(func.sum(ApiKey.usage_count)).filter(
        ApiKey.tenant_id == tenant_id,
        ApiKey.last_used_at >= yesterday,
    ).scalar() or 0

    return {
        "total": total,
        "active": active,
        "expired": expired,
        "revoked": revoked,
        "usage_24h": usage_24h,
    }
