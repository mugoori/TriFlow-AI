"""
비밀번호 해싱 유틸리티
bcrypt 알고리즘 사용
"""
from passlib.context import CryptContext

# bcrypt 컨텍스트 설정
# deprecated="auto": 새로운 해시 알고리즘이 추가되면 자동으로 마이그레이션
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 해시된 비밀번호 비교

    Args:
        plain_password: 사용자가 입력한 평문 비밀번호
        hashed_password: DB에 저장된 해시된 비밀번호

    Returns:
        일치 여부
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    비밀번호 해싱

    Args:
        password: 평문 비밀번호

    Returns:
        bcrypt 해시된 비밀번호
    """
    return pwd_context.hash(password)
