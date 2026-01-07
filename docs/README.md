# TriFlow AI 문서

## 빠른 시작

| 목적 | 문서 |
|------|------|
| **프로젝트 현황 파악** | [프로젝트 현황 보고서](project/PROJECT_STATUS.md) |
| **개발 시작점 확인** | [개발 우선순위 가이드](specs/implementation/DEVELOPMENT_PRIORITY_GUIDE.md) |
| **스펙 vs 구현 비교** | [스펙 리뷰 요약](spec-reviews/00_SUMMARY_REPORT.md) |

---

## 문서 구조

```
docs/
├── project/           # 프로젝트 관리 문서
├── specs/             # 스펙 문서 (시리즈별 분류)
│   ├── A-requirements/    # 요구사항/기획
│   ├── B-design/          # 설계
│   ├── C-development/     # 개발/테스트
│   ├── D-operations/      # 운영
│   ├── E-advanced/        # 고급 기능
│   └── implementation/    # 구현 계획
├── spec-reviews/      # 스펙 리뷰 문서 (36개)
├── guides/            # 가이드 문서
├── diagrams/          # 다이어그램
└── archive/           # 구 버전/참고 문서
```

---

## 프로젝트 관리 (project/)

| 문서 | 대상 | 설명 |
|------|------|------|
| [프로젝트 현황](project/PROJECT_STATUS.md) | 상급자 | Executive Summary |
| [스펙 대비 현황](project/SPEC_COMPARISON.md) | PM/기획자 | 요구사항별 구현 현황 |
| [아키텍처](project/ARCHITECTURE.md) | 아키텍트 | 시스템 구조, 기술 스택 |
| [구현 가이드](project/IMPLEMENTATION_GUIDE.md) | 개발자 | 기능별 사용법, API 호출 |
| [품질 지표/로드맵](project/METRICS_ROADMAP.md) | 기술 리더 | 통계, 성능 지표, 향후 과제 |
| [QA 테스트 리포트](project/QA_TEST_REPORT_20251230.md) | QA | 테스트 결과 |

---

## 스펙 문서 (specs/)

### 시리즈 개요

| 시리즈 | 내용 | 문서 수 |
|--------|------|:------:|
| [A-requirements/](specs/A-requirements/) | 요구사항/기획 | 9개 |
| [B-design/](specs/B-design/) | 설계 | 19개 |
| [C-development/](specs/C-development/) | 개발/테스트 | 8개 |
| [D-operations/](specs/D-operations/) | 운영 | 9개 |
| [E-advanced/](specs/E-advanced/) | 고급 기능 | 6개 |
| [implementation/](specs/implementation/) | 구현 계획 | 2개 |

### 주요 스펙 문서

| 문서 | 설명 |
|------|------|
| [A-1 제품 비전](specs/A-requirements/A-1_Product_Vision_Scope.md) | 제품 비전 및 범위 |
| [A-2 시스템 요구사항](specs/A-requirements/A-2_System_Requirements_Spec.md) | 기능/비기능 요구사항 |
| [B-1-1 아키텍처 개요](specs/B-design/B-1-1_Architecture_Overview.md) | 시스템 아키텍처 |
| [B-5 워크플로우 상태 머신](specs/B-design/B-5_Workflow_State_Machine_Spec.md) | 워크플로우 엔진 |
| [B-6 AI Agent 아키텍처](specs/B-design/B-6_AI_Agent_Architecture_Prompt_Spec.md) | AI 에이전트 설계 |

### 구현 계획

| 문서 | 설명 |
|------|------|
| [V2 구현 계획](specs/implementation/V2_Implementation_Plan.md) | V2 전체 구현 계획 |
| [개발 우선순위 가이드](specs/implementation/DEVELOPMENT_PRIORITY_GUIDE.md) | 개발 시작점 및 우선순위 |

---

## 스펙 리뷰 (spec-reviews/)

스펙 문서 대비 실제 구현 현황 분석

| 문서 | 설명 |
|------|------|
| [요약 리포트](spec-reviews/00_SUMMARY_REPORT.md) | 전체 구현률 75%, Critical Gap 분석 |
| [리뷰 목록](spec-reviews/README.md) | 35개 개별 리뷰 문서 |

### 구현률 현황

| 영역 | 구현률 | 상태 |
|------|:------:|:----:|
| Judgment Engine | 86% | 🟢 |
| Workflow Engine | 100% | ✅ |
| BI Engine | 100% | ✅ |
| Learning Pipeline | 20% | 🔴 |
| RBAC | 40% | 🟡 |

---

## 가이드 (guides/)

| 문서 | 설명 |
|------|------|
| [배포 가이드](guides/DEPLOYMENT.md) | 설치 및 배포 방법 |
| [테스트 가이드](guides/TESTING.md) | 테스트 실행 방법 |
| [테스트 시나리오](guides/TEST_SCENARIOS.md) | E2E 테스트 시나리오 |
| [트러블슈팅](guides/TROUBLESHOOTING.md) | 문제 해결 가이드 |

---

## 기타

| 폴더 | 설명 |
|------|------|
| [diagrams/](diagrams/) | 시스템 다이어그램 |
| [archive/](archive/) | 구 버전 문서, 분석 파일 |

---

## 문서 작성 규칙

1. **파일 네이밍**: `[시리즈]-[번호]_[이름].md` (예: `B-1-1_Architecture_Overview.md`)
2. **Enhanced 버전**: 원본과 Enhanced가 공존할 경우 Enhanced만 유지
3. **스펙 리뷰**: 각 스펙에 대한 구현 현황 리뷰는 `spec-reviews/` 폴더에
4. **구현 계획**: 개발 관련 계획 문서는 `specs/implementation/` 폴더에

---

**최종 업데이트**: 2026-01-07
