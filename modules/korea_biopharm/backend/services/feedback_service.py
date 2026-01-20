"""
Feedback Service - TriFlow 통합 패턴
"""
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Dict, Any, Optional
from datetime import datetime

from .db_service import execute_query, fetch_all


class FeedbackService:
    """피드백 서비스"""

    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def create_feedback(
        self,
        recipe_id: int,
        rating: int,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """피드백 저장"""
        if rating < 1 or rating > 5:
            raise ValueError("평점은 1-5 사이여야 합니다.")

        query = """
            INSERT INTO feedback_logs (recipe_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?)
        """
        now = datetime.now().isoformat()

        execute_query(query, (recipe_id, rating, comment, now))
        return {"success": True, "message": "피드백이 저장되었습니다."}

    async def get_all_feedback(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """모든 피드백 조회"""
        query = """
            SELECT id, recipe_id, rating, comment, created_at
            FROM feedback_logs
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        rows = fetch_all(query, (limit, skip))
        return [
            {
                "id": row[0],
                "recipe_id": row[1],
                "rating": row[2],
                "comment": row[3],
                "created_at": row[4]
            }
            for row in rows
        ]

    async def get_feedback_stats(self) -> Dict[str, Any]:
        """피드백 통계"""
        query = """
            SELECT
                COUNT(*) as total,
                AVG(rating) as avg_rating,
                SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as positive_count
            FROM feedback_logs
        """
        rows = fetch_all(query)
        if rows and rows[0]:
            total = rows[0][0] or 0
            avg_rating = rows[0][1] or 0
            positive_count = rows[0][2] or 0
            return {
                "total_feedback": total,
                "average_rating": round(avg_rating, 2) if avg_rating else 0,
                "positive_count": positive_count,
                "positive_rate": round((positive_count / total * 100), 1) if total > 0 else 0
            }
        return {
            "total_feedback": 0,
            "average_rating": 0,
            "positive_count": 0,
            "positive_rate": 0
        }
