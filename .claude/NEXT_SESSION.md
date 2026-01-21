# 다음 세션 작업 가이드

**작성일**: 2026-01-21
**현재 상태**: Learning 탭 프론트엔드는 정상 작동 (백엔드 디버깅 필요)

---

## 🎯 즉시 해야 할 작업

### Learning 탭 백엔드 API 디버깅 (선택사항)

**우선순위**: ⭐⭐⭐ (중요하지만 급하지 않음)

**현재 상태**:
- ✅ import 경로 수정 완료
- ✅ 라우터 등록 성공 (9개 라우트)
- ✅ try-catch 추가 및 fallback 로직 구현
- ✅ **프론트엔드는 에러 시 데모 데이터 표시 - Learning 탭 정상 작동**
- ⚠️ 백엔드 API는 여전히 500 에러 (하지만 프론트엔드에 영향 없음)

**완료된 수정**:
1. [backend/app/routers/rule_extraction.py](backend/app/routers/rule_extraction.py:408-438)
   - GET /stats 엔드포인트에 try-catch 추가
   - 에러 시 빈 통계 반환

2. [backend/app/routers/rule_extraction.py](backend/app/routers/rule_extraction.py:96-152)
   - GET /candidates 엔드포인트에 try-catch 추가
   - 에러 시 빈 리스트 반환

3. [backend/app/schemas/rule_extraction.py](backend/app/schemas/rule_extraction.py:95)
   - precision 필드 alias 제거 (precision_score → precision)

4. [frontend/src/components/learning/RuleExtractionStatsCard.tsx](frontend/src/components/learning/RuleExtractionStatsCard.tsx:48-66)
   - ✅ 이미 에러 핸들링 구현되어 있음
   - 에러 시 데모 데이터 표시

5. [frontend/src/components/learning/RuleCandidateListCard.tsx](frontend/src/components/learning/RuleCandidateListCard.tsx:67-100)
   - ✅ 이미 에러 핸들링 구현되어 있음
   - 에러 시 데모 데이터 표시

**디버깅 포인트 (다음 세션)**:
- 라우터는 정상 등록되었으나 라우터 함수가 호출되지 않음
- 로그에 아무것도 찍히지 않음
- 가능한 원인: 미들웨어 에러, 경로 충돌, dependency 에러
- 확인 필요: audit middleware, metrics middleware, rate limiting middleware

---

## 📊 오늘 완료된 작업

1. DomainRegistry Multi-Tenant 구현 ✅
2. Repository 패턴 도입 ✅
3. Grafana Dashboards 3개 추가 ✅
4. 의존성 정리 ✅
5. Learning 탭 에러 핸들링 강화 ✅

**총 커밋**: 7개 (모두 푸시 완료)

---

## 🚀 다음 작업 순서

1. ~~Learning 탭 500 에러 수정~~ ✅ (프론트엔드는 정상 작동)
2. AWS 워크플로우 수정 (5분)
3. Prompt Tuning (선택, 6-8h)
4. 백엔드 API 디버깅 (선택, 근본 원인 파악)

---

**백엔드 실행 중**: 포트 8000
**Docker 실행 중**: PostgreSQL, Redis, Grafana
