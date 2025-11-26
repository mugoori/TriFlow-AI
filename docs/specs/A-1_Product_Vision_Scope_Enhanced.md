# A-1. Product Vision & Scope - Enhanced

## 문서 정보
- **문서 ID**: A-1
- **버전**: 2.0 (Enhanced)
- **최종 수정일**: 2025-11-26
- **상태**: Draft
- **관련 문서**:
  - A-2 System Requirements Spec
  - A-3 Use Case & User Story
  - B-1 System Architecture

## 목차
1. [제품 비전](#1-제품-비전)
2. [시장 분석 및 경쟁 분석](#2-시장-분석-및-경쟁-분석)
3. [타겟 고객 및 페르소나](#3-타겟-고객-및-페르소나)
4. [문제 정의 및 해결 방안](#4-문제-정의-및-해결-방안)
5. [제품 범위 (Scope)](#5-제품-범위-scope)
6. [주요 기능 개요](#6-주요-기능-개요)
7. [비즈니스 모델](#7-비즈니스-모델)
8. [성공 기준 및 메트릭](#8-성공-기준-및-메트릭)
9. [로드맵 및 릴리스 계획](#9-로드맵-및-릴리스-계획)
10. [리스크 및 가정사항](#10-리스크-및-가정사항)

---

## 1. 제품 비전

### 1.1 비전 선언문 (Vision Statement)

> **"AI Factory Decision Engine은 제조 현장의 모든 판단을 지능화하여, 데이터 기반 의사결정을 실시간으로 지원하고, 지속적 학습을 통해 제조 품질과 생산성을 혁신한다."**

### 1.2 미션 (Mission)

우리는 제조 현장의 다음을 실현한다:

1. **빠르고 정확한 판단**: Rule과 AI를 결합하여 1.5초 이내 정확한 판단 제공
2. **설명 가능한 AI**: 판단 근거와 증거를 명확히 제시하여 신뢰 확보
3. **지속적 학습**: 피드백을 통해 자동으로 개선되는 지능형 시스템
4. **쉬운 사용**: 자연어로 데이터 조회하고 워크플로우를 구성
5. **통합 플랫폼**: ERP, MES, 센서, 엑셀 등 모든 데이터 소스 통합

### 1.3 핵심 가치 제안 (Value Proposition)

#### 제조 현장 관리자에게:
- ⏱️ **빠른 의사결정**: 불량 발생 시 1.5초 내 원인 추정 및 조치 가이드
- 🎯 **정확한 판단**: Rule + AI Hybrid로 정확도 90% 이상, 오경보 50% 감소
- 📊 **통합 대시보드**: 생산/품질/설비 데이터를 한눈에 파악

#### 품질 관리자에게:
- 🔍 **근본 원인 분석**: 자동 RCA Workflow로 원인 파악 시간 70% 단축
- 📈 **트렌드 분석**: 자연어 BI 쿼리로 불량 패턴 즉시 확인
- ✅ **추적 가능성**: 모든 판단 로그 2년 보존, HACCP/ISO 22000 준수

#### AI 엔지니어에게:
- 🤖 **자동 Rule 추출**: 학습 샘플에서 Decision Tree 기반 Rule 자동 생성
- 🚀 **안전한 배포**: Canary 배포로 점진적 업데이트, 자동 롤백
- 📉 **비용 최적화**: Rule 우선 사용으로 LLM 비용 60% 절감

#### 경영진에게:
- 💰 **ROI 측정**: OEE 향상, 불량 감소, 인건비 절감 정량화
- 📊 **고수준 대시보드**: 전사 생산성 지표 실시간 모니터링
- 🏆 **경쟁력 강화**: 스마트 팩토리 전환, 디지털 트윈 기반 시뮬레이션

---

## 2. 시장 분석 및 경쟁 분석

### 2.1 시장 규모 (TAM, SAM, SOM)

| 시장 | 규모 (2025) | 설명 |
|------|-------------|------|
| **TAM** (Total Addressable Market) | $500B | 전 세계 제조업 스마트 팩토리 시장 |
| **SAM** (Serviceable Available Market) | $50B | AI 기반 의사결정 지원 시스템 (국내 + 아시아) |
| **SOM** (Serviceable Obtainable Market) | $500M | 중소/중견 제조업 (식음료, 화학, 조립) |

**성장률**: 연평균 15% (2025~2030)

**동인**:
- 스마트 팩토리 정부 지원 (한국, 중국, 일본)
- AI/LLM 기술 성숙
- 노동력 부족 (자동화 니즈)
- ESG 규제 강화 (품질 추적, 탄소 배출)

### 2.2 경쟁사 분석

| 경쟁사 | 강점 | 약점 | 차별화 전략 |
|--------|------|------|------------|
| **SAP MII** | 엔터프라이즈 급, ERP 통합 | 고비용, 복잡한 설정, AI 부족 | ✅ AI Hybrid, 저비용, 쉬운 설정 |
| **Siemens MES** | 설비 통합, 강력한 MES | AI 제한적, 커스터마이징 어려움 | ✅ 자연어 BI, Workflow DSL |
| **Palantir Foundry** | 강력한 데이터 통합, AI | 고비용, 제조 도메인 약함 | ✅ 제조 특화, Rule Hybrid, 저비용 |
| **C3 AI** | AI 플랫폼, 예측 모델 | 복잡도 높음, 비용 높음 | ✅ 간단한 사용성, Canary 배포 |
| **자체 개발** | 커스터마이징 가능 | 개발/유지보수 부담, AI 전문성 부족 | ✅ SaaS, 지속 개선, 전문 AI |

**우리의 경쟁 우위**:
1. **Rule + LLM Hybrid**: 정확도와 설명 가능성 모두 확보
2. **자동 학습**: 피드백 기반 지속 개선, Rule 자동 추출
3. **Workflow DSL**: 비개발자도 워크플로우 구성 가능
4. **저비용**: Rule 우선 사용으로 LLM 비용 60% 절감
5. **빠른 온보딩**: SaaS 모델, 1일 내 시작 가능

---

## 3. 타겟 고객 및 페르소나

### 3.1 타겟 고객 세그먼트

#### 3.1.1 1차 타겟 (Primary)
- **산업**: 식음료, 화학, 조립 제조업
- **규모**: 중견기업 (직원 100~1000명, 매출 500억~5000억)
- **특징**:
  - 생산 라인 5~20개
  - ERP/MES 시스템 보유
  - 품질 이슈로 인한 손실 발생
  - 스마트 팩토리 전환 의지

#### 3.1.2 2차 타겟 (Secondary)
- **산업**: 전자, 자동차 부품, 의료기기
- **규모**: 대기업 (직원 1000명+, 매출 5000억+)
- **특징**:
  - 복잡한 공정 (50개+ 라인)
  - 높은 품질 요구 (Six Sigma)
  - 규제 준수 필요 (FDA, ISO)

### 3.2 페르소나

#### Persona 1: 김현장 (제조 현장 관리자)
- **나이**: 45세
- **경력**: 20년 (현장 15년, 관리자 5년)
- **목표**: 불량 조기 발견, 빠른 조치, 생산 효율 향상
- **Pain Points**:
  - 불량 발생 후 대응이 늦어 추가 손실 발생
  - 데이터가 여러 시스템에 흩어져 있어 파악 어려움
  - 경보가 많아서 무시하게 됨 (오경보)
- **Needs**:
  - 실시간 알림 (Slack)
  - 명확한 조치 가이드
  - 간단한 UI (모바일 지원)
- **Scenarios**:
  - Slack에서 `@AI-Factory LINE-A 불량 판단` 요청
  - 판단 결과 즉시 수신 (상태, 조치사항)
  - 조치 후 피드백 제공 (👍👎)

#### Persona 2: 이품질 (품질 관리자)
- **나이**: 38세
- **경력**: 10년 (품질 엔지니어 7년, 관리자 3년)
- **목표**: 불량률 감소, 근본 원인 파악, 규제 준수
- **Pain Points**:
  - 근본 원인 분석에 수일 소요
  - 데이터 수집 및 정리에 시간 낭비
  - 보고서 작성이 수동적이고 반복적
- **Needs**:
  - 자동 RCA (Root Cause Analysis)
  - 자연어 BI 쿼리 ("지난 달 불량률 트렌드")
  - 정기 보고서 자동 생성
- **Scenarios**:
  - 불량 이벤트 선택 → RCA Workflow 실행
  - 추정 원인 Top 3, 근거 차트 확인
  - 조치 계획 수립 및 Jira 이슈 생성

#### Persona 3: 박분석 (데이터 분석가)
- **나이**: 32세
- **경력**: 5년 (데이터 분석)
- **목표**: 생산/품질 데이터 분석, 인사이트 도출, 보고서 작성
- **Pain Points**:
  - SQL 작성 시간 소요
  - 데이터 소스 파악 어려움 (ERP, MES, 엑셀)
  - 대시보드 구성이 복잡함
- **Needs**:
  - 자연어 BI 쿼리
  - 드래그 앤 드롭 대시보드
  - 데이터 자동 리프레시
- **Scenarios**:
  - "지난 7일간 LINE-A 불량률 트렌드 보여줘" 입력
  - 차트 즉시 생성 (< 3초)
  - 대시보드에 추가 및 공유

#### Persona 4: 최엔지니어 (AI/ML 엔지니어)
- **나이**: 35세
- **경력**: 8년 (ML 5년, AI 플랫폼 3년)
- **목표**: Rule/Prompt 튜닝, 모델 성능 개선, 자동화
- **Pain Points**:
  - Rule 수동 작성 시간 소요
  - 배포 시 서비스 중단 우려
  - 실험 및 A/B 테스트 어려움
- **Needs**:
  - Rule 자동 추출
  - Canary 배포 (안전한 점진적 배포)
  - 메트릭 대시보드 (정확도, 비용)
- **Scenarios**:
  - 학습 샘플 450개로 Rule 자동 추출
  - Precision 92%, Recall 85% 확인
  - Canary 배포 (10% 트래픽, 60분)
  - 성공 기준 만족 → 100% 배포

---

## 4. 문제 정의 및 해결 방안

### 4.1 현장 Pain Points (고객 문제)

#### 4.1.1 판단 일관성 부족
**문제**:
- 품질/설비 이상 탐지 기준이 라인별·사람별로 다름
- 경험에 의존한 주관적 판단
- 표준화 어려움

**영향**:
- 오판으로 인한 불량 유출
- 오경보로 인한 현장 피로도 증가
- 신규 작업자 교육 시간 증가

**해결 방안**:
✅ **Rule Engine**: 표준화된 판단 기준 (Rhai 스크립트)
✅ **LLM Fallback**: Rule로 처리 어려운 복잡한 상황 대응
✅ **Hybrid Policy**: 두 방식 조합으로 정확도 극대화

#### 4.1.2 데이터 파편화
**문제**:
- ERP, MES, 센서, 엑셀 등 데이터 분산
- 수동 데이터 수집 및 정리 시간 소요
- 데이터 불일치 및 지연

**영향**:
- 의사결정 지연 (데이터 수집에 수시간)
- 데이터 신뢰성 문제
- 중복 작업

**해결 방안**:
✅ **Data Hub**: 자동 ETL (RAW → DIM → FACT)
✅ **MCP ToolHub**: 표준화된 외부 시스템 연동
✅ **Pre-aggregation**: Materialized View로 빠른 조회

#### 4.1.3 추적성 한계
**문제**:
- 불량 발생 시 원인 파악 어려움 (수일 소요)
- LOT 추적 수동 작업
- 변경 이력 관리 부족

**영향**:
- 근본 원인 미발견 → 재발
- 규제 준수 어려움 (HACCP, ISO)
- 리콜 발생 시 범위 파악 지연

**해결 방안**:
✅ **RCA Workflow**: 자동 근본 원인 분석 (< 60초)
✅ **Audit Log**: 모든 판단/Rule/배포 이력 보존 (2년)
✅ **Vector Search**: 유사 과거 케이스 즉시 검색

#### 4.1.4 개선 주기 지연
**문제**:
- 판단 기준 수정 시 개발자 필요
- 배포 주기 길음 (월 1회)
- 개선 효과 검증 어려움

**영향**:
- 현장 니즈 반영 지연
- 오경보 지속
- 시스템 신뢰도 하락

**해결 방안**:
✅ **Learning Pipeline**: 피드백 기반 자동 Rule 추출
✅ **Canary 배포**: 안전한 점진적 배포 (시간 단위)
✅ **A/B 테스트**: 배포 전후 성능 비교

---

## 5. 제품 범위 (Scope)

### 5.1 In-Scope (1차 릴리스 포함)

#### 5.1.1 Core Features

| 기능 | 설명 | 우선순위 |
|------|------|---------|
| **Hybrid Judgment Engine** | Rule + LLM 조합 판단, 6가지 정책 | P0 |
| **Workflow Engine** | 12가지 노드 타입, DSL 실행 | P0 |
| **BI Query Planner** | 자연어 → SQL, 차트 생성 | P0 |
| **MCP ToolHub** | Excel, GDrive, Jira 연동 | P1 |
| **Learning Pipeline** | 피드백 수집, Rule 자동 추출 | P1 |
| **Chat Interface** | Intent 분류, Slot 추출, Slack Bot | P1 |
| **Admin Dashboard** | 사용자 관리, 커넥터 설정, 모니터링 | P0 |

#### 5.1.2 Data & Integration

| 항목 | 설명 | 우선순위 |
|------|------|---------|
| **PostgreSQL Schema** | Core, BI, RAG 스키마 | P0 |
| **pgvector RAG** | 문서 벡터 검색, 유사 케이스 | P1 |
| **ERP/MES 연동** | DB 직접 연결 또는 REST API | P0 |
| **센서 연동** | MQTT 또는 OPC UA (기본 지원) | P2 |
| **Redis Cache** | Judgment, BI 쿼리 결과 캐싱 | P1 |

#### 5.1.3 Deployment & Operations

| 항목 | 설명 | 우선순위 |
|------|------|---------|
| **Canary 배포** | Rule/Prompt 점진적 배포 | P1 |
| **Monitoring** | Prometheus, Grafana, Loki | P0 |
| **Backup** | PostgreSQL 백업 (일 1회, WAL) | P0 |
| **High Availability** | 서비스 이중화, DB Replication | P1 |

### 5.2 Out-of-Scope (향후 확장)

#### 5.2.1 Advanced Features (Phase 2+)

| 기능 | 설명 | 예상 릴리스 |
|------|------|------------|
| **3D Digital Twin** | 물리적 충돌, 유체 역학 시뮬레이션 | Phase 3 (1년+) |
| **실시간 로봇/PLC 제어** | 실제 로봇 명령 전송 (현재는 시뮬레이션만) | Phase 2 (6개월) |
| **Edge AI** | 온디바이스 판단 (Collector 수준) | Phase 3 (1년+) |
| **강화학습 최적화** | RL 기반 자율 최적화 | Phase 3 (1년+) |
| **음성 인터페이스** | 음성 명령 및 응답 | Phase 2 (6개월) |
| **모바일 앱** | iOS/Android 네이티브 앱 | Phase 2 (6개월) |

#### 5.2.2 제외 사항 (Explicitly Excluded)

| 항목 | 이유 |
|------|------|
| **생산 계획 최적화** | ERP 영역, 스코프 외 |
| **자재 소요 계획 (MRP)** | ERP 영역, 스코프 외 |
| **인사/급여 관리** | 제조 AI와 무관 |
| **영상/CCTV 분석** | Phase 1에서는 제외 (Phase 2 고려) |

---

## 6. 주요 기능 개요

### 6.1 기능 맵

```
AI Factory Decision Engine
│
├─ 1. Judgment & Decision (판단 및 의사결정)
│   ├─ 1.1 Hybrid Judgment Engine (Rule + LLM)
│   ├─ 1.2 Confidence Scoring (신뢰도 계산)
│   ├─ 1.3 Explanation Generation (설명 생성)
│   ├─ 1.4 Caching (캐싱, TTL 300s)
│   └─ 1.5 Simulation (What-if, Replay)
│
├─ 2. Workflow Automation (워크플로우 자동화)
│   ├─ 2.1 DSL Parser & Validator (12 노드 타입)
│   ├─ 2.2 Workflow Executor (상태 관리, 재시도)
│   ├─ 2.3 Flow Control (SWITCH, PARALLEL, WAIT)
│   ├─ 2.4 Approval Workflow (승인 대기)
│   └─ 2.5 Visual Editor (드래그 앤 드롭)
│
├─ 3. BI & Analytics (데이터 분석)
│   ├─ 3.1 Natural Language Query (자연어 → SQL)
│   ├─ 3.2 BI Catalog (Dataset, Metric, Component)
│   ├─ 3.3 Chart Rendering (6가지 차트)
│   ├─ 3.4 Dashboard Builder (위젯 구성)
│   └─ 3.5 Scheduled Reports (정기 보고서 자동 생성)
│
├─ 4. Learning & Improvement (학습 및 개선)
│   ├─ 4.1 Feedback Collection (피드백 수집)
│   ├─ 4.2 Sample Curation (학습 데이터 구축)
│   ├─ 4.3 Auto Rule Extraction (Decision Tree)
│   ├─ 4.4 Prompt Tuning (Few-shot 업데이트)
│   └─ 4.5 Canary Deployment (안전한 배포)
│
├─ 5. Integration (통합)
│   ├─ 5.1 MCP ToolHub (Excel, GDrive, Jira)
│   ├─ 5.2 DB Connectors (ERP, MES)
│   ├─ 5.3 Sensor Integration (MQTT, OPC UA)
│   ├─ 5.4 Health Check (커넥터 상태 모니터링)
│   └─ 5.5 Drift Detection (스키마 변경 감지)
│
└─ 6. Chat & Collaboration (대화 및 협업)
    ├─ 6.1 Intent Classification (의도 분류)
    ├─ 6.2 Slot Extraction (파라미터 추출)
    ├─ 6.3 Multi-turn Dialog (연속 대화)
    ├─ 6.4 Slack Bot (멘션, 알림)
    └─ 6.5 Model Routing (비용 최적화)
```

### 6.2 주요 기능 상세

#### 6.2.1 Hybrid Judgment Engine

**개요**: Rule과 LLM을 조합하여 정확하고 설명 가능한 판단 제공

**핵심 기능**:
- **6가지 Judgment Policy**: RULE_ONLY, LLM_ONLY, RULE_FALLBACK, LLM_FALLBACK, HYBRID_WEIGHTED, HYBRID_GATE
- **신뢰도 기반 Fallback**: Rule 신뢰도 < 0.7 시 LLM 호출
- **Explanation**: 판단 근거, 증거 데이터, 추천 조치
- **Caching**: Redis 캐시 (TTL 300s), 응답 < 300ms
- **Simulation**: 과거 execution_id로 What-if 재실행

**사용 예시**:
```
입력: {line_code: "LINE-A", defect_count: 5, production_count: 100}
처리:
  1. Rule 실행 → 불량률 5% > 임계값 2% → HIGH_DEFECT (conf 0.95)
  2. 신뢰도 높음 → LLM 호출 생략 (비용 절감)
  3. 결과 반환 (1.2초)
출력: {status: "HIGH_DEFECT", confidence: 0.95, actions: ["Stop LINE-A"]}
```

#### 6.2.2 Workflow DSL Engine

**개요**: 다단계 워크플로우를 DSL로 정의하고 자동 실행

**핵심 기능**:
- **12가지 노드 타입**: DATA, BI, JUDGMENT, MCP, ACTION, APPROVAL, WAIT, SWITCH, PARALLEL, COMPENSATION, DEPLOY, ROLLBACK, SIMULATE
- **상태 영속화**: 장애 복구 및 재개 지원
- **Circuit Breaker**: 외부 서비스 장애 시 Fallback
- **Visual Editor**: 드래그 앤 드롭 워크플로우 구성

**사용 예시**:
```
RCA Workflow (불량 근본 원인 분석):
  1. DATA 노드: MES에서 생산 이력 조회
  2. BI 노드: 유사 불량 패턴 분석
  3. JUDGMENT 노드: 원인 추정 판단
  4. MCP 노드: Excel 설비 이력 조회
  5. ACTION 노드: Slack 알림 + Jira 이슈 생성
→ 전체 실행 시간: 45초
```

#### 6.2.3 Natural Language BI

**개요**: 자연어로 BI 쿼리를 실행하고 차트 즉시 생성

**핵심 기능**:
- **자연어 이해**: LLM 기반 analysis_plan 생성
- **SQL 자동 생성**: analysis_plan → SQL
- **6가지 차트**: Line, Bar, Pie, Scatter, Heatmap, Table
- **Query Caching**: Redis 캐시 (TTL 600s)

**사용 예시**:
```
입력: "지난 7일간 LINE-A 일별 생산량과 불량률 보여줘"
처리:
  1. LLM이 analysis_plan 생성 (1.5초)
  2. SQL 생성 및 실행 (0.5초)
  3. Line Chart 설정 생성 (0.2초)
  4. 프론트엔드 렌더링 (0.3초)
→ 전체 응답 시간: 2.5초
```

---

## 7. 비즈니스 모델

### 7.1 수익 모델

#### 7.1.1 SaaS 구독 모델

| 등급 | 월 요금 | Judgment/월 | 저장 용량 | 동시 Workflow | 타겟 고객 |
|------|---------|-------------|-----------|--------------|----------|
| **Free** | $0 | 1,000회 | 1GB | 5개 | 개인, 소규모 테스트 |
| **Standard** | $500 | 10,000회 | 10GB | 20개 | 중소기업 (5~10 라인) |
| **Premium** | $2,000 | 100,000회 | 100GB | 100개 | 중견기업 (10~20 라인) |
| **Enterprise** | Custom | Unlimited | Unlimited | Unlimited | 대기업 (20+ 라인) |

**추가 요금**:
- 추가 Judgment: $0.05/회
- 추가 저장 용량: $10/10GB/월
- LLM 비용: 실비 전가 (선택적)

#### 7.1.2 온프렘 라이선스

| 항목 | 가격 | 설명 |
|------|------|------|
| **라이선스** | $50,000 (1회) | 영구 라이선스 (1 서버, 500 사용자) |
| **유지보수** | $10,000/년 | 버그 수정, 보안 패치, 기술 지원 |
| **커스터마이징** | $5,000~$50,000 | 고객 요구사항 반영 (T&M) |

### 7.2 비용 구조

#### 7.2.1 클라우드 운영 비용 (월 기준)

| 항목 | 비용 | 설명 |
|------|------|------|
| **AWS 인프라** | $3,000 | EKS, EC2, RDS, S3 |
| **LLM API** | $500 | OpenAI GPT-4, Embeddings |
| **모니터링** | $100 | Prometheus, Grafana, Loki |
| **기타** | $200 | 도메인, 인증서, 백업 |
| **총 운영 비용** | $3,800/월 | - |

#### 7.2.2 개발 비용 (초기)

| 항목 | 인원 | 기간 | 비용 |
|------|------|------|------|
| **Backend 개발** | 3명 | 6개월 | $180,000 |
| **Frontend 개발** | 2명 | 6개월 | $120,000 |
| **AI/ML 엔지니어** | 2명 | 6개월 | $150,000 |
| **DevOps** | 1명 | 6개월 | $60,000 |
| **QA** | 1명 | 6개월 | $50,000 |
| **PM** | 1명 | 6개월 | $70,000 |
| **총 개발 비용** | - | - | $630,000 |

### 7.3 ROI 분석 (고객사 관점)

**가정**: 중견 제조업 (연 매출 1000억, 생산 라인 10개)

| 항목 | 현재 (As-Is) | 도입 후 (To-Be) | 절감 효과 |
|------|-------------|----------------|----------|
| **불량 손실** | 연 5억 (불량률 2%) | 연 3억 (불량률 1.2%) | **-2억** |
| **데이터 분석 인건비** | 연 1억 (2명) | 연 5천만 (1명, 자동화) | **-5천만** |
| **RCA 시간** | 수일 (수동) | 60초 (자동) | **시간 절감** |
| **시스템 비용** | - | 연 2,400만 (Premium) | **+2,400만** |
| **순 절감** | - | - | **연 2.26억** |

**ROI**: 첫 해 941%, Payback Period: 1.3개월

---

## 8. 성공 기준 및 메트릭

### 8.1 비즈니스 메트릭

| 메트릭 | 목표 (1년) | 측정 방법 |
|--------|-----------|----------|
| **고객 수** | 50개 기업 | CRM 데이터 |
| **ARR (Annual Recurring Revenue)** | $1.2M | 구독 매출 합계 |
| **Churn Rate** | < 5% | 이탈 고객 비율 |
| **NPS (Net Promoter Score)** | > 50 | 고객 설문 |
| **MAU (Monthly Active Users)** | 500명 | 로그인 사용자 수 |

### 8.2 제품 메트릭

| 메트릭 | 목표 | 측정 방법 |
|--------|------|----------|
| **Judgment 정확도** | > 90% | 피드백 기반 정확도 |
| **Judgment 평균 응답 시간** | < 1.5초 | Prometheus 메트릭 |
| **캐시 적중률** | > 40% | Redis 통계 |
| **Workflow 성공률** | > 99% | workflow_instances 통계 |
| **Intent 분류 정확도** | > 90% | 피드백 기반 정확도 |
| **LLM JSON 파싱 성공률** | > 99.5% | llm_calls 통계 |

### 8.3 운영 메트릭

| 메트릭 | 목표 | 측정 방법 |
|--------|------|----------|
| **시스템 가용성** | > 99.9% | Uptime 모니터링 |
| **평균 복구 시간 (MTTR)** | < 30분 | 장애 대응 로그 |
| **배포 빈도** | 주 2회 | CI/CD 통계 |
| **배포 성공률** | > 95% | 배포 로그 |
| **보안 취약점** | 0개 (Critical) | 보안 스캔 |

---

## 9. 로드맵 및 릴리스 계획

### 9.1 전체 로드맵 (2년)

```
2025 Q4          2026 Q1          2026 Q2          2026 Q3          2026 Q4
│                │                │                │                │
│ Phase 0        │ Phase 1 (MVP)  │ Phase 2        │ Phase 3        │
│ (기획/설계)     │ (핵심 기능)     │ (확장)         │ (고도화)        │
│                │                │                │                │
├─ A-1~A-3 ─────┤                │                │                │
├─ B-1~B-6 ─────┤                │                │                │
├─ C-1~C-5 ─────┤                │                │                │
├─ D-1~D-4 ─────┤                │                │                │
│                ├─ Release 1.0 ─┤                │                │
│                │ (3개월)        │                │                │
│                │ - Judgment     │                │                │
│                │ - Workflow     │                │                │
│                │ - BI           │                │                │
│                │                ├─ Release 1.1 ─┤                │
│                │                │ (2개월)        │                │
│                │                │ - Learning     │                │
│                │                │ - Canary       │                │
│                │                │ - Sensor       │                │
│                │                │                ├─ Release 1.2 ─┤
│                │                │                │ (2개월)        │
│                │                │                │ - Auto Rule    │
│                │                │                │ - Drift        │
│                │                │                │ - Mobile       │
```

### 9.2 릴리스 상세

#### Release 1.0 (MVP) - 2026년 1월

**목표**: 핵심 Judgment, Workflow, BI 기능 제공

**주요 기능**:
- ✅ Hybrid Judgment Engine (Rule + LLM, 6 Policy)
- ✅ Workflow Engine (12 노드, DSL 실행)
- ✅ BI Query Planner (자연어 → SQL)
- ✅ Web Dashboard (React)
- ✅ MCP ToolHub (Excel, GDrive)
- ✅ Admin Portal (사용자, 커넥터 관리)

**메트릭 목표**:
- 고객 수: 10개 (파일럿)
- MAU: 50명
- Judgment 정확도: > 80%
- 응답 시간: < 2초

**개발 기간**: 3개월 (2025년 12월 ~ 2026년 2월)

---

#### Release 1.1 (확장) - 2026년 3월

**목표**: 학습, 배포, 센서 연동 추가

**주요 기능**:
- ✅ Learning Pipeline (피드백, 샘플 큐레이션)
- ✅ Canary Deployment (Rule/Prompt 안전 배포)
- ✅ Sensor Integration (MQTT, OPC UA)
- ✅ Slack Bot (멘션, 알림)
- ✅ Health Check (커넥터 상태)

**메트릭 목표**:
- 고객 수: 25개
- MAU: 150명
- 학습 샘플: > 500개
- 캐시 적중률: > 40%

**개발 기간**: 2개월 (2026년 3월 ~ 2026년 4월)

---

#### Release 1.2 (고도화) - 2026년 5월

**목표**: AI 고도화, 자동화, 품질 개선

**주요 기능**:
- ✅ Auto Rule Extraction (Decision Tree)
- ✅ Prompt Tuning (Few-shot 자동 업데이트)
- ✅ Drift Detection (스키마 변경 감지)
- ✅ Mobile App (React Native)
- ✅ Advanced Monitoring (분산 추적, APM)

**메트릭 목표**:
- 고객 수: 50개
- MAU: 500명
- 자동 Rule 정확도: > 85%
- Drift 감지율: 100%

**개발 기간**: 2개월 (2026년 5월 ~ 2026년 6월)

---

## 10. 리스크 및 가정사항

### 10.1 주요 리스크

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|----------|
| **LLM API 장애/비용 증가** | 중 | 높음 | Rule 우선 사용, 여러 LLM 제공자 지원, Fallback |
| **고객사 데이터 품질 낮음** | 높음 | 중 | 데이터 품질 검사, 샘플 데이터 제공, 온보딩 교육 |
| **Rule 작성 복잡도** | 중 | 중 | Visual Rule Builder, 자동 Rule 추출, 템플릿 제공 |
| **망 분리 환경 배포 어려움** | 중 | 높음 | 온프렘 지원, Air-gap 설치 가이드, 프록시 지원 |
| **학습 데이터 부족** | 중 | 중 | 초기 Rule 수동 작성, Few-shot 프롬프트, 합성 데이터 |
| **보안/규제 준수** | 낮음 | 높음 | PII 마스킹, 감사 로그, 암호화, 컴플라이언스 체크리스트 |

### 10.2 가정사항

#### 10.2.1 기술 가정
- [ ] PostgreSQL 14+ 사용 가능
- [ ] pgvector 확장 설치 가능
- [ ] 외부 인터넷 연결 가능 (LLM API)
- [ ] Kubernetes 또는 Docker 환경
- [ ] 최소 4 CPU, 8GB RAM 서버

#### 10.2.2 데이터 가정
- [ ] 최소 6개월 이상 생산/품질 히스토리 데이터 제공
- [ ] ERP/MES API 또는 DB 접근 권한 제공
- [ ] 제품/라인/설비 마스터 데이터 제공
- [ ] 도메인 전문가 협조 (Rule 검증, 피드백)

#### 10.2.3 조직 가정
- [ ] 관리자 계정 생성 권한
- [ ] IT 담당자 배포 지원 (1~2명)
- [ ] 현장 전문가 피드백 제공 (주 1~2시간)
- [ ] 월 1회 리뷰 미팅 참석

---

## 결론

본 문서(A-1)는 **제조업 AI 플랫폼 (AI Factory Decision Engine)** 의 제품 비전과 범위를 명확히 정의하였다.

### 주요 성과
1. **명확한 비전**: "데이터 기반 의사결정을 실시간으로 지원하고, 지속적 학습을 통해 제조 품질과 생산성을 혁신"
2. **4가지 핵심 Pain Points** 식별 및 해결 방안 제시
3. **5가지 페르소나** 정의 (현장 관리자, 품질 관리자, 데이터 분석가, AI 엔지니어, 경영진)
4. **명확한 범위**: In-Scope (MVP), Out-of-Scope (Phase 2+)
5. **비즈니스 모델**: SaaS 구독 (4등급), 온프렘 라이선스
6. **ROI 분석**: 고객사 연 2.26억 절감, ROI 941%
7. **3단계 로드맵**: MVP (3개월) → 확장 (2개월) → 고도화 (2개월)

### 다음 단계
1. 요구사항 리뷰 (A-2) 및 고객 검증
2. MVP 프로토타입 개발 시작
3. 파일럿 고객사 모집 (3~5개)
4. 마케팅 자료 작성 (랜딩 페이지, 데모 영상)

---

## 문서 이력
| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-10-01 | Product Team | 초안 작성 |
| 2.0 | 2025-11-26 | AI Factory Team | Enhanced 버전 (시장 분석, 페르소나, 비즈니스 모델 추가) |
