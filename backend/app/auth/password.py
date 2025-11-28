"""
비밀번호 해싱 유틸리티
bcrypt 알고리즘 사용 (passlib 대신 bcrypt 직접 사용 - 호환성 문제 해결)
"""
import bcrypt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 해시된 비밀번호 비교

    Args:
        plain_password: 사용자가 입력한 평문 비밀번호
        hashed_password: DB에 저장된 해시된 비밀번호

    Returns:
        일치 여부
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """
    비밀번호 해싱

    Args:
        password: 평문 비밀번호

    Returns:
        bcrypt 해시된 비밀번호
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")
