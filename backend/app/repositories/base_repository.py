# -*- coding: utf-8 -*-
"""
Base Repository
모든 Repository의 기본 클래스
"""
from typing import Generic, TypeVar, Type, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.utils.errors import raise_not_found

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    기본 Repository 클래스
    공통 CRUD 메서드 제공
    """
    
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model
    
    def get_by_id(self, id: UUID) -> Optional[T]:
        """ID로 조회"""
        return self.db.query(self.model).filter(
            self.model.id == id  # type: ignore
        ).first()
    
    def get_by_id_or_404(self, id: UUID) -> T:
        """ID로 조회 (없으면 404)"""
        resource = self.get_by_id(id)
        if not resource:
            raise_not_found(self.model.__name__, str(id))
        return resource
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """전체 조회 (페이지네이션)"""
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, obj: T) -> T:
        """생성"""
        self.db.add(obj)
        self.db.flush()
        return obj
    
    def update(self, obj: T) -> T:
        """업데이트"""
        self.db.add(obj)
        self.db.flush()
        return obj
    
    def delete(self, obj: T):
        """삭제"""
        self.db.delete(obj)
        self.db.flush()
