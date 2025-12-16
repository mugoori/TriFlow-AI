"""
Core Schema Extended ORM Models
스펙 참조: B-3-1_Core_Schema.md

NOTE: 이 파일의 모든 클래스는 core.py로 통합되었습니다.
      이 파일은 호환성을 위해 유지되지만, 새로운 모델은 core.py에 추가하세요.

Migration 011에서 추가된 테이블들의 ORM 정의:
- 워크플로우 단계, 실행 로그
- 판단 캐시
- 룰 충돌/배포
- 학습 샘플, 자동 룰 후보
- 프롬프트 템플릿
- 채팅 세션/메시지
- 데이터 커넥터
- MCP 통합
- 모델 학습 작업

이제 app.models.core에서 모든 모델을 가져올 수 있습니다.
"""

# All classes moved to core.py - this file is kept for reference only
# Import from core.py instead
