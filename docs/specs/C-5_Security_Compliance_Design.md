# C-5. Security & Compliance Design

## 1. 인증/인가 구조
- **AuthN**: OAuth2/OIDC(JWT), 서비스 간 mTLS 옵션; 토큰에 tenant_id, roles 포함
- **AuthZ**: RBAC(admin/operator/viewer/approver); API 별 권한 매트릭스; 워크플로우/Rule/Prompt 변경은 승인/감사 필수
- **Session**: Chat/UI는 짧은 세션 토큰 + Refresh, CSRF 보호(웹)

## 2. 데이터 보안
- **암호화**: TLS 전송, DB at-rest 암호화(클라우드 KMS), 비밀키는 Secret Manager/K8s Secret
- **PII/민감정보**: 입력 단계 마스킹 옵션(LLM 전 게이트웨이/Adapter), 로그/LLM payload에서 PII 제거/치환
- **키 관리**: KMS/RBAC, 키 롤테이션 정책(90일), LLM API 키 별도 스토리지

## 3. 감사/로그 정책
- **감사 대상**: Rule/Prompt/DSL 변경, 커넥터 등록/수정, 권한 변경, Judgment 실행, 배포/롤백
- **필수 필드**: who/when/what(before/after)/version/ticket/approver/trace_id
- **보존**: 판단/CCP/감사 로그 2년 이상, 접근로그 6개월 이상(규제에 따라 조정)

## 4. 규제/개인정보 대응
- **HACCP/ISO/FSSC**: CCP 기록 변경 불가/감사추적, LOT 추적 필수, 2년 보관
- **개인정보**: 최소 수집 원칙, 목적 외 사용 금지, 요청 시 삭제/익명화; 데이터 국외반출 시 계약/동의 확보
- **LLM 사용 시**: 고객사 지정 데이터만 사용, 모델/벤더 별 데이터 보존 정책 확인, 필요 시 온프레 모델로 대체 옵션 제공

## 5. 네트워크/인프라 보안
- VPC/서브넷 분리, SG/NSG 최소화, DB는 내부망만; WAF/레이트리밋; MCP/외부로 나가는 트래픽 egress 제어
- 비상 접근은 Jump/Bastion, 모든 접근 로그화
- **Webhook 보안**: 서명/HMAC, idempotency-key, 재전송 제한, IP 화이트리스트(옵션)

## 6. 보안 테스트 & 대응
- 정적 분석(SAST), 취약점 스캔(SCA), 비밀키 스캔, 종속성 CVE 모니터링
- 펜테스트/모의해킹(하이시즌 전에), 취약점 패치 SLA 정의
- 사고 대응 Runbook: 탐지→분류→격리→조치→보고, 커뮤니케이션 채널 지정

## 7. PII/마스킹/웹훅 HMAC 예시
- **PII 마스킹 규칙**: 이름/전화/이메일/주민번호/주소/자주 쓰는 필드에 대해 정규식 기반 치환(예: 이메일 `user@example.com`→`u***@example.com`), LLM 호출 전 필터 적용, 로그 저장 금지.
- **민감 필드 레이블링**: 스키마/DSL에 `sensitive:true` 메타 추가 → 게이트웨이/Adapter가 자동 마스킹.
- **Webhook HMAC 예시**:
  - 헤더: `X-Signature: sha256=HEX(HMAC_SHA256(secret, body))`
  - 수신 측: 바디 원문으로 HMAC 검증, 타임스탬프 허용창(예: 5분) 체크, idempotency-key로 중복 처리 방지.

## 8. 역할/권한 매트릭스 (예시)
| 기능 | admin | operator | viewer | approver |
| --- | --- | --- | --- | --- |
| 워크플로우 생성/수정/배포 | O | O | X | 승인만 |
| Rule/Prompt 생성/배포 | O | O | X | 승인만 |
| 커넥터 등록/수정 | O | O | X | X |
| 판단/BI 실행 | O | O | O | O |
| 로그/감사 조회 | O | O | O(제한) | O(제한) |
| 사용자/권한 관리 | O | X | X | X |

## 9. 추적성 체크리스트 (보안/컴플라이언스 ↔ 요구/데이터/테스트/모니터링)
- SEC-FR (A-2) ↔ B-4 인증/웹훅/HMAC ↔ B-3 audit_logs/PII 필드 ↔ C-3 TC-SEC/Webhook HMAC ↔ D-2 보안/감사 로그 알람 ↔ D-3 DR/배포 점검.
- PII 마스킹: A-2 SEC-FR ↔ C-5 마스킹 규칙 ↔ 게이트웨이/Adapter 구현 ↔ 로그/LLM 전송 차단 확인 테스트.
