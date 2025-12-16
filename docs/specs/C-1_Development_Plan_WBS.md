# C-1. Development Plan & WBS

## 1. 개발 범위와 단계 (초안)
- **MVP (0~2개월)**: Hybrid Judgment, Workflow Runtime v1, Intent Router v1, BI Planner v1, MCP ToolHub skeleton, 기본 Observability/CI
- **V1 (2~4개월)**: Workflow Builder UI, BI 컴포넌트/Pre-agg, Learning Rule 후보/승인, Zwave Replay 최소판, 보안/RBAC 강화
- **V2 (4~6개월)**: Chart Intelligence, Scenario Simulation 확장, 로봇/PLC Action stub, Edge/Sensor 입력 스펙 확장, 고도 모니터링

## 2. WBS (요약)
| WBS | 작업 | 기간(주) | 담당 | 선행 |
| --- | --- | --- | --- | --- |
| 1 | 요구사항 확정/문서화(A-1~A-3) | 1 | PO/SE | - |
| 2 | DSL/정책 스펙(B-5, Hybrid Policy) | 1 | SE | 1 |
| 3 | Judgment Core (Rule+LLM, 캐시, 로그) | 2 | BE/ML | 2 |
| 4 | Workflow Runtime(노드/재시도/장기실행) | 2 | BE | 2 |
| 5 | Intent Router v1(LLM+룰) | 1 | BE | 2 |
| 6 | BI Planner v1 + 카탈로그 | 2 | BE/DS | 2 |
| 7 | MCP ToolHub + 커넥터 메타 | 1 | BE | 2 |
| 8 | Data ETL raw→fact + Pre-agg | 2 | DE | 2 |
| 9 | Observability/CI/CD 셋업 | 1 | DevOps | 병렬 |
| 10 | Learning 파이프라인(샘플/후보) | 2 | ML/BE | 3,4,5 |
| 11 | UI Builder/Monitoring/BI 뷰 | 2 | FE | 3~8 |
| 12 | 테스트/성능/보안 점검 | 1 | QA/SEC | 3~11 |
| 13 | PoC 릴리즈/운영 핸드오프 | 1 | 전팀 | 12 |

## 3. 리소스 계획 (예시)
- **PO/PM** 1, **SE/아키텍트** 1, **BE** 3, **FE** 1, **ML** 1, **DE** 1, **DevOps** 1, **QA** 1
- 외주/라이선스: LLM API 비용, 모니터링/로깅 SaaS(필요 시), 보안 점검

## 4. 리스크 및 대응전략
- **LLM 안정성/비용**: 저가형 모델 우선, 캐시/프롬프트 튜닝, Token 모니터링
- **데이터 품질/스키마 불일치**: 스키마 등록/검증 툴 제공, ETL 검증 단계, 샘플 데이터셋 확보
- **외부 연동 실패**: 회로차단/재시도/대체 경로, MCP ToolHub 타임아웃/알람
- **보안/PII 누출**: 마스킹/레드락팅, 프라이버시 레이어, 온프레 옵션
- **일정 슬립**: 크리티컬 경로(3,4,5,6,8)를 우선 완료, 주간 버퍼 10~15%

## 5. 산출물/Definition of Done (MVP 기준)
- 동작하는 API: Judgment/Workflow/BI/MCP/Intent
- DSL/Hybrid Policy/Prompt 문서와 코드 반영, 스키마 마이그레이션 완료
- 테스트: 단위 60%+, E2E 핵심 시나리오(판단/알림/BI) 통과, 성능 스모크(TPS/지연)
- 모니터링/알람 대시보드, 로그 수집/조회 가능
- 보안: 인증/권한 기본 적용, LLM 호출 로그 PII 마스킹 검증
- 운영: 배포 파이프라인/롤백, 운영 매뉴얼 초안
