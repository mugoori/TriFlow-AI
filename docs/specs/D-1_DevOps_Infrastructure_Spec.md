# D-1. DevOps & Infrastructure Spec

## 1. 인프라 토폴로지 (추천)
- **클라우드 옵션**: VPC(공용/사설), 서브넷 분리(Web/API, App, DB), ALB/NLB, Bastion
- **온프렘 옵션**: K8s 클러스터 + Ingress + MetalLB/HAProxy
- **핵심 컴포넌트**:
  - API Gateway(Kong/Nginx)
  - App Services(Chat/Intent/WF/Judgment/BI/Learning/MCP)
  - Data: Postgres(primary+replica), Redis(Cluster/Sentinel), Object Storage(S3/MinIO)
  - Observability: Prometheus+Grafana, Loki/ELK, Alertmanager
  - CI/CD Runner, Artifact Registry(Container)

## 2. 배포 파이프라인 (CI/CD)
- **CI 단계**: lint → test → build → security scan(SCA/SAST/secret) → image build → push
- **CD 단계**: staging deploy → smoke → manual approval → prod deploy
- **전략**: Helm/Kustomize, Rolling/Canary(기본), Blue-Green(선택), DB 마이그레이션 pre/post hook
- **검증**: 헬스체크, 로그/메트릭 수집 확인, 롤백 버튼(직전 릴리즈 태그)

## 3. 설정/비밀키 관리
- **Config**: ConfigMap/Env(비민감), Helm values; 테넌트별 설정은 DB/설정 서비스에 저장
- **Secret**: K8s Secret + KMS, 외부 Vault(옵션), 권한 최소화
- **LLM/MCP 자격**: per-tenant key 분리, 로깅 금지, 만료/회전 지원

## 4. 롤백/재해복구
- 애플리케이션: 이전 이미지 재배포, Helm rollback
- DB: 백업/스냅샷(WAL), PITR; 마이그레이션 실패 시 다운그레이드 스크립트 준비
- Redis: AOF/RDB 백업, 장애 시 캐시 비움 후 재생성
- DR 목표: **RTO 4h, RPO 30m (초안)**
- DR 절차: 주기적 백업 검증(주 1회 복구 테스트) → DR 리전/온프렘 복제(옵션) → 장애 시 DNS/Ingress 전환 → 데이터 정합성 검증 체크리스트 실행

## 5. 운영 자동화/정책
- **모니터링 지표**: 서비스 에러율/지연, LLM 실패율, 캐시 적중률, 큐 대기, DB/Redis 자원, MCP/외부 연동 성공률
- **알람**: 임계값 + 슬랙/문자, 에러 버스트 감지, LLM 비용 급증 경보; 알람→액션 매핑(온콜/스케일/회로차단)
- **로그**: 구조화(JSON), Trace-id 포함, PII 마스킹, 보관/아카이빙 정책
- **스케일링**: HPA(CPU/지연/큐 길이), 크론 기반 축소/확장 가능
- **배포 윈도우**: 영업시간 외 우선, 긴급 패치 시 롤백 플랜 필수

## 6. 추적성 체크리스트 (DevOps/Infra ↔ 요구/테스트/모니터링)
- CI/CD 배포/롤백: A-2 OBS/DR-FR ↔ C-3 TC(canary/롤백) ↔ D-3 배포 runbook ↔ D-2 알람/SLO 관찰.
- DR: A-2 DR-FR ↔ D-3 DR 절차/검증 SQL ↔ 백업/복구 설정(WAL/스냅샷) ↔ 알람(DR 트리거).
- 보안/시크릿: A-2 SEC-FR ↔ C-5 PII/HMAC/RBAC ↔ Vault/Secret 관리 ↔ C-3 보안 TC.
- 스케일링/성능: A-2 NFR(지연/TPS) ↔ HPA/리소스 설정 ↔ D-2 SLO/알람 ↔ C-3 성능 테스트.
