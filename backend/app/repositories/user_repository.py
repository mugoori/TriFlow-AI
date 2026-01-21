# -*- coding: utf-8 -*-
"""
User Repository
사용자 데이터 접근 계층
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.core import User
from app.repositories.base_repository import BaseRepository
from app.utils.errors import raise_not_found


class UserRepository(BaseRepository[User]):
    """사용자 Repository"""
    
    def __init__(self, db: Session):
        super().__init__(db, User)
    
    def get_by_id_or_404(self, user_id: UUID) -> User:
        """ID로 사용자 조회 (없으면 404)"""
        user = self.db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise_not_found("User", str(user_id))
        return user
    
    def get_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        return self.db.query(User).filter(User.email == email).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """사용자명으로 조회"""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_active_users(self) -> List[User]:
        """활성 사용자 목록"""
        return self.db.query(User).filter(User.is_active == True).all()
    
    def get_by_tenant(self, tenant_id: UUID) -> List[User]:
        """테넌트별 사용자 목록"""
        return self.db.query(User).filter(User.tenant_id == tenant_id).all()
    
    def email_exists(self, email: str) -> bool:
        """이메일 중복 확인"""
        return self.db.query(User).filter(User.email == email).first() is not None
    
    def username_exists(self, username: str) -> bool:
        """사용자명 중복 확인"""
        return self.db.query(User).filter(User.username == username).first() is not None
