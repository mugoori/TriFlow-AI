#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
안전한 Feature Flags 활성화 스크립트

Progressive Trust와 Data Source Trust를 기본 활성화합니다.
이 두 기능은 읽기 전용이고 자동 실행을 하지 않아 안전합니다.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.feature_flag_service import FeatureFlagService, V2Feature
from app.services.cache_service import CacheService

def main():
    """안전한 기능 활성화"""

    import io
    import sys
    # UTF-8 출력 설정
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # Redis 연결 확인
    client = CacheService.get_client()
    if client is None:
        print("Redis connection failed. Please start Docker.")
        return 1

    print("=== Enabling Safe Feature Flags ===\n")

    # 1. Progressive Trust 활성화
    result = FeatureFlagService.enable(V2Feature.PROGRESSIVE_TRUST)
    if result:
        print("✅ Progressive Trust 활성화 완료")
        print("   → AI 판단마다 Trust Score 계산")
        print("   → 위험: 없음 (읽기 전용)\n")
    else:
        print("❌ Progressive Trust 활성화 실패\n")

    # 2. Data Source Trust 활성화
    result = FeatureFlagService.enable(V2Feature.DATA_SOURCE_TRUST)
    if result:
        print("✅ Data Source Trust 활성화 완료")
        print("   → 데이터 소스별 신뢰도 평가")
        print("   → 위험: 없음 (경고만 표시)\n")
    else:
        print("❌ Data Source Trust 활성화 실패\n")

    # 현재 상태 확인
    print("=== 현재 Feature Flags 상태 ===\n")
    for feature in V2Feature:
        enabled = FeatureFlagService.is_enabled(feature)
        status = "🟢 ON" if enabled else "⚪ OFF"
        print(f"{status}  {feature.value}")

    print("\n✅ 완료! Settings 페이지를 새로고침하세요.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
